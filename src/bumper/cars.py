import logging
import os
import pkg_resources


from bumper.utils import parse_requirements, PyPI

log = logging.getLogger(__name__)


class BumpAccident(Exception):
  """ Exception for any bump errors """
  pass


class BumpRequirement(object):
  """ A single requirement to be bumped or filtered. It is a wrapper on top of :class:`pkg_resources.Requirement`. """

  def __init__(self, req, required=False):
    """
      :param pkg_resources.Requirement req:
      :param bool required: Is this requirement required to be fulfilled? If not, then it is a filter.
    """
    self.requirement = req
    self.required = required
    self.required_by = None

  @classmethod
  def parse(cls, s, required=False):
    """
      Parse string to create an instance

      :param str s: String with requirement to parse
      :param bool required: Is this requirement required to be fulfilled? If not, then it is a filter.
    """
    req = pkg_resources.Requirement.parse(s)
    return cls(req, required=required)

  def __getattr__(self, attr):
    return getattr(self.requirement, attr)

  def __str__(self):
    return str(self.requirement)

  def __contains__(self, item):
    return item in self.requirement


class Bump(object):
  """ A change made in a target file. """

  def __init__(self, name, new_version, changes=None, requirements=None):
    """
      :param str name: Name of the product/library that was bumped
      :param str new_version: New version that was bumped to
      :param any changes: Detailed changelog entries from the old version to the new version
      :param str|list requirements: Any requirements that must be fulfilled for this bump to occur.
    """
    self.name = name
    self.new_version = new_version
    self.changes = changes
    self.requirements = []
    if requirements:
      self.requires(requirements)

  def __str__(self):
    if not self.new_version:
      return self.name
    elif self.new_version.startswith(('<', '>', '=', '!')):
      return self.name + self.new_version
    else:
      return '%s to %s' + (self.name, self.new_version)

  def __repr__(self):
    return '%s(%s, %s, reqs=%s)' % (self.__class__.__name__, self.name, self.new_version, len(self.requirements))

  @classmethod
  def from_requirement(cls, req, changes=None):
    """ Create an instance from :class:`pkg_resources.Requirement` instance """
    return cls(req.project_name, req.specs and ''.join(req.specs[0]) or '', changes=changes)

  def requires(self, req):
    """ Add new requirements that must be fulfilled for this bump to occur """
    reqs = req if isinstance(req, list) else [req]
    for req in reqs:
      req.required = True
      req.required_by = self
      self.requirements.append(req)

  def satisfies(self, req):
    """ Does this bump satisfies the given requirements? """
    if req.project_name != self.name:
      return False

    if not req.specs:
      return True

    if self.new_version.startswith(('<', '>', '=', '!')):
      req_version = ''.join(req.specs[0])
      return req_version == self.new_version
    else:
      return self.new_version in req


class AbstractBumper(object):
  """ Abstract implementation for all bumper cars """

  def __init__(self, target, detail=False, test_drive=False):
    """
      :param str target: Path to a target file to bump.
      :param bool detail: Generate detailed changes from changelog if possible.
      :param bool test_drive: Perform a dry run
    """
    self.target = target
    self.detail = detail
    self.test_drive = test_drive
    self.original_target_content = None
    self.found_bump_requirements = False
    self.bumps = []
    self.bumped = False

  def __repr__(self):
    return '%s(%s)' % (self.__class__.__name__, self.target)

  @classmethod
  def likes(cls, target):
    """ Check if this bumper likes the target. """
    raise NotImplementedError

  def _bump(self, bump_requirements, **kwargs):
    """
      Subclass must override this `_bump` method and not the `bump` method.
      This does the actual bumping/updating of files based on the requirements.

      :param list bump_requirements: Dict of product name to :class:`BumpRequirement` instances to be bumped.
                                     If any of the requirement project names is found in `self.target`, then
                                     `self.found_bump_requirements` will be set to True.
      :param dict kwargs: Additional args from argparse. Some bumpers accept user options, and some not.
      :return: List of :class:`Bump` changes made.
    """
    raise NotImplementedError

  def bump_message(self, include_changes=False):
    """ Compose a bump message for the given bumps """
    raise NotImplementedError

  def bump(self, bump_requirements=None, **kwargs):
    """
      Bump dependencies using given requirements.

      :param list bump_requirements: Dict of product name to :class:`BumpRequirement` instances to be bumped.
                                     If any of the requirement project names is found in `self.target`, then
                                     `self.found_bump_requirements` will be set to True.
      :param dict kwargs: Additional args from argparse. Some bumpers accept user options, and some not.
      :return: List of :class:`Bump` changes made.
    """
    if not self.original_target_content:
      with open(self.target) as fp:
        self.original_target_content = fp.read()

    bumps = self._bump(bump_requirements, **kwargs)

    self.bumps.extend(bumps)
    self.bumped = True

    return bumps

  def reverse(self):
    """ Revert any bumps made. """
    if self.original_target_content:
      with open(self.target, 'w') as fp:
        fp.write(self.original_target_content)


