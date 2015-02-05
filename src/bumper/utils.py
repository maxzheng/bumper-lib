import logging
import pkg_resources
import requests
import simplejson
import sys

log = logging.getLogger(__name__)


def parse_requirements(requirements, in_file=None):
  """ Parse string requirements into list of :class:`pkg_resources.Requirement` instances """
  try:
    return list(pkg_resources.parse_requirements(requirements))
  except Exception as e:
    in_file = ' in %s' % in_file if in_file else ''
    log.error(' '.join(e) + in_file)
    sys.exit(1)


class PyPI(object):
  """ Helper functions to get package info from PyPI """

  @staticmethod
  def module_info(module):
    """ All module info for given module """
    module_json_url = 'https://pypi.python.org/pypi/%s/json' % module

    try:
      logging.getLogger('requests').setLevel(logging.WARN)
      response = requests.get(module_json_url)
      response.raise_for_status()

      return simplejson.loads(response.text)
    except Exception as e:
      raise Exception('Could not get module info from %s: %s', module_json_url, e)

  @staticmethod
  def latest_module_version(module):
    """ Latest version for module """
    return PyPI.module_info(module)['info']['version']

  @staticmethod
  def all_module_versions(module):
    """ All versions for module """
    return sorted(PyPI.module_info(module)['releases'].keys(), key=lambda x: x.split(), reverse=True)
