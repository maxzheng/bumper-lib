import argparse
import itertools
import logging
import os
import sys

from bumper.cars import RequirementsBumper, BumpRequirement, BumpAccident
from bumper.utils import parse_requirements

log = logging.getLogger(__name__)


def bump():
  """ CLI entry point to bump requirements in requirements.txt or pinned.txt """

  parser = argparse.ArgumentParser(description=bump.__doc__)
  parser.add_argument('names', nargs='*', help="""
    Only bump dependencies that match the name.
    Name can be a product group name defined in workspace.cfg.
    To bump to a specific version instead of latest, append version to name
    (i.e. requests==1.2.3 or 'requests>=1.2.3'). When > or < is used, be sure to quote.""")
  parser.add_argument('--add', '--require', action='store_true',
                      help='Add the `names` to the requirements file if they don\'t exist.')
  parser.add_argument('--file', help='Requirement file to bump. Defaults to requirements.txt and pinned.txt')
  parser.add_argument('--force', action='store_true', help='Force a bump even when certain bump requirements are not met.')
  parser.add_argument('--verbose', action='store_true', help='Show detailed changes if available')
  parser.add_argument('-n', '--dry-run', action='store_true', help='Perform a dry run without making changes')
  parser.add_argument('--debug', action='store_true', help='Turn on debug mode')

  args = parser.parse_args()
  targets = [args.file] if args.file else ['requirements.txt', 'pinned.txt']

  level = logging.DEBUG if args.debug else logging.INFO
  logging.basicConfig(level=level, format='[%(levelname)s] %(message)s')

  try:
    bumper = BumperDriver(targets, full_throttle=args.force, detail=args.detail, test_drive=args.dry_run)
    bumper.bump(args.names, required=args.add)
  except Exception as e:
    if args.debug:
      raise
    else:
      log.error(e)
      sys.exit(1)


class BumperDriver(object):
  """ Driver that controls the main logic / coordinates the bumps with different bumper models (cars) """

  def __init__(self, targets, bumper_models=None, full_throttle=False, detail=False, test_drive=False):
    """
    :param list targets: List of file paths to bump
    :param list bumper_models: List of bumper classes that implements :class:`bumper.cars.AbstractBumper`
    :param bool full_throttle: Force bumps even when required requirements are not met
    :param bool detail: Generate detailed changes from changelog if possible.
    :param bool test_drive: Perform a dry run
    """
    self.targets = targets
    self.bumper_models = bumper_models or [RequirementsBumper]
    self.full_throttle = full_throttle
    self.detail = detail
    self.test_drive = test_drive

  def bump(self, filter_requirements, required=False, show_summary=True, **kwargs):
    """
    Bump dependency requirements using filter.

    :param list filter_requirements: List of dependency filter requirements.
    :param bool required: Require the filter_requirements to be met (by adding if possible).
    :param bool show_summary: Show summary for each bump made.
    :return: Dict of target file to bump message
    :raise BumpAccident: for any bump errors
    """
    found_targets = [target for target in self.targets if os.path.exists(target)]

    if not found_targets:
      raise BumpAccident('None of the requirement file(s) were found: %s' % ', '.join(self.targets))

    bump_requirements = {}
    if filter_requirements:
      requirements = parse_requirements(filter_requirements)
      bump_requirements = dict([(r.project_name, BumpRequirement(r, required=required)) for r in requirements])

    filter_matched = not bump_requirements
    bumpers = []
    bumps = []

    try:

      for target in found_targets:
        log.debug('Bump target: %s', target)

        target_bumpers = []
        target_bump_requirements = bump_requirements

        while True:
          if not target_bumpers:
            target_bumpers = [model(target, detail=self.detail, test_drive=self.test_drive) for model in self.bumper_models if model.likes(target)]

            if not target_bumpers:
              log.warn('No bumpers found that can bump %s', target)
              continue

            bumpers.extend(target_bumpers)

          new_target_bump_requirements = {}

          for bumper in target_bumpers:
            target_bumps = bumper.bump(target_bump_requirements)
            bumps.extend(target_bumps)

            filter_matched |= bumper.found_bump_requirements or len(target_bumps)

            for new_req in itertools.chain(*[b.requirements for b in target_bumps]):
              if new_req.project_name in bump_requirements:
                old_req = bump_requirements[new_req.project_name]
                if str(old_req) == str(new_req) or new_req.specs and not old_req.specs or\
                   new_req.specs and new_req.specs[0][0] == '==' and (not old_req.specs or old_req.specs[0][0] == '=='):
                  del bump_requirements[new_req.project_name]
              new_target_bump_requirements[new_req.project_name] = new_req

          target_bump_requirements = new_target_bump_requirements

          if target_bump_requirements:
            bump_requirements.update(target_bump_requirements)
          else:
            break

      if not bumpers:
        raise BumpAccident('No bumpers found for %s' % ', '.join(found_targets))

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
              log.warn('User required %s, but bumped to %s', str(req), bump.new_version)

          if not self.full_throttle:
            use_force = 'Use --force for force the bump' if req.required_by else ''

            tip = RequirementsBumper in self.bumper_models and 'RequirementsBumper' not in [b.__class__.__name__ for b in bumpers]

            if tip:
              hint = '\n        Hint: If that is a 3rd party PyPI packages, please create requirements.txt or pinned.txt first.'
            else:
              hint = ''

            raise BumpAccident('Requirement "%s" could not be met so bump can not proceed. %s%s' % (req, use_force, hint))

      if not filter_matched:
        raise BumpAccident('None of the specified dependencies were found in %s' % ', '.join(found_targets))

      if bumps:
        if self.test_drive:
          log.info("Changes that would be made:\n")

        messages = {}

        for bumper in bumpers:
          if bumper.bumps:
            if self.test_drive or show_summary:
              msg = bumper.bump_message(self.test_drive or self.detail)

              if self.test_drive:
                print msg
              else:
                if msg.startswith('Bump '):
                  msg = msg.replace('Bump ', 'Bumped ', 1)
                log.info(msg)

            messages[bumper.target] = bumper.bump_message(True)

        return messages

      else:
        log.info('No need to bump. Everything is up to date!')
        return {}

    except Exception:
      if not self.test_drive and bumps:
        map(lambda b: b.reverse(), bumpers)
      raise
