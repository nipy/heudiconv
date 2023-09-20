# v1.0.0 (Wed Sep 20 2023)

#### 💥 Breaking Change

- [gh-actions](deps): Bump actions/checkout from 3 to 4 [#703](https://github.com/nipy/heudiconv/pull/703) ([@dependabot[bot]](https://github.com/dependabot[bot]))

#### 🚀 Enhancement

- Fix inconsistent behavior of existing session when using -d compared to --files option: raise an AssertionError instead of just a warning [#682](https://github.com/nipy/heudiconv/pull/682) ([@neurorepro](https://github.com/neurorepro))

#### 🐛 Bug Fix

- Various tiny enhancements flake etc demanded [#702](https://github.com/nipy/heudiconv/pull/702) ([@yarikoptic](https://github.com/yarikoptic))
- Boost claimed BIDS version to 1.8.0 from 1.4.1 [#699](https://github.com/nipy/heudiconv/pull/699) ([@yarikoptic](https://github.com/yarikoptic))
- Point to Courtois-neuromod heuristic [#702](https://github.com/nipy/heudiconv/pull/702) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Add codespell to lint tox env [#706](https://github.com/nipy/heudiconv/pull/706) ([@yarikoptic](https://github.com/yarikoptic))
- test-compare-two-versions.sh: also ignore differences in HeudiconvVersion field in jsons since we have it there now [#685](https://github.com/nipy/heudiconv/pull/685) ([@yarikoptic](https://github.com/yarikoptic))

#### 📝 Documentation

- Add description of placeholders which could be used in the produced templates [#681](https://github.com/nipy/heudiconv/pull/681) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- [@dependabot[bot]](https://github.com/dependabot[bot])
- Michael ([@neurorepro](https://github.com/neurorepro))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.13.1 (Tue May 23 2023)

#### 🐛 Bug Fix

- Make .subsecond optional in BIDS/DICOM datetime entries [#675](https://github.com/nipy/heudiconv/pull/675) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- [gh-actions](deps): Bump codespell-project/actions-codespell from 1 to 2 [#677](https://github.com/nipy/heudiconv/pull/677) ([@dependabot[bot]](https://github.com/dependabot[bot]))
- Replace (no longer used) Travis badge with GitHub action one (for test) [#677](https://github.com/nipy/heudiconv/pull/677) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- [@dependabot[bot]](https://github.com/dependabot[bot])
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.13.0 (Mon May 08 2023)

#### 🚀 Enhancement

- Add type annotations [#656](https://github.com/nipy/heudiconv/pull/656) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))
- ENH: Support extracting DICOMs from ZIP files (and possibly other archives) by switching to use shutil.unpack_archive instead of tarfile module functionality [#471](https://github.com/nipy/heudiconv/pull/471) ([@HippocampusGirl](https://github.com/HippocampusGirl) [@psadil](https://github.com/psadil))
- Allow filling of acq_time when AcquisitionDate AcquisitionTime missing [#614](https://github.com/nipy/heudiconv/pull/614) ([@psadil](https://github.com/psadil))

#### 🐛 Bug Fix

- BF(?): make _setter images be taken as scouts - only DICOMs are saved [#570](https://github.com/nipy/heudiconv/pull/570) ([@yarikoptic](https://github.com/yarikoptic))
- Adjust .mailmap to account for mapping various folks with multiple emails so that git shortlog -sn -e provides entries without duplicates [#570](https://github.com/nipy/heudiconv/pull/570) ([@yarikoptic](https://github.com/yarikoptic))
- Make an `embed_dicom_and_nifti_metadata()` annotation work on Python 3.7 [#673](https://github.com/nipy/heudiconv/pull/673) ([@jwodder](https://github.com/jwodder))
- Merge branch 'feature_dicom_compresslevel' [#673](https://github.com/nipy/heudiconv/pull/673) ([@yarikoptic](https://github.com/yarikoptic))
- Update heudiconv/dicoms.py [#669](https://github.com/nipy/heudiconv/pull/669) ([@octomike](https://github.com/octomike))
- Don't call `logging.basicConfig()` in `__init__.py` [#659](https://github.com/nipy/heudiconv/pull/659) ([@jwodder](https://github.com/jwodder))

#### ⚠️ Pushed to `master`

- Mailmapping more contributors ([@yarikoptic](https://github.com/yarikoptic))
- Adjust comment and remove trailing space flipping linting ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Declare `custom_grouping` return type instead of casting [#671](https://github.com/nipy/heudiconv/pull/671) ([@jwodder](https://github.com/jwodder))
- Use `pydicom.dcmread()` instead of `pydicom.read_file()` [#668](https://github.com/nipy/heudiconv/pull/668) ([@jwodder](https://github.com/jwodder))
- Add `sample_nifti.json` to `.gitignore` [#663](https://github.com/nipy/heudiconv/pull/663) ([@jwodder](https://github.com/jwodder))
- Write command arguments as lists of strings instead of splitting strings on whitespace [#664](https://github.com/nipy/heudiconv/pull/664) ([@jwodder](https://github.com/jwodder))
- Add & apply pre-commit and lint job [#658](https://github.com/nipy/heudiconv/pull/658) ([@jwodder](https://github.com/jwodder))
- Fix some strings with \ (make them raw or double-\), improve pytest config: move to tox.ini, make unknown warnings into errors [#660](https://github.com/nipy/heudiconv/pull/660) ([@jwodder](https://github.com/jwodder))
- Replace py.path with pathlib [#654](https://github.com/nipy/heudiconv/pull/654) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Make `test_private_csa_header` test write to temp dir [#666](https://github.com/nipy/heudiconv/pull/666) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Replace third-party `mock` library with stdlib's `unittest.mock` [#661](https://github.com/nipy/heudiconv/pull/661) ([@jwodder](https://github.com/jwodder))
- Remove kludgy support for older versions of pydicom and dcmstack [#662](https://github.com/nipy/heudiconv/pull/662) ([@jwodder](https://github.com/jwodder))
- Remove use of `six` [#655](https://github.com/nipy/heudiconv/pull/655) ([@jwodder](https://github.com/jwodder))

#### Authors: 5

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Lea Waller ([@HippocampusGirl](https://github.com/HippocampusGirl))
- Michael ([@octomike](https://github.com/octomike))
- Patrick Sadil ([@psadil](https://github.com/psadil))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.12.2 (Tue Mar 14 2023)

#### 🏠 Internal

- [DATALAD RUNCMD] produce updated dockerfile [#652](https://github.com/nipy/heudiconv/pull/652) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.12.1 (Tue Mar 14 2023)

#### 🐛 Bug Fix

- Re-add explicit instructions to install dcm2niix "manually" and remove it from install_requires [#651](https://github.com/nipy/heudiconv/pull/651) ([@yarikoptic](https://github.com/yarikoptic))

#### 📝 Documentation

- Contributing guide. [#641](https://github.com/nipy/heudiconv/pull/641) ([@TheChymera](https://github.com/TheChymera))
- Reword and correct punctuation on installation.rst [#643](https://github.com/nipy/heudiconv/pull/643) ([@yarikoptic](https://github.com/yarikoptic) [@candleindark](https://github.com/candleindark))

#### Authors: 3

- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- Isaac To ([@candleindark](https://github.com/candleindark))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.12.0 (Tue Feb 21 2023)

#### 🚀 Enhancement

- strip non-alphanumeric from session ids too [#647](https://github.com/nipy/heudiconv/pull/647) ([@keithcallenberg](https://github.com/keithcallenberg) [@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Docker images: tag also as "unstable", strip "v" prefix, and avoid building in non-release workflow for releases. [#642](https://github.com/nipy/heudiconv/pull/642) ([@yarikoptic](https://github.com/yarikoptic))
- add install link to README [#640](https://github.com/nipy/heudiconv/pull/640) ([@asmacdo](https://github.com/asmacdo))
- Setting git author and email in test environment [#631](https://github.com/nipy/heudiconv/pull/631) ([@TheChymera](https://github.com/TheChymera))
- Duecredit dcm2niix [#622](https://github.com/nipy/heudiconv/pull/622) ([@yarikoptic](https://github.com/yarikoptic))
- Do not issue warning if cannot parse _task entity [#621](https://github.com/nipy/heudiconv/pull/621) ([@yarikoptic](https://github.com/yarikoptic))
- Provide codespell config and workflow [#619](https://github.com/nipy/heudiconv/pull/619) ([@yarikoptic](https://github.com/yarikoptic))
- BF: Use .get in group_dicoms_into_seqinfos to not puke if SeriesDescription is missing [#622](https://github.com/nipy/heudiconv/pull/622) ([@yarikoptic](https://github.com/yarikoptic))
- DOC: do provide short version for sphinx [#609](https://github.com/nipy/heudiconv/pull/609) ([@yarikoptic](https://github.com/yarikoptic))

#### ⚠️ Pushed to `master`

- DOC: add clarification on where docs/requirements.txt should be "installed" from ([@yarikoptic](https://github.com/yarikoptic))
- fix minor typo ([@yarikoptic](https://github.com/yarikoptic))
- DOC: fixed the comment. Original was copy/pasted from DataLad ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- dcm2niix explicitly noted as a (PyPI) dependency and removed from being installed via apt-get etc [#628](https://github.com/nipy/heudiconv/pull/628) ([@TheChymera](https://github.com/TheChymera) [@yarikoptic](https://github.com/yarikoptic))

#### 📝 Documentation

- Reword number of intended ideas in README.rst [#639](https://github.com/nipy/heudiconv/pull/639) ([@candleindark](https://github.com/candleindark))
- Add a bash anon-cmd to be used to incrementally anonymize sids [#615](https://github.com/nipy/heudiconv/pull/615) ([@yarikoptic](https://github.com/yarikoptic))
- Reword and correct punctuation on usage.rst [#644](https://github.com/nipy/heudiconv/pull/644) ([@candleindark](https://github.com/candleindark) [@yarikoptic](https://github.com/yarikoptic))
- Clarify the infotodict function [#645](https://github.com/nipy/heudiconv/pull/645) ([@yarikoptic](https://github.com/yarikoptic))
- Added distribution badges [#632](https://github.com/nipy/heudiconv/pull/632) ([@TheChymera](https://github.com/TheChymera))
- Capitalize sentences and end sentences with period [#629](https://github.com/nipy/heudiconv/pull/629) ([@candleindark](https://github.com/candleindark))
- Tune up .mailmap to harmonize Pablo, Dae and Mathias [#629](https://github.com/nipy/heudiconv/pull/629) ([@yarikoptic](https://github.com/yarikoptic))
- Add HOWTO 101 section, with references to ReproIn to README.rst [#623](https://github.com/nipy/heudiconv/pull/623) ([@yarikoptic](https://github.com/yarikoptic))
- minor fix -- Fix use of code:: directive [#623](https://github.com/nipy/heudiconv/pull/623) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- Add 3.11 to be tested etc [#635](https://github.com/nipy/heudiconv/pull/635) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 5

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Horea Christian ([@TheChymera](https://github.com/TheChymera))
- Isaac To ([@candleindark](https://github.com/candleindark))
- Keith Callenberg ([@keithcallenberg](https://github.com/keithcallenberg))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.11.6 (Thu Nov 03 2022)

#### 🏠 Internal

- Delete .dockerignore [#607](https://github.com/nipy/heudiconv/pull/607) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- DOC: Various fixes to make RTD build the docs again [#608](https://github.com/nipy/heudiconv/pull/608) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.11.5 (Thu Nov 03 2022)

#### 🐛 Bug Fix

- Fix certificate issue as indicated in #595 [#597](https://github.com/nipy/heudiconv/pull/597) ([@neurorepro](https://github.com/neurorepro))
- BF docker build: use python3.9 (not 3.7 which gets upgraded to 3.9) and newer dcm2niix [#596](https://github.com/nipy/heudiconv/pull/596) ([@yarikoptic](https://github.com/yarikoptic))
- Fixup miniconda spec for neurodocker so it produces dockerfile now [#596](https://github.com/nipy/heudiconv/pull/596) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Update GitHub Actions action versions [#601](https://github.com/nipy/heudiconv/pull/601) ([@jwodder](https://github.com/jwodder))
- Set action step outputs via $GITHUB_OUTPUT [#600](https://github.com/nipy/heudiconv/pull/600) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- DOC: codespell fix a few typos in code comments [#605](https://github.com/nipy/heudiconv/pull/605) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Michael ([@neurorepro](https://github.com/neurorepro))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.11.4 (Thu Sep 29 2022)

#### 🐛 Bug Fix

- install dcmstack straight from github until it is released [#593](https://github.com/nipy/heudiconv/pull/593) ([@yarikoptic](https://github.com/yarikoptic))
- DOC: provide rudimentary How to contribute section in README.rst ([@yarikoptic](https://github.com/yarikoptic))

#### ⚠️ Pushed to `master`

- Check out a full clone when testing ([@jwodder](https://github.com/jwodder))
- Convert Travis workflow to GitHub Actions ([@jwodder](https://github.com/jwodder))
- BF(docker): replace old -tipsy with -y -all for conda clean as neurodocker does now ([@yarikoptic](https://github.com/yarikoptic))
- adjusted script for neurodocker although it does not work ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- 0.9 of dcmstack was released, no need for github version [#594](https://github.com/nipy/heudiconv/pull/594) ([@yarikoptic](https://github.com/yarikoptic))
- Minor face-lifts to ReproIn: align doc and code better to BIDS terms, address deprecation warnings etc [#569](https://github.com/nipy/heudiconv/pull/569) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.11.3 (Thu May 12 2022)

#### 🏠 Internal

- BF: add recently tests data missing from distribution [#567](https://github.com/nipy/heudiconv/pull/567) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.11.2 (Thu May 12 2022)

#### 🏠 Internal

- Make versioningit write version to file; make setup.py read version as fallback [#566](https://github.com/nipy/heudiconv/pull/566) ([@jwodder](https://github.com/jwodder))
- BF: add fetch-depth: 0 to get all tags into docker builds of master [#566](https://github.com/nipy/heudiconv/pull/566) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.11.1 (Tue May 10 2022)

#### 🏠 Internal

- Remove .git/ from .dockerignore so that versioning works while building docker image [#564](https://github.com/nipy/heudiconv/pull/564) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.11.0 (Tue May 10 2022)

#### 🚀 Enhancement

- RF: drop Python 3.6 (EOLed), fix dcm2niix version in neurodocker script [#555](https://github.com/nipy/heudiconv/pull/555) ([@yarikoptic](https://github.com/yarikoptic))
- ENH: Adds populate_intended_for for fmaps [#482](https://github.com/nipy/heudiconv/pull/482) ([@pvelasco](https://github.com/pvelasco) [@yarikoptic](https://github.com/yarikoptic) bids@dbic.dartmouth.edu [@neurorepro](https://github.com/neurorepro))

#### 🐛 Bug Fix

- bids_ME heuristic: add test for the dataset that raised #541, add support for MEGRE [#547](https://github.com/nipy/heudiconv/pull/547) ([@pvelasco](https://github.com/pvelasco) [@yarikoptic](https://github.com/yarikoptic))
- reproin heuristic: specify POPULATE_INTENDED_FOR_OPTS [#546](https://github.com/nipy/heudiconv/pull/546) ([@yarikoptic](https://github.com/yarikoptic))
- FIX: Convert sets to lists for filename updaters [#461](https://github.com/nipy/heudiconv/pull/461) ([@tsalo](https://github.com/tsalo))
- Added new infofilestyle compatible with BIDS [#12](https://github.com/nipy/heudiconv/pull/12) ([@chrisgorgo](https://github.com/chrisgorgo))
- try a simple fix for wrongly ordered files in tar file [#535](https://github.com/nipy/heudiconv/pull/535) ([@bpinsard](https://github.com/bpinsard))
- BF: Fix the order of the 'echo' entity in the filename [#542](https://github.com/nipy/heudiconv/pull/542) ([@pvelasco](https://github.com/pvelasco))
- ENH: add HeudiconvVersion to sidecar .json files [#529](https://github.com/nipy/heudiconv/pull/529) ([@yarikoptic](https://github.com/yarikoptic))
- BF (TST): make anonymize_script actually output anything and map deterministically [#511](https://github.com/nipy/heudiconv/pull/511) ([@yarikoptic](https://github.com/yarikoptic))
- Rename DICOMCONVERT_README.md to README.md [#4](https://github.com/nipy/heudiconv/pull/4) ([@satra](https://github.com/satra))

#### ⚠️ Pushed to `master`

- Dockerfile - use bullseye for the base and fresh dcm2niix ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Run codespell on some obvious typos [#563](https://github.com/nipy/heudiconv/pull/563) ([@yarikoptic](https://github.com/yarikoptic))
- Set up auto [#558](https://github.com/nipy/heudiconv/pull/558) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- BF(TST): use caplog to control logging level, use python3 in shebang [#553](https://github.com/nipy/heudiconv/pull/553) ([@yarikoptic](https://github.com/yarikoptic))
- BF(TST): use caplog instead of capfd for testing if we log a warning [#534](https://github.com/nipy/heudiconv/pull/534) ([@yarikoptic](https://github.com/yarikoptic))
- Travis - Use bionic for the base [#533](https://github.com/nipy/heudiconv/pull/533) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 9

- Basile ([@bpinsard](https://github.com/bpinsard))
- Chris Gorgolewski ([@chrisgorgo](https://github.com/chrisgorgo))
- DBIC BIDS Team (bids@dbic.dartmouth.edu)
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Michael ([@neurorepro](https://github.com/neurorepro))
- Pablo Velasco ([@pvelasco](https://github.com/pvelasco))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Taylor Salo ([@tsalo](https://github.com/tsalo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# [0.10.0] - 2021-09-16

Various improvements and compatibility/support (dcm2niix, datalad) changes.

## Added

- Add "AcquisitionTime" to the seqinfo ([#487][])
- Add support for saving the Phoenix Report in the sourcedata folder ([#489][])

## Changed

- Python 3.5 EOLed, supported (tested) versions now: 3.6 - 3.9
- In reprorin heuristic, allow for having multiple accessions since now there is
  `-g all` grouping ([#508][])
- For BIDS, produce a singular `scans.json` at the top level, and not one per
  sub/ses (generates too many identical files) ([#507][])


## Fixed

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

## Removed

- In reproin heuristic, old hardcoded sequence renamings and filters ([#508][])


# [0.9.0] - 2020-12-23

Various improvements and compatibility/support (dcm2niix, datalad,
duecredit) changes.  Major change is placement of output files to the
target output directory during conversion.

## Added

- #454 zenodo referencing in README.rst and support for ducredit for
  heudiconv and reproin heuristic
- #445 more tutorial references in README.md

## Changed

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

## Fixed

- minimal version of nipype set to 1.2.3 to guarantee correct handling
  of DWI files ([#480][])
- `heudiconvDCM*` temporary directories are removed now ([#462][])
- compatibility with DataLad 0.13 ([#464][])

## Removed

- #443 pathlib as a dependency (we are Python3 only now)


# [0.8.0] - 2020-04-15

## Enhancements

- Centralized saving of .json files.  Indentation of some files could
  change now from previous versions where it could have used `3`
  spaces. Now indentation should be consistently `2` for .json files
  we produce/modify ([#436][]) (note: dcm2niix uses tabs for indentation)
- ReproIn heuristic: support SBRef and phase data ([#387][])
- Set the "TaskName" field in .json sidecar files for multi-echo data
  ([#420][])
- Provide an informative exception if command needs heuristic to be
  specified ([#437][])

## Refactored

- `embed_nifti` was refactored into `embed_dicom_and_nifti_metadata`
  which would no longer create `.nii` file if it does not exist
  already ([#432][])

## Fixed

- Skip datalad-based tests if no datalad available ([#430][])
- Search heuristic file path first so we do not pick up a python
  module if name conflicts ([#434][])

# [0.7.0] - 2020-03-20

## Removed

- Python 2 support/testing

## Enhancement

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

## Fixed

- Use nan, not None for absent echo value in sorting
- reproin heuristic: case seqinfos into a list to be able to modify from
  overloaded heuristic ([#419][])
- No spurious errors from the logger upon a warning about `etelemetry`
  absence ([#407][])

# [0.6.0] - 2019-12-16

This is largely a bug fix.  Metadata and order of `_key-value` fields in BIDS
could change from the result of converting using previous versions, thus minor
version boost.
14 people contributed to this release -- thanks
[everyone](https://github.com/nipy/heudiconv/graphs/contributors)!

## Enhancement

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

## Fixed
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

# [0.5.4] - 2019-04-29

This release includes fixes to BIDS multi-echo conversions, the
re-implementation of queuing support (currently just SLURM), as well as
some bugfixes.

Starting today, we will (finally) push versioned releases to DockerHub.
Finally, to more accurately reflect on-going development, the `latest`
tag has been renamed to `unstable`.

## Added
- Readthedocs documentation ([#327][])

## Changed
- Update Docker dcm2niix to v.1.0.20190410 ([#334][])
- Allow usage of `--files` with basic heuristics. This requires
  use of `--subject` flag, and is limited to one subject. ([#293][])

## Deprecated

## Fixed
- Improve support for multiple `--queue-args` ([#328][])
- Fixed an issue where generated BIDS sidecar files were missing additional
  information - treating all conversions as if the `--minmeta` flag was
  used ([#306][])
- Re-enable SLURM queuing support ([#304][])
- BIDS multi-echo support for EPI + T1 images ([#293][])
- Correctly handle the case when `outtype` of heuristic has "dicom"
  before '.nii.gz'. Previously would have lead to absent additional metadata
  extraction etc ([#310][])

## Removed
- `--sbargs` argument was renamed to `--queue-args` ([#304][])

## Security


# [0.5.3] - 2019-01-12

Minor hot bugfix release

## Fixed
- Do not shorten spaces in the dates while pretty printing .json

# [0.5.2] - 2019-01-04

A variety of bugfixes

## Changed
- Reproin heuristic: `__dup` indices would now be assigned incrementally
  individually per each sequence, so there is a chance to properly treat
  associate for multi-file (e.g. `fmap`) sequences
- Reproin heuristic: also split StudyDescription by space not only by ^
- `tests/` moved under `heudiconv/tests` to ease maintenance and facilitate
  testing of an installed heudiconv
- Protocol name will also be accessed from private Siemens
  csa.tProtocolName header field if not present in public one
- nipype>=0.12.0 is required now

## Fixed
- Multiple files produced by dcm2niix are first sorted to guarantee
  correct order e.g. of magnitude files in fieldmaps, which otherwise
  resulted in incorrect according to BIDS ordering of them
- Aggregated top level .json files now would contain only the fields
  with the same values from all scanned files. In prior versions,
  those files were not regenerated after an initial conversion
- Unicode handling in anonimization scripts

# [0.5.1] - 2018-07-05
Bugfix release

## Added
- Video tutorial / updated slides
- Helper to set metadata restrictions correctly
- Usage is now shown when run without arguments
- New fields to Seqinfo
  - series_uid
- Reproin heuristic support for xnat
## Changed
- Dockerfile updated to use `dcm2niix v1.0.20180622`
- Conversion table will be regenerated if heurisic has changed
- Do not touch existing BIDS files
  - events.tsv
  - task JSON
## Fixed
- Python 2.7.8 and older installation
- Support for updated packages
  - `Datalad` 0.10
  - `pydicom` 1.0.2
- Later versions of `pydicom` are prioritized first
- JSON pretty print should not remove spaces
- Phasediff fieldmaps behavior
  - ensure phasediff exists
  - support for single magnitude acquisitions

# [0.5] - 2018-03-01
The first release after major refactoring:

## Changed
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
## Added
- [LICENSE](https://github.com/nipy/heudiconv/blob/master/LICENSE)
  with Apache 2.0 license for the project
- [CHANGELOG.md](https://github.com/nipy/heudiconv/blob/master/CHANGELOG.md)
- [Regression testing](https://github.com/nipy/heudiconv/blob/master/tests/test_regression.py) on real data (using datalad)
- A dedicated [ReproIn](https://github.com/repronim/reproin) project
  with details about ReproIn setup/specification and operation using
  `reproin` heuristic shipped with heudiconv
- [utils/test-compare-two-versions.sh](utils/test-compare-two-versions.sh)
  helper to compare conversions with two different versions of heudiconv
## Removed
- Support for converters other than `dcm2niix`, which is now the default.
  Explicitly specify `-c none` to only prepare conversion specification
  files without performing actual conversion
## Fixed
- Compatibility with Nipype 1.0, PyDicom 1.0, and upcoming DataLad 0.10
- Consistency with converted files permissions
- Ensured subject id for BIDS conversions will be BIDS compliant
- Re-add `seqinfo` fields as column names in generated `dicominfo`
- More robust sanity check of the regex reformatted .json file to avoid
  numeric precision issues
- Many other various issues

# [0.4] - 2017-10-15
A usable release to support [DBIC][] use-case
## Added
- more testing
## Changes
- Dockerfile updates (added pigz, progressed forward [dcm2niix][])
## Fixed
- correct date/time in BIDS `_scans` files
- sort entries in `_scans` by date and then filename

# [0.3] - 2017-07-10
A somewhat working release on the way to support [DBIC][] use-case
## Added
- more tests
- grouping of dicoms by series if provided
- many more features and fixes

# [0.2] - 2016-10-20
An initial release on the way to support [DBIC][] use-case
## Added
- basic Python project assets (`setup.py`, etc)
- basic tests
- [datalad][] support
- dbic_bids heuristic
- `--dbg` command line flag to enter `pdb` environment upon failure
# Fixed
- Better Python3 support
- Better PEP8 compliance

# [0.1] - 2015-09-23

Initial version

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
