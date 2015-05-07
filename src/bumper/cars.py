from collections import defaultdict
import logging
import pkg_resources
import re

from bumper.utils import parse_requirements, PyPI

log = logging.getLogger(__name__)
REQUIREMENTS_STR = '([\w\-]+)([>=<!\d+\.]+| to ([\d\.]+))?'
REQUIREMENTS_RE = re.compile(REQUIREMENTS_STR)
IS_REQUIREMENTS_RE = re.compile('^(?:Bump|Require|Pin) ((?:%s)(?:, %s)*)$' % (REQUIREMENTS_STR, REQUIREMENTS_STR))
IS_REQUIREMENTS_RE2 = re.compile('requires?=(\w+.+)')


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

  def __eq__(self, other):
      return (
          isinstance(other, BumpRequirement) and
          self.requirement.hashCmp == other.requirement.hashCmp and
          self.required == other.required and
          self.required_by == other.required_by
      )

  def __getattr__(self, attr):
    return getattr(self.requirement, attr)

  def __repr__(self):
    return '%s(%s, required=%s/%s)' % (self.__class__.__name__, str(self), self.required, self.required_by)

  def __str__(self):
    return str(self.requirement)

  def __contains__(self, item):
    return item in self.requirement


class RequirementsManager(object):
  """ Manage a list of :class:`BumpRequirement` """

  def __init__(self, requirements=None):
    """
    :param list requirements: List of requirements to manage
    """
    self.requirements = defaultdict(list)
    self.matched_name = False
    self.checked = []
    if requirements:
      self.add(requirements)

  def __iter__(self):
    for reqs in self.requirements.values():
      for req in reqs:
        yield req

  def __getitem__(self, key):
    return self.requirements[key]

  def __contains__(self, item):
    return item in self.requirements

  def __len__(self):
    return len(self.requirements)

  def add(self, requirements, required=None):
    """
    Add requirements to be managed

    :param list/Requirement requirements: List of :class:`BumpRequirement` or :class:`pkg_resources.Requirement`
    :param bool required: Set required flag for each requirement if provided.
    """
    if isinstance(requirements, RequirementsManager):
      requirements = list(requirements)
    elif not isinstance(requirements, list):
      requirements = [requirements]

    for req in requirements:
      name = req.project_name

      if not isinstance(req, BumpRequirement):
        req = BumpRequirement(req, required=required)
      elif required is not None:
        req.required = required

      add = True

      if name in self.requirements:
        for existing_req in self.requirements[name]:
          if req == existing_req:
            add = False
            break

          # Need to replace existing as the new req will be used to bump next, and req.required could be updated.
          replace = False

          # Two pins: Use highest pinned version
          if req.specs and req.specs[0][0] == '==' and existing_req.specs and existing_req.specs[0][0] == '==':
            if pkg_resources.parse_version(req.specs[0][1]) < pkg_resources.parse_version(existing_req.specs[0][1]):
              req.requirement = existing_req.requirement
            replace = True

          # Replace Any
          if not (req.specs and existing_req.specs):
            if existing_req.specs:
              req.requirement = existing_req.requirement
            replace = True

          if replace:
            req.required |= existing_req.required
            if existing_req.required_by and not req.required_by:
              req.required_by = existing_req.required_by
            self.requirements[name].remove(existing_req)
            break

      if add:
        self.requirements[name].append(req)

  def get(self, name):
    return self.requirements.get(name)

  def check(self, context, version=None):
    """
    Check off requirements that are met by name/version.

    :param str|Bump|Requirement context: Either package name, requirement string, :class:`Bump`, :class:`BumpRequirement`, or
                                         :class:`pkg_resources.Requirement instance
    :return: True if any requirement was satisified by context
    """
    req_str = None

    self.checked.append((context, version))

    if isinstance(context, str) and not version:
      context = BumpRequirement.parse(context)

    if isinstance(context, Bump):
      name = context.name
      if context.new_version and context.new_version[0] == '==':
        version = context.new_version[1]
      else:
        req_str = str(context)

    elif isinstance(context, (pkg_resources.Requirement, BumpRequirement)):
      name = context.project_name
      if context.specs and context.specs[0][0] == '==':
        version = context.specs[0][1]
      else:
        req_str = str(context)

    else:
      name = context

    if name in self:
      self.matched_name = True

      for req in self[name]:
        if req.required and (version and version in req or req_str == str(req)):
          req.required = False
          return True

    return False

  def satisfied_by_checked(self, req):
    """
    Check if requirement is already satisfied by what was previously checked

    :param Requirement req: Requirement to check
    """
    req_man = RequirementsManager([req])

    return any(req_man.check(*checked) for checked in self.checked)

  def required_requirements(self):
    required = defaultdict(list)

    for reqs in self.requirements.values():
      for req in reqs:
        if req.required:
          required[req.project_name].append(req)

    return required


