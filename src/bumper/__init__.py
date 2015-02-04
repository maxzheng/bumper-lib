import itertools
import logging
import os
import sys

from bumper.cars import RequirementsBumper, BumpRequirement
from bumper.utils import parse_requirements

log = logging.getLogger(__name__)


class BumpAccident(Exception):
  """ Exception for any bump errors """
  pass


class BumperDriver(object):
  def __init__(self, targets, bumper_models=None, full_throttle=False, test_drive=False):
    """
    :param list targets: List of file paths to bump
    :param list bumper_models: List of bumper classes that implements :class:`bumper.cars.AbstractBumper`
    :param bool full_throttle: Force bumps even when required requirements are not met
    :param bool test_drive: Perform a dry run
    """
    self.targets = targets
    self.bumper_models = bumper_models or [RequirementsBumper]
    self.full_throttle = full_throttle
    self.test_drive = test_drive

  def bump(self, filter_requirements, required=False, **kwargs):
    """
    Bump dependency requirements using filter.

    :param list filter_requirements: List of dependency filter requirements.
    :param bool reuired: Require the filter_requirements to be met (by adding if possible).
    :return: Dict of target file to bump message
    :raise BumpAccident: for any bump errors
    """
    found_targets = [target for target in self.targets if os.path.exists(target)]

    if not found_targets:
      raise BumpAccident('None of the requirement file(s) were found: %s' % ', '.join(self.targets))

    bump_requirements = {}
    if filter_requirements:
      log.info('Only bumping: %s', ' '.join(filter_requirements))
      requirements = parse_requirements(filter_requirements)
      bump_requirements = dict([(r.project_name, BumpRequirement(r, required=required)) for r in requirements])

    filter_matched = False
    bumpers = []
    bumps = []

    for target in found_targets:
      target_bumpers = []
      target_bump_requirements = bump_requirements

      while target_bump_requirements:
        if not target_bumpers:
          target_bumpers = [model(target, test_drive=self.test_drive) for model in self.bumper_models if model.likes(target)]

          if not target_bumpers:
            log.warn('No bumpers found that can bump %s', target)
            continue

          bumpers.extend(target_bumpers)

        new_target_bump_requirements = []

        for bumper in target_bumpers:
          target_bumps = bumper.bump(target_bump_requirements)
          bumps.extend(target_bumps)

          filter_matched |= bumper.found_bump_requirements or len(target_bumps)

          for new_req in itertools.chain(*[b.requirements for b in target_bumps]):
            if new_req.project_name in bump_requirements:
              log.warn('%s requires %s, but there is already an existing requirement %s, so it will be ignored.',
                       new_req.bump.name, new_req, bump_requirements[new_req.project_name])
            else:
              new_target_bump_requirements.append(new_req)

        target_bump_requirements = new_target_bump_requirements

        if target_bump_requirements:
          bump_requirements.update(dict((r.project_name, r) for r in target_bump_requirements))

    if not bumpers:
      raise BumpAccident('No bumpers found for %s', ', '.join(found_targets))

    required_bumps = filter(lambda r: r.required, bump_requirements.values())

    if required_bumps:
      bumped = dict([b.name, b] for b in bumps)

      for req in required_bumps:
        if req.project_name in bumped:
          bump = bumped[req.project_name]

          if bump.satisfies(req):
            continue

          if req.required_by:
            log.warn('Changes in %s requires %s, but %s is at %s.' % (req.required_by.name, str(req), req.project_name, bump.new_version))
          else:
            log.warn('User required %s, but bump bumped to %s', str(req), bump.new_version)

        if not self.full_throttle:
          if not self.test_drive and bumps:
            map(lambda b: b.reverse(), bumpers)
          use_force = 'Use --force for force the bump' if req.required_by else ''
          raise BumpAccident('Requirement "%s" could not be met so bump can not proceed. %s' % (req, use_force))

    if not filter_matched:
      raise BumpAccident('None of the specified dependencies were found in %s' % ', '.join(found_targets))

    if bumps:
      if self.test_drive:
        log.info("Changes that would be made:\n")

      messages = {}

      for bumper in bumpers:
        if bumper.bumps:
          print bumper.bump_message(self.test_drive)
          print
          messages[bumper.target] = bumper.bump_message(True)

      return messages

    else:
      log.info('No need to bump. Everything is up to date!')
      return {}
