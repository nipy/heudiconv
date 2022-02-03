# Changelog
All notable changes to this project will be documented (for humans) in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [0.10.0] - 2021-09-16

Various improvements and compatibility/support (dcm2niix, datalad) changes.

### Added

- Add "AcquisitionTime" to the seqinfo ([#487][])
- Add support for saving the Phoenix Report in the sourcedata folder ([#489][])

### Changed

- Python 3.5 EOLed, supported (tested) versions now: 3.6 - 3.9
- In reprorin heuristic, allow for having multiple accessions since now there is
  `-g all` groupping ([#508][])
- For BIDS, produce a singular `scans.json` at the top level, and not one per
  sub/ses (generates too many identical files) ([#507][])


### Fixed

- Compatibility with DataLad 0.15.0. Minimal version is 0.13.0 now.
- Try to open top level BIDS .json files a number of times for adjustment,
  so in the case of competition across parallel processes, they just end up
  with the last one "winning over" ([#523][])
- Don't fail if etelemetry.get_project returns None ([#501][])
- Consistently use `n/a` for age/sex, also handle ?M for months ([#500][])
- To avoid crashing on unrelated derivatives files etc, make `find_files` to
  take list of topdirs (excluding `derivatives/` etc),
  and look for _bold only under sub-* directories ([#496][])
- Ensure bvec/bval files are only created for dwi output ([#491][])

### Removed

- In reproin heuristic, old hardcoded sequence renamings and filters ([#508][])


## [0.9.0] - 2020-12-23

Various improvements and compatibility/support (dcm2niix, datalad,
duecredit) changes.  Major change is placement of output files to the
target output directory during conversion.

### Added

- #454 zenodo referencing in README.rst and support for ducredit for
  heudiconv and reproin heuristic
- #445 more tutorial references in README.md

### Changed

- [#485][] placed files during conversion right away into the target
  directory (with a `_heudiconv???` suffix, renamed into ultimate target
  name later on), which avoids hitting file size limits of /tmp ([#481][]) and
  helped to avoid a regression in dcm2nixx 1.0.20201102
- [#477][] replaced `rec-<magnitude|phase>` with `part-<mag|phase>` now
  hat BIDSsupports the part entity
- [#473][] made default for CogAtlasID to be a TODO URL
- [#459][] made AcquisitionTime used for acq_time scans file field
- [#451][] retained sub-second resolution in scans files
- [#442][] refactored code so there is now heudiconv.main.workflow for
  more convenient use as a Python module

### Fixed

- minimal version of nipype set to 1.2.3 to guarantee correct handling
  of DWI files ([#480][])
- `heudiconvDCM*` temporary directories are removed now ([#462][])
- compatibility with DataLad 0.13 ([#464][])

### Removed

- #443 pathlib as a dependency (we are Python3 only now)


## [0.8.0] - 2020-04-15

### Enhancements

- Centralized saving of .json files.  Indentation of some files could
  change now from previous versions where it could have used `3`
  spaces. Now indentation should be consistently `2` for .json files
  we produce/modify ([#436][]) (note: dcm2niix uses tabs for indentation)
- ReproIn heuristic: support SBRef and phase data ([#387][])
- Set the "TaskName" field in .json sidecar files for multi-echo data
  ([#420][])
- Provide an informative exception if command needs heuristic to be
  specified ([#437][])

### Refactored

- `embed_nifti` was refactored into `embed_dicom_and_nifti_metadata`
  which would no longer create `.nii` file if it does not exist
  already ([#432][])

### Fixed

- Skip datalad-based tests if no datalad available ([#430][])
- Search heuristic file path first so we do not pick up a python
  module if name conflicts ([#434][])

## [0.7.0] - 2020-03-20

### Removed

- Python 2 support/testing

### Enhancement

- `-g` option obtained two new modes: `all` and `custom`. In case of `all`,
  all provided DICOMs will be treated as coming from a single scanning session.
  `custom` instructs to use `.grouping` value (could be a DICOM attribute or
  a callable)provided by the heuristic ([#359][]).
- Stop before reading pixels data while gathering metadata from DICOMs ([#404][])
- reproin heuristic:
  - In addition to original "md5sum of the study_description" `protocols2fix`
    could now have (and applied after md5sum matching ones)
    1). a regular expression searched in study_description,
    2). an empty string as "catch all".
    This features could be used to easily provide remapping into reproin
    naming (documentation is to come to http://github.com/ReproNim/reproin)
    ([#425][])

### Fixed

- Use nan, not None for absent echo value in sorting
- reproin heuristic: case seqinfos into a list to be able to modify from
  overloaded heuristic ([#419][])
- No spurious errors from the logger upon a warning about `etelemetry`
  absence ([#407][])

## [0.6.0] - 2019-12-16

This is largely a bug fix.  Metadata and order of `_key-value` fields in BIDS
could change from the result of converting using previous versions, thus minor
version boost.
14 people contributed to this release -- thanks
[everyone](https://github.com/nipy/heudiconv/graphs/contributors)!

### Enhancement

- Use [etelemetry](https://pypi.org/project/etelemetry) to inform about most
  recent available version of heudiconv. Please set `NO_ET` environment variable
  if you want to disable it ([#369][])
- BIDS:
  - `--bids` flag became an option. It can (optionally) accept `notop` value
    to avoid creation of top level files (`CHANGES`, `dataset_description.json`,
    etc) as a workaround during parallel execution to avoid race conditions etc.
    ([#344][])
  - Generate basic `.json` files with descriptions of the fields for
    `participants.tsv` and `_scans.tsv` files ([#376][])
  - Use `filelock` while writing top level files. Use
    `HEUDICONV_FILELOCK_TIMEOUT` environment to change the default timeout value
    ([#348][])
  - `_PDT2` was added as a suffix for multi-echo (really "multi-modal")
    sequences ([#345][])
- Calls to `dcm2niix` would include full output path to make it easier to
  discern in the logs what file it is working on ([#351][])
- With recent [datalad]() (>= 0.10), created DataLad dataset will use
  `--fake-dates` functionality of DataLad to not leak data conversion dates,
  which might be close to actual data acquisition/patient visit ([#352][])
- Support multi-echo EPI `_phase` data ([#373][] fixes [#368][])
- Log location of a bad .json file to ease troubleshooting ([#379][])
- Add basic pypi classifiers for the package ([#380][])

### Fixed
- Sorting `_scans.tsv` files lacking valid dates field should not cause a crash
  ([#337][])
- Multi-echo files detection based number of echos ([#339][])
- BIDS
  - Use `EchoTimes` from the associated multi-echo files if `EchoNumber` tag is
    missing ([#366][] fixes [#347][])
  - Tolerate empty ContentTime and/or ContentDate in DICOMs ([#372][]) and place
    "n/a" if value is missing ([#390][])
  - Do not crash and store original .json file is "JSON pretification" fails
    ([#342][])
- ReproIn heuristic
  - tolerate WIP prefix on Philips scanners ([#343][])
  - allow for use of `(...)` instead of `{...}` since `{}` are not allowed
    ([#343][])
  - Support pipolar fieldmaps by providing them with `_epi` not `_magnitude`.
    "Loose" BIDS `_key-value` pairs might come now after `_dir-` even if they
    came first before ([#358][] fixes [#357][])
- All heuristics saved under `.heudiconv/` under `heuristic.py` name, to avoid
  discrepancy during reconversion ([#354][] fixes [#353][])
- Do not crash (with TypeError) while trying to sort absent file list ([#360][])
- heudiconv requires nipype >= 1.0.0 ([#364][]) and blacklists `1.2.[12]` ([#375][])

## [0.5.4] - 2019-04-29

This release includes fixes to BIDS multi-echo conversions, the
re-implementation of queuing support (currently just SLURM), as well as
some bugfixes.

Starting today, we will (finally) push versioned releases to DockerHub.
Finally, to more accurately reflect on-going development, the `latest`
tag has been renamed to `unstable`.

### Added
- Readthedocs documentation ([#327][])

### Changed
- Update Docker dcm2niix to v.1.0.20190410 ([#334][])
- Allow usage of `--files` with basic heuristics. This requires
  use of `--subject` flag, and is limited to one subject. ([#293][])

### Deprecated

### Fixed
- Improve support for multiple `--queue-args` ([#328][])
- Fixed an issue where generated BIDS sidecar files were missing additional
  information - treating all conversions as if the `--minmeta` flag was
  used ([#306][])
- Re-enable SLURM queuing support ([#304][])
- BIDS multi-echo support for EPI + T1 images ([#293][])
- Correctly handle the case when `outtype` of heuristic has "dicom"
  before '.nii.gz'. Previously would have lead to absent additional metadata
  extraction etc ([#310][])

### Removed
- `--sbargs` argument was renamed to `--queue-args` ([#304][])

### Security


## [0.5.3] - 2019-01-12

Minor hot bugfix release

### Fixed
- Do not shorten spaces in the dates while pretty printing .json

## [0.5.2] - 2019-01-04

A variety of bugfixes

### Changed
- Reproin heuristic: `__dup` indices would now be assigned incrementally
  individually per each sequence, so there is a chance to properly treat
  associate for multi-file (e.g. `fmap`) sequences
- Reproin heuristic: also split StudyDescription by space not only by ^
- `tests/` moved under `heudiconv/tests` to ease maintenance and facilitate
  testing of an installed heudiconv
- Protocol name will also be accessed from private Siemens
  csa.tProtocolName header field if not present in public one
- nipype>=0.12.0 is required now

### Fixed
- Multiple files produced by dcm2niix are first sorted to guarantee
  correct order e.g. of magnitude files in fieldmaps, which otherwise
  resulted in incorrect according to BIDS ordering of them
- Aggregated top level .json files now would contain only the fields
  with the same values from all scanned files. In prior versions,
  those files were not regenerated after an initial conversion
- Unicode handling in anonimization scripts

## [0.5.1] - 2018-07-05
Bugfix release

### Added
- Video tutorial / updated slides
- Helper to set metadata restrictions correctly
- Usage is now shown when run without arguments
- New fields to Seqinfo
  - series_uid
- Reproin heuristic support for xnat
### Changed
- Dockerfile updated to use `dcm2niix v1.0.20180622`
- Conversion table will be regenerated if heurisic has changed
- Do not touch existing BIDS files
  - events.tsv
  - task JSON
### Fixed
- Python 2.7.8 and older installation
- Support for updated packages
  - `Datalad` 0.10
  - `pydicom` 1.0.2
- Later versions of `pydicom` are prioritized first
- JSON pretty print should not remove spaces
- Phasediff fieldmaps behavior
  - ensure phasediff exists
  - support for single magnitude acquisitions

## [0.5] - 2018-03-01
The first release after major refactoring:

### Changed
- Refactored into a proper `heudiconv` Python module
  - `heuristics` is now a `heudiconv.heuristics` submodule
  - you can specify shipped heuristics by name (e.g. `-f reproin`)
    without providing full path to their files
  - you need to use `--files` (not just positional argument(s)) if not
    using `--dicom_dir_templates` or `--subjects` to point to data files
    or directories with input DICOMs
- `Dockerfile` is generated by [neurodocker](https://github.com/kaczmarj/neurodocker)
- Logging verbosity reduced
- Increased leniency with missing DICOM fields
- `dbic_bids` heuristic renamed into reproin
### Added
- [LICENSE](https://github.com/nipy/heudiconv/blob/master/LICENSE)
  with Apache 2.0 license for the project
- [CHANGELOG.md](https://github.com/nipy/heudiconv/blob/master/CHANGELOG.md)
- [Regression testing](https://github.com/nipy/heudiconv/blob/master/tests/test_regression.py) on real data (using datalad)
- A dedicated [ReproIn](https://github.com/repronim/reproin) project
  with details about ReproIn setup/specification and operation using
  `reproin` heuristic shipped with heudiconv
- [utils/test-compare-two-versions.sh](utils/test-compare-two-versions.sh)
  helper to compare conversions with two different versions of heudiconv
### Removed
- Support for converters other than `dcm2niix`, which is now the default.
  Explicitly specify `-c none` to only prepare conversion specification
  files without performing actual conversion
### Fixed
- Compatibility with Nipype 1.0, PyDicom 1.0, and upcoming DataLad 0.10
- Consistency with converted files permissions
- Ensured subject id for BIDS conversions will be BIDS compliant
- Re-add `seqinfo` fields as column names in generated `dicominfo`
- More robust sanity check of the regex reformatted .json file to avoid
  numeric precision issues
- Many other various issues

## [0.4] - 2017-10-15
A usable release to support [DBIC][] use-case
### Added
- more testing
### Changes
- Dockerfile updates (added pigz, progressed forward [dcm2niix][])
### Fixed
- correct date/time in BIDS `_scans` files
- sort entries in `_scans` by date and then filename

## [0.3] - 2017-07-10
A somewhat working release on the way to support [DBIC][] use-case
### Added
- more tests
- groupping of dicoms by series if provided
- many more features and fixes

## [0.2] - 2016-10-20
An initial release on the way to support [DBIC][] use-case
### Added
- basic Python project assets (`setup.py`, etc)
- basic tests
- [datalad][] support
- dbic_bids heuristic
- `--dbg` command line flag to enter `pdb` environment upon failure
## Fixed
- Better Python3 support
- Better PEP8 compliance

## [0.1] - 2015-09-23

Initial version

---

Just a template for future records:

## [Unreleased] - Date
TODO Summary
### Added
### Changed
### Deprecated
### Fixed
### Removed
### Security

---

## References
[DBIC]: http://dbic.dartmouth.edu
[datalad]: http://datalad.org
[dcm2niix]: https://github.com/rordenlab/dcm2niix
[#301]: https://github.com/nipy/heudiconv/issues/301
[#353]: https://github.com/nipy/heudiconv/issues/353
[#354]: https://github.com/nipy/heudiconv/issues/354
[#357]: https://github.com/nipy/heudiconv/issues/357
[#358]: https://github.com/nipy/heudiconv/issues/358
[#347]: https://github.com/nipy/heudiconv/issues/347
[#366]: https://github.com/nipy/heudiconv/issues/366
[#368]: https://github.com/nipy/heudiconv/issues/368
[#373]: https://github.com/nipy/heudiconv/issues/373
[#485]: https://github.com/nipy/heudiconv/issues/485
[#442]: https://github.com/nipy/heudiconv/issues/442
[#451]: https://github.com/nipy/heudiconv/issues/451
[#459]: https://github.com/nipy/heudiconv/issues/459
[#473]: https://github.com/nipy/heudiconv/issues/473
[#477]: https://github.com/nipy/heudiconv/issues/477
[#293]: https://github.com/nipy/heudiconv/issues/293
[#304]: https://github.com/nipy/heudiconv/issues/304
[#306]: https://github.com/nipy/heudiconv/issues/306
[#310]: https://github.com/nipy/heudiconv/issues/310
[#327]: https://github.com/nipy/heudiconv/issues/327
[#328]: https://github.com/nipy/heudiconv/issues/328
[#334]: https://github.com/nipy/heudiconv/issues/334
[#337]: https://github.com/nipy/heudiconv/issues/337
[#339]: https://github.com/nipy/heudiconv/issues/339
[#342]: https://github.com/nipy/heudiconv/issues/342
[#343]: https://github.com/nipy/heudiconv/issues/343
[#344]: https://github.com/nipy/heudiconv/issues/344
[#345]: https://github.com/nipy/heudiconv/issues/345
[#348]: https://github.com/nipy/heudiconv/issues/348
[#351]: https://github.com/nipy/heudiconv/issues/351
[#352]: https://github.com/nipy/heudiconv/issues/352
[#359]: https://github.com/nipy/heudiconv/issues/359
[#360]: https://github.com/nipy/heudiconv/issues/360
[#364]: https://github.com/nipy/heudiconv/issues/364
[#369]: https://github.com/nipy/heudiconv/issues/369
[#372]: https://github.com/nipy/heudiconv/issues/372
[#375]: https://github.com/nipy/heudiconv/issues/375
[#376]: https://github.com/nipy/heudiconv/issues/376
[#379]: https://github.com/nipy/heudiconv/issues/379
[#380]: https://github.com/nipy/heudiconv/issues/380
[#387]: https://github.com/nipy/heudiconv/issues/387
[#390]: https://github.com/nipy/heudiconv/issues/390
[#404]: https://github.com/nipy/heudiconv/issues/404
[#407]: https://github.com/nipy/heudiconv/issues/407
[#419]: https://github.com/nipy/heudiconv/issues/419
[#420]: https://github.com/nipy/heudiconv/issues/420
[#425]: https://github.com/nipy/heudiconv/issues/425
[#430]: https://github.com/nipy/heudiconv/issues/430
[#432]: https://github.com/nipy/heudiconv/issues/432
[#434]: https://github.com/nipy/heudiconv/issues/434
[#436]: https://github.com/nipy/heudiconv/issues/436
[#437]: https://github.com/nipy/heudiconv/issues/437
[#462]: https://github.com/nipy/heudiconv/issues/462
[#464]: https://github.com/nipy/heudiconv/issues/464
[#480]: https://github.com/nipy/heudiconv/issues/480
[#481]: https://github.com/nipy/heudiconv/issues/481
[#487]: https://github.com/nipy/heudiconv/issues/487
[#489]: https://github.com/nipy/heudiconv/issues/489
[#491]: https://github.com/nipy/heudiconv/issues/491
[#496]: https://github.com/nipy/heudiconv/issues/496
[#500]: https://github.com/nipy/heudiconv/issues/500
[#501]: https://github.com/nipy/heudiconv/issues/501
[#507]: https://github.com/nipy/heudiconv/issues/507
[#508]: https://github.com/nipy/heudiconv/issues/508
[#523]: https://github.com/nipy/heudiconv/issues/523