class Bump(object):
  """ A change made in a target file. """

  def __init__(self, name, new_version=None, changes=None, requirements=None):
    """
      :param str name: Name of the product/library that was bumped
      :param tuple new_version: New version that was bumped to in (op, version) format.
      :param list changes: Detailed changelog entries from the old version to the new version
      :param str|list requirements: Any requirements that must be fulfilled for this bump to occur.
    """
    self.name = name
    self.new_version = new_version
    self.changes = changes or []
    self.requirements = []
    if requirements:
      self.require(requirements)

  def __eq__(self, other):
    return str(self) == str(other)

  def __hash__(self):
    return hash(str(self))

  def __str__(self):
    if not self.new_version:
      return self.name
    else:
      return self.name + ''.join(self.new_version)

  def __repr__(self):
    return '%s(%s, %s, reqs=%s)' % (self.__class__.__name__, self.name, str(self.new_version), len(self.requirements))

  @classmethod
  def from_requirement(cls, req, changes=None):
    """ Create an instance from :class:`pkg_resources.Requirement` instance """
    return cls(req.project_name, req.specs and ''.join(req.specs[0]) or '', changes=changes)

  def as_requirement(self):
    """ Convert back to a :class:`pkg_resources.Requirement` instance """
    if self.new_version:
      return pkg_resources.Requirement.parse(self.name + ''.join(self.new_version))
    else:
      return pkg_resources.Requirement.parse(self.name)

  def require(self, req):
    """ Add new requirements that must be fulfilled for this bump to occur """
    reqs = req if isinstance(req, list) else [req]

    for req in reqs:
      if not isinstance(req, BumpRequirement):
        req = BumpRequirement(req)
      req.required = True
      req.required_by = self
      self.requirements.append(req)


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
    self.bumps = set()
    self._original_target_content = None

  @classmethod
  def requirements_for_changes(self, changes):
    """
    Parse changes for requirements

    :param list changes:
    """
    requirements = []
    reqs_set = set()

    if isinstance(changes, str):
      changes = changes.split('\n')

    if not changes or changes[0].startswith('-'):
      return requirements

    for line in changes:
      line = line.strip(' -+*')

      if not line:
        continue

      match = IS_REQUIREMENTS_RE2.search(line)  # or  IS_REQUIREMENTS_RE.match(line)
      if match:
        for match in REQUIREMENTS_RE.findall(match.group(1)):
          if match[1]:
            version = '==' + match[2] if match[1].startswith(' to ') else match[1]
            req_str = match[0] + version
          else:
            req_str = match[0]

          if req_str not in reqs_set:
            reqs_set.add(req_str)
            try:
              requirements.append(pkg_resources.Requirement.parse(req_str))
            except Exception as e:
              log.warn('Could not parse requirement "%s" from changes: %s', req_str, e)

    return requirements

  def __repr__(self):
    return '%s(%s)' % (self.__class__.__name__, self.target)

  @property
  def original_target_content(self):
    if not self._original_target_content:
      with open(self.target) as fp:
        self._original_target_content = fp.read()

    return self._original_target_content

  @classmethod
  def likes(cls, target):
    """ Check if this bumper likes the target. """
    raise NotImplementedError

  @classmethod
  def bump_message(self, bumps, include_changes=False):
    """
    Compose a bump message for the given bumps

    :param list bumps: List of :class:`Bump` instances
    :param bool include_changes: Indicate if the message should include detailed changes.
    """
    raise NotImplementedError

  def requirements(self):
    """ Return a list of existing requirements (as :class:`pkg_resources.Requirement`) """
    raise NotImplementedError

  def update_requirements(self):
    """ Update/persist requirements from `self.bumps` """
    raise NotImplementedError

  def _package_changes(self, name, current_version, new_version):
    """
      List of changes for package name from current_version to new_version, in descending order.

      :param str name: Name of package
      :param current_version: Current version
      :param new_version: New version. It is guaranteed to be higher than current version.
    """
    raise NotImplementedError

  def all_package_versions(self, name):
    """ List of all versions, in descending order, for the given package name. """
    raise NotImplementedError

  def latest_package_version(self, name):
    """ Latest version for the given package name. """
    return self.all_package_versions(name)[0]

  def should_pin(self):
    """ Should requirement be pinned? This should be True for leaf products. """
    return False

  def package_changes(self, name, current_version, new_version):
    """
      List of changes for package name from current_version to new_version, in descending order.
      If current version is higher than new version (downgrade), then a minus sign will be prefixed to each change.
    """
    if pkg_resources.parse_version(current_version) > pkg_resources.parse_version(new_version):
      downgrade_sign = '- '
      (current_version, new_version) = (new_version, current_version)
    else:
      downgrade_sign = None

    changes = self._package_changes(name, current_version, new_version)

    if changes and downgrade_sign:
      changes = [downgrade_sign + c for c in changes]

    return changes

  def latest_version_for_requirements(self, reqs):
    all_package_versions = self.all_package_versions(reqs[0].project_name)

    for version in all_package_versions:
      if all(version in r for r in reqs):
        return version

    if all_package_versions:
      raise BumpAccident('No published version could satisfy the requirement(s): %s\n\tLatest published versions: %s' %
                         (', '.join(str(r) for r in reqs), ', '.join(all_package_versions[:10])))
    else:
      raise BumpAccident('No published versions found for "%s"' % reqs[0].project_name)

  def _bump(self, existing_req=None, bump_reqs=None):
    """
      Bump an existing requirement to the desired requirement if any.
      Subclass can override this `_bump` method to change how each requirement is bumped.

      BR = Bump to Requested Version
      BL = Bump to Latest Version
      BLR = Bump to Latest Version per Requested Requirement
      BROL = Bump to Requested Version or Latest (if Pin)
      N = No Bump
      ERR = Error
      C = Version Conflict

      Pin case "requires=" will be required.
      Filter case "requires=" will be:
         1) From user = Required
         2) From bump = bump/require if existing = One, otherwise print warning.

      Filter Case::
          Bump:    None  Any  One  Many
      Existing:
           None    N     N    N    N
            Any    N     N    BR   BR
            One    BL    BL   BR   BR
           Many    N     N    BR   BR

      Pin Case::
          Bump:    None  Any  One  Many
      Existing:
           None    N     N    N    N
            Any    N     N    BR   BLR*
            One    BL    BL   BR   BLR*
           Many    N     N    BR   BLR*

      Add/Require Case::
          Bump:    None  Any  One  Many
      Existing:
           None    N     BROL BROL BROL

      :param pkg_resources.Requirement existing_req: Existing requirement if any
      :param list bump_reqs: List of `BumpRequirement`
      :return Bump: Either a :class:`Bump` instance or None
      :raise BumpAccident:
    """
    if existing_req or bump_reqs and any(r.required for r in bump_reqs):
      name = existing_req and existing_req.project_name or bump_reqs[0].project_name

      log.info('Checking %s', name)

      bump = current_version = new_version = None

      if bump_reqs:
        # BLR: Pin with Many bump requirements
        if self.should_pin() and (len(bump_reqs) > 1 or bump_reqs[0] and bump_reqs[0].specs and bump_reqs[0].specs[0][0] != '=='):
          log.debug('Bump to latest within requirements: %s', bump_reqs)

          new_version = self.latest_version_for_requirements(bump_reqs)
          current_version = existing_req and existing_req.specs and existing_req.specs[0][0] == '==' and existing_req.specs[0][1]

          if current_version == new_version:
            return None

          bump = Bump(name, ('==', new_version))

        elif len(bump_reqs) > 1:
          raise BumpAccident('Not sure which requirement to use for %s: %s' % (name, ', '.join(str(r) for r in bump_reqs)))

        # BR: Pin with One bump requirement or Filter with One or Many bump requirements or Bump to Any reuqired.
        elif bump_reqs[0].specs or not (existing_req or self.should_pin() or bump_reqs[0].specs):
          log.debug('Bump to requirement: %s', bump_reqs)

          latest_version = self.latest_version_for_requirements(bump_reqs)

          new_version = bump_reqs[0].specs and bump_reqs[0].specs[0][0] == '==' and bump_reqs[0].specs[0][1] or latest_version
          current_version = existing_req and existing_req.specs and existing_req.specs[0][0] == '==' and existing_req.specs[0][1]

          if current_version == new_version:
            return None

          if len(bump_reqs[0].specs) > 1:
            version = (','.join(s[0] + s[1] for s in bump_reqs[0].specs),)
          elif bump_reqs[0].specs:
            version = bump_reqs[0].specs[0]
          else:
            version = None
          bump = Bump(name, version)

      # BL: Pin to Latest
      if not bump and (existing_req and existing_req.specs and existing_req.specs[0][0] == '==' or self.should_pin() and not existing_req):
        log.debug('Bump to latest: %s', bump_reqs or name)

        current_version = existing_req and existing_req.specs[0][1]
        new_version = self.latest_package_version(name)

        if current_version == new_version:
          return None

        if not new_version:
          raise BumpAccident('No published version found for %s' % name)

        bump = Bump(name, ('==', new_version))

      if bump and current_version and new_version and self.detail:
        changes = self.package_changes(bump.name, current_version, new_version)
        bump.changes.extend(changes)
        if self.should_pin():
          bump.require(self.requirements_for_changes(changes))

      if bump:
        log.debug('Bumped %s', bump)

        if bump.requirements:
          log.info('Changes in %s require: %s', bump.name, ', '.join(sorted(str(r) for r in bump.requirements)))

      return bump if str(bump) != str(existing_req) else None

  def bump(self, bump_reqs=None, **kwargs):
    """
      Bump dependencies using given requirements.

      :param RequirementsManager bump_reqs: Bump requirements manager
      :param dict kwargs: Additional args from argparse. Some bumpers accept user options, and some not.
      :return: List of :class:`Bump` changes made.
    """

    bumps = {}

    for existing_req in sorted(self.requirements(), key=lambda r: r.project_name):
      if bump_reqs and existing_req.project_name not in bump_reqs:
        continue

      bump_reqs.check(existing_req)

      try:
        bump = self._bump(existing_req, bump_reqs.get(existing_req.project_name))

        if bump:
          bumps[bump.name] = bump
          bump_reqs.check(bump)

      except Exception as e:
        if not bump_reqs or bump_reqs.get(existing_req.project_name) and all(r.required_by is None for r in bump_reqs.get(existing_req.project_name)):
          raise
        else:
          log.warn(e)

    for reqs in bump_reqs.required_requirements().values():
      name = reqs[0].project_name
      if name not in bumps and self.should_add(name):
        try:
          bump = self._bump(None, reqs)

          if bump:
            bumps[bump.name] = bump
            bump_reqs.check(bump)

        except Exception as e:
          if all(r.required_by is None for r in reqs):
            raise
          else:
            log.warn(e)

    self.bumps.update(bumps.values())

    return bumps.values()

  def reverse(self):
    """ Restore content in target file to be before any changes """
    if self._original_target_content:
      with open(self.target, 'w') as fp:
        fp.write(self._original_target_content)


