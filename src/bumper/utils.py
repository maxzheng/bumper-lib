import base64
import logging
import pkg_resources
import re

import requests
import simplejson

log = logging.getLogger(__name__)


def parse_requirements(requirements, in_file=None):
  """
    Parse string requirements into list of :class:`pkg_resources.Requirement` instances

    :param str requirements: Requirements text to parse
    :param str in_file: File the requirements came from
    :return: List of requirements
    :raises ValueError: if failed to parse
  """
  try:
    return list(pkg_resources.parse_requirements(requirements))
  except Exception as e:
    in_file = ' in %s' % in_file if in_file else ''
    raise ValueError(' '.join(e) + in_file)


class PyPI(object):
  """ Helper functions to get package info from PyPI """

  package_info_cache = {}

  @classmethod
  def package_info(cls, package):
    """ All package info for given package """

    if package not in cls.package_info_cache:
      package_json_url = 'https://pypi.python.org/pypi/%s/json' % package

      try:
        logging.getLogger('requests').setLevel(logging.WARN)
        response = requests.get(package_json_url)
        response.raise_for_status()

        cls.package_info_cache[package] = simplejson.loads(response.text)

      except Exception as e:
        log.debug('Could not get package info from %s: %s', package_json_url, e)
        cls.package_info_cache[package] = None

    return cls.package_info_cache[package]

  @staticmethod
  def latest_package_version(package):
    """ Latest version for package """
    info = PyPI.package_info(package)
    return info and info['info']['version']

  @staticmethod
  def all_package_versions(package):
    """ All versions for package """
    info = PyPI.package_info(package)
    return info and sorted(info['releases'].keys(), key=lambda x: x.split(), reverse=True) or []

  @staticmethod
  def changes(package, current_version, new_version):
    changes = []

    if not current_version:
      return changes

    parsed_current_version = pkg_resources.parse_version(current_version)
    parsed_new_version = pkg_resources.parse_version(new_version)

    try:
      package_info = PyPI.package_info(package)

      repo_url = None
      repo_re = re.compile('https?://(?:github.com|bitbucket.org)/[\w\-]+/' + package)

      for url_name in ['home_page', 'docs_url']:
        if package_info['info'].get(url_name):
          match = repo_re.match(package_info['info'][url_name])
          if match:
            repo_url = match.group(0)

      if not repo_url and package_info['info'].get('description'):
        match = repo_re.search(package_info['info']['description'])
        if match:
          repo_url = match.group(0)

      if not repo_url:
        log.debug('Could not find repo url for %s to get changelog', package)
        return changes

      changelog = PyPI._changelog(repo_url)
      version_re = re.compile('^(?:Version )?(\d+(?:\.\d+)+)', flags=re.IGNORECASE)
      hr_re = re.compile('^\s*(?:[\-=~+]+)\s*$')

      if changelog:
        version = None
        for line in changelog.split('\n'):
          line = line.rstrip()

          if not line or hr_re.match(line):
            continue

          match = version_re.match(line)
          if match:
            version = match.group(1)
            parsed_version = pkg_resources.parse_version(version)
            if parsed_version <= parsed_current_version:
              break
            if parsed_version <= parsed_new_version:
              changes.append(version)
            else:
              version = None
            continue

          if version:
            if line.startswith('- '):
              line = '+' + line.lstrip('-')
            changes.append('  ' + line)

    except Exception as e:
      log.debug('Could not parse changelog file: %s', e)

    return changes

  @staticmethod
  def _changelog(repo_url):
    if 'github.com' in repo_url:
      repo_url = repo_url.replace('github.com', 'api.github.com/repos').replace('http:', 'https:') + '/contents'
      doc_dirs = []

      def get_changelog(repo_url, entry):
        if entry['type'] == 'file' and entry['name'].lower().startswith(('change', 'history')):
          try:
            response = requests.get(repo_url + '/' + entry['name'], timeout=5)
            response.raise_for_status()

            return base64.decodestring(response.json()['content'])

          except Exception as e:
            log.debug('%s/%s: %s' % (repo_url, entry['name'], e))

      try:
        for entry in requests.get(repo_url, timeout=5).json():
          changelog = get_changelog(repo_url, entry)
          if changelog:
            return changelog

          elif entry['type'] == 'dir' and entry['name'].lower().startswith('doc'):
            doc_dirs.append(entry['name'])

        for doc_dir in doc_dirs:
          for entry in requests.get(repo_url + '/' + doc_dir, timeout=5).json():
            changelog = get_changelog(repo_url + '/' + doc_dir, entry)
            if changelog:
              return changelog

      except Exception as e:
        log.debug('Could not find changelog file: %s', e)

    else:
      for change_ext in ['rst', 'md', 'txt', None]:
        for change_name in ['CHANGELOG', 'HISTORY', 'CHANGES', 'changes']:
          for subfolder in ['', 'docs']:
            changelog_url = '%s/%s/%s%s' % (repo_url, subfolder, change_name, '.' + change_ext if change_ext else '')
            log.debug('Trying %s', changelog_url)
            try:
              response = requests.get(changelog_url, timeout=5)
              response.raise_for_status()

              return response.text

            except Exception:
              pass
