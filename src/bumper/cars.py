import logging
import os
import pkg_resources
import sys

from bumper.utils import parse_requirements, PYPI

log = logging.getLogger(__name__)


class BumpRequirement(object):
  """ A single requirement to be bumped """

  def __init__(self, req, required=False):
    self.requirement = req
    self.required = required
    self.required_by = None

  @classmethod
  def parse(cls, s, required=False):
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
    self.name = name
    self.new_version = new_version
    self.changes = changes
    self.requirements = []
    if requirements:
      self.requires(requirements)

  @classmethod
  def from_requirement(cls, req):
    return cls(req.project_name, req.specs and ''.join(req.specs[0]) or '')

  def requires(self, req):
    reqs = req if isinstance(req, list) else [req]
    for req in reqs:
      req.required = True
      req.required_by = self
      self.requirements.append(req)

  def satisfies(self, req):
    if req.project_name != self.name:
      return False

    if not req.specs:
      return True

    if self.new_version.startswith(('<', '>', '=', '!')):
      req_version = ''.join(req.specs[0])
      return req_version == self.new_version
    else:
      return self.new_version in req

  def __str__(self):
    if not self.new_version:
      return self.name
    elif self.new_version.startswith(('<', '>', '=', '!')):
      return self.name + self.new_version
    else:
      return '%s to %s' + (self.name, self.new_version)


class AbstractBumper(object):
  """ Abstract implementation for all bumper cars """

  def __init__(self, target, test_drive=False):
    """
      Initialize with the target to bump.

      :param str target: Path to a target file to bump.
      :param bool test_drive: Perform a dry run
    """
    self.target = target
    self.test_drive = test_drive
    self.original_target_content = None
    self.found_bump_requirements = False
    self.bumps = []
    self.bumped = False

  @classmethod
  def likes(cls, target):
    """ Check if this bumper likes the target. """
    raise NotImplementedError

  def _bump(self, bump_requirements, **kwargs):
    raise NotImplementedError

  def bump_message(self, include_changes=False):
    """
      Compose a bump message for the given bumps
    """
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
          latest_version = PYPI.latest_module_version(req.project_name)
          if latest_version not in req:
            op = req.specs[0][0]
            if op == '<':
              op = '<='
            elif op == '>':
              op = '>='
            elif op == '!=':
              log.warn('%s will not be bumped as it explicitly excludes latest version')
              op = None
            if op:
              req = pkg_resources.Requirement.parse(req.project_name + op + latest_version)
              bumps.append(Bump(req.project_name, op + latest_version))

        elif req.project_name in bump_requirements:
          bump_requirements[req.project_name].required = False

      elif req.project_name in bump_requirements and bump_requirements[req.project_name].specs:
        self.found_bump_requirements = True

        if str(req) == str(bump_requirements[req.project_name]):
          bump_requirements[req.project_name].required = False
        else:
          req = bump_requirements[req.project_name]
          self._check_requirement(req)
          bumps.append(Bump.from_requirement(req))

      requirements[req.project_name] = req

    for name, req in bump_requirements.items():
      if req.required and name not in requirements:
        try:
          latest_version = PYPI.latest_module_version(name)
        except Exception:
          log.debug('Will not add new requirement for %s to %s as it is not published on PyPI', name, self.target)
          continue

        if self.target.endswith('pinned.txt') and (not req.specs or req.specs[0][0].startswith('>')):
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
    msg = 'Update %s: %s' % (os.path.basename(self.target), bumps)

    return msg

  def _check_requirement(self, req):
    all_module_versions = PYPI.all_module_versions(req.project_name)
    if req.specs and not any(version in req for version in all_module_versions):
      log.error('There are no published versions that satisfies %s', req)
      log.info('Please change to match at least one of these: %s', ', '.join(all_module_versions[:10]))
      sys.exit(1)