class RequirementsBumper(AbstractBumper):
  """ Bumper for requirements.txt or pinned.txt """

  def __init__(self, target, detail=False, test_drive=False):
    super(RequirementsBumper, self).__init__(target, detail, test_drive)

    # Represents all requirements in the file that will be written out later (contains updated)
    self._requirements = {}

    # Comments for requirements
    self.requirement_comments = {}

  @classmethod
  def likes(cls, target):
    return target.endswith(('requirements.txt', 'pinned.txt'))

  def should_pin(self):
    return self.target.endswith('pinned.txt')

  def should_add(self, name):
    """ Should this bumper try to add the given name if requested. """
    return True

  def bump_message(self, include_changes=False):
    if not self.bumps:
      return

    bumps = (', ').join(sorted([str(b) for b in self.bumps]))
    bump_word = 'Pin' if self.should_pin() else 'Require'
    msg = '%s %s' % (bump_word, bumps)

    if include_changes:
      changes = []
      for bump in sorted(self.bumps, key=lambda b: b.name):
        if bump.changes:
          changes.append(bump.name)
          changes.append('  ' + '\n  '.join(bump.changes))
          changes.append('')
      if changes:
        msg += '\n\n' + '\n'.join(changes)

    return msg

  def requirements(self):
    if not self._requirements:
      comments = []

      for req in self.original_target_content.strip().split('\n'):
        if not req or req.startswith('#'):
          comments.append(req)
          continue

        req = parse_requirements(req, self.target)[0]
        self._requirements[req.project_name] = req

        if comments:
          self.requirement_comments[req.project_name] = '\n'.join(comments)
          comments = []

    return self._requirements.values()

  def update_requirements(self):
    if self.bumps and not self.test_drive:
      for bump in self.bumps:
        self._requirements[bump.name] = bump.as_requirement()

      with open(self.target, 'w') as fp:
        for name in sorted(self._requirements):
          if name in self.requirement_comments:
            fp.write(self.requirement_comments[name] + '\n')
          fp.write(str(self._requirements[name]) + '\n')

  def _package_changes(self, name, current_version, new_version):
    return PyPI.changes(name, current_version, new_version)

  def all_package_versions(self, name):
    return PyPI.all_package_versions(name)

  def latest_package_version(self, name):
    """ Latest version for package """
    return PyPI.latest_package_version(name)