class RequirementsBumper(AbstractBumper):
  """ Bumper for requirements.txt or pinned.txt """

  def __init__(self, target, detail=False, test_drive=False):
    super(RequirementsBumper, self).__init__(target, detail, test_drive)

    #: Pin requirements to a specific version using '==' when appropriate
    self.pin = target.endswith('pinned.txt')

  @classmethod
  def likes(cls, target):
    return target.endswith(('requirements.txt', 'pinned.txt'))

  def _bump(self, bump_requirements=None, **kwargs):
    # Represents all requirements in the file that will be written out later (contains updated)
    requirements = {}

    # Comments for requirements
    requirement_comments = {}

    # Represents only the updated requirements that will be used to generate commit msg.
    bumps = []

    comments = []

    for req in self.original_target_content.strip().split('\n'):
      if not req or req.startswith('#'):
        comments.append(req)
        continue

      req = parse_requirements(req, self.target)[0]

      if comments:
        requirement_comments[req.project_name] = '\n'.join(comments)
        comments = []

      if not bump_requirements or req.project_name in bump_requirements and not bump_requirements[req.project_name].specs:
        self.found_bump_requirements = True

        if req.specs:
          latest_version = PyPI.latest_package_version(req.project_name)
          if latest_version in req:
            if req.project_name in bump_requirements:
              bump_requirements[req.project_name].required = False

          else:
            op = req.specs[0][0]
            if op == '<':
              op = '<='
            elif op == '>':
              op = '>='
            elif op == '!=':
              log.warn('%s will not be bumped as it explicitly excludes latest version')
              op = None
            if op:
              current_version = req.specs[0][1]
              req = pkg_resources.Requirement.parse(req.project_name + op + latest_version)
              changes = PyPI.changes(req.project_name, current_version, latest_version) if self.detail else None
              bumps.append(Bump(req.project_name, op + latest_version, changes=changes))

        elif req.project_name in bump_requirements:
          bump_requirements[req.project_name].required = False

      elif req.project_name in bump_requirements and bump_requirements[req.project_name].specs:
        self.found_bump_requirements = True

        if str(req) == str(bump_requirements[req.project_name]):
          bump_requirements[req.project_name].required = False
        else:
          current_version = req.specs and req.specs[0][1]
          req = bump_requirements[req.project_name]
          self._check_requirement(req)
          changes = PyPI.changes(req.project_name, current_version, req.specs[0][1]) if self.detail else None
          bumps.append(Bump.from_requirement(req, changes))

      requirements[req.project_name] = req

    # Add new requirements
    for name, req in bump_requirements.items():
      if req.required and name not in requirements:
        try:
          latest_version = PyPI.latest_package_version(name)
        except Exception:
          log.debug('Will not add new requirement for %s to %s as it is not published on PyPI', name, self.target)
          continue

        if self.pin and not req.specs:
          req = pkg_resources.Requirement.parse(name + '==' + latest_version)
        else:
          self._check_requirement(req)

        requirements[name] = req
        bumps.append(Bump.from_requirement(req))

    if bumps and not self.test_drive:
      with open(self.target, 'w') as fp:
        for name in sorted(requirements):
          if name in requirement_comments:
            fp.write(requirement_comments[name] + '\n')
          fp.write(str(requirements[name]) + '\n')

    return bumps

  def bump_message(self, include_changes=False):
    if not self.bumps:
      return

    bumps = (' ').join(sorted([str(b) for b in self.bumps]))
    msg = 'Bump %s: %s' % (os.path.basename(self.target), bumps)

    if include_changes:
      changes = []
      for bump in self.bumps:
        if bump.changes:
          changes.append(bump.name)
          changes.append('  ' + '\n  '.join(bump.changes))
          changes.append('')
      if changes:
        msg += '\n\n' + '\n'.join(changes)

    return msg

  def _check_requirement(self, req):
    all_package_versions = PyPI.all_package_versions(req.project_name)
    if req.specs and not any(version in req for version in all_package_versions):
      msg = ('There are no published versions that satisfies %s\n        '
             'Please change to match at least one of these: %s' % (req, ', '.join(all_package_versions[:10])))
      raise BumpAccident(msg)

