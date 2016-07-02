Version 0.2.17
================================================================================

* Python 3 compatible & tests
* Use print()
* Remove use of --download-cache option

Version 0.2.16
--------------------------------------------------------------------------------

* Print warning for single bump failure when no requirements are provided

Version 0.2.15
--------------------------------------------------------------------------------

* Support recursive requirements and ignore other meta flags

Version 0.2.14
--------------------------------------------------------------------------------

* Treat bad requirements as comment so bumping will work
* Better debug log message when failing to get changelog

Version 0.2.13
--------------------------------------------------------------------------------

* Optimize changelog search using github REST endpoint

Version 0.2.12
--------------------------------------------------------------------------------

* Remove transitive dependency parsing with Bump/Require/Pin commit words

Version 0.2.11
--------------------------------------------------------------------------------

* Check bumps to see if they satisfy any requirements so we do not try to bump again

Version 0.2.10
--------------------------------------------------------------------------------

* Return bumps made for BumperDriver.bump()

Version 0.2.9
--------------------------------------------------------------------------------

* Only check existing requirement for one that will be attempted to be bumped

Version 0.2.8
--------------------------------------------------------------------------------

* Only bump once per package and check requirements after all bumps are done to ensure all requirements are met

Version 0.2.7
--------------------------------------------------------------------------------

* Fix bump for package name / no version
* Fix bumping to specific version

Version 0.2.6
--------------------------------------------------------------------------------

* Add should_add to check if a product name should be added to the bumper target

Version 0.2.5
--------------------------------------------------------------------------------

* Return empty changes list instead of None

Version 0.2.4
--------------------------------------------------------------------------------

* Replace existing requirement instead of merging to ensure the proper bump requirement is updated

Version 0.2.3
--------------------------------------------------------------------------------

* Move downgrade changes logic to abstract bumper

Version 0.2.2
--------------------------------------------------------------------------------

* Only reword first/one word when showing bump summary

Version 0.2.1
--------------------------------------------------------------------------------

* Skip requirements parsing for changes when downgrading

Version 0.2.0
--------------------------------------------------------------------------------

* Fully abstract bumper logic

Version 0.1.5
================================================================================

* Fix dependency looping bug

Version 0.1.4
--------------------------------------------------------------------------------

* Better merged message formatting

* Rename --detail to --verbose


Version 0.1.3
--------------------------------------------------------------------------------

* Add option to include changelog details for requirements bumper

* Add long description / url


Version 0.1.2
--------------------------------------------------------------------------------

* Fix new requirement addition and add a tip

Version 0.1.0
--------------------------------------------------------------------------------

* Initial release
