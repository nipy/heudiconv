---
title: 'HeuDiConv — flexible DICOM conversion into structured directory layouts'
tags:
  - Python
  - neuroscience
  - standardization
  - DICOM
  - BIDS
  - open science
  - FOSS
authors:
  - name: TODO
    orcid: 0000-0000-0000-0000
    equal-contrib: true
    affiliation: "1, 2" # (Multiple affiliations must be quoted)
  - name: Author Without ORCID
    equal-contrib: true # (This is how you can denote equal contributions between multiple authors)
    affiliation: 2
  - name: Author with no affiliation
    corresponding: true # (This is how to denote the corresponding author)
    affiliation: 3
affiliations:
 - name: TODO
   index: 1
 - name: Institution Name, Country
   index: 2
 - name: Independent Researcher, Country
   index: 3
date: 2023-01-31
bibliography: paper.bib

---

# Summary

In order to support efficient processing, data must be formatted according to standards prevalent in the field, and widely supported among actively developed analysis tools.
The Brain Imaging Data Structure (BIDS) [@GAC+16] is an open standard designed for computational accessibility, operator legibility, and a wide and easily extendable scope of modalities — and is consequently used by numerous analysis and processing tools as the preferred input format.
HeuDiConv (Heuristic DICOM Converter) enables flexible and efficient conversion of spatially reconstructed neuroimaging data from the DICOM format (quasi-ubiquitous in biomedical image acquisition systems, particularly in clinical settings) to BIDS, as well as other file layouts.
HeuDiConv provides a multi-stage operator input workflow (discovery, manual tuning, conversion) where manual tuning step is optional and thus the entire conversion can be seamlessly integrated into a data processing pipeline.
HeuDiConv is written in Python, and supports the DICOM specification for input parsing, and the BIDS specification for output construction.
The support for these standards is extensive, and HeuDiConv can handle complex organization scenarios such as arise for specific data types (e.g., multi-echo sequences, or single-band reference volumes).
In addition to generating valid BIDS outputs, additional support is offered for custom output layouts.
This is obtained via a set of built-in fully functional or example heuristics expressed as simple Python functions.
Those heuristics could be taken as a template or as a base for developing custom heuristics, thus providing full flexibility and maintaining user accessibility.
HeuDiConv further integrates with DataLad [@datalad], and can automatically prepare hierarchies of DataLad datasets with optional obfuscation of sensitive data and metadata, including obfuscating patient visit timestamps in the git version control system.
As a result, given its extensibility, large modality support, and integration with advanced data management technologies, HeuDiConv has become a mainstay in numerous neuroimaging workflows, and constitutes a powerful and highly adaptable tool of potential interest to large swathes of the neuroimaging community.


# Statement of Need

Neuroimaging is an empirical research area which relies heavily on efficient data acquisition, harmonization, and processing.
Neuroimaging data sourced from medical imaging equipment, and in particular magnetic resonance imaging (MRI) scanners, can be exported in numerous formats, among which DICOM (Digital Imaging and Communications in Medicine) is most prominent.
DICOM data are often transmitted to PACS (Picture Archiving and Communication Systems) servers for archiving or further processing.
Unlike in clinical settings, where data are interfaced with directly from PACS in the DICOM format, in neuroimaging research, tools typically require data files in the much simpler (and metadata-restricted) NIfTI [@nifticlib] format.
Tools such as `dcm2niix` [@Li_2016] can be used to convert *individual* DICOM files into named NIfTI files, and can extract metadata fields not covered by the NIfTI header into sidecar `.json` files.
However, the scope of such tools is limited, as it does not extend to organizing *multiple* files within a study.

HeuDiConv was created in 2014 to provide flexible tooling so that labs may rapidly and consistently convert collections of DICOM files into collections of NIfTI files in customizable file system hierarchies.
As manual file renaming and metadata reorganization is tedious and error prone, automation is preferable, and this is a consistent focus of HeuDiConv.

Since the inception of HeuDiConv in 2014, the BIDS standard [@GAC+16] was established.
BIDS standard formalizes data file hierarchies and metadata storage in a fashion which, due to its community-driven nature, is both highly optimized and widely understood by analysis tools.
Since then, DICOM conversion to NIfTI files contained within a BIDS hierarchy has emerged as the most frequent use-case for HeuDiConv.

# Overview of HeuDiConv functionality

HeuDiConv was initially developed to implement common for every lab logic (groupping DICOMs, extraction of metadata, conversion of individual sequences, populating standard BIDS files, etc.) while allowing individual groups to customize **how** files should be organized and named while driving custom decisions by the conventions and desires of those individual groups.
Such decision making is implemented in *HeuDiConv heuristics*, which are implemented as Python modules following some minimalistic specified interfaces documented in HeuDiConv documentation (https://heudiconv.readthedocs.io/en/latest/heuristics.html).
HeuDiConv, if instructed to operate in BIDS mode (`--bids` flag) after heuristic provides base naming instructions, takes care about correct placement of files in the hierarchy, naming of multi-echo and other split files, etc.

![**HeuDiConv automates the keystone conversion step in reproducible data handling, without compromising operator flexibility.** The showcased set-up depicts a 2-machine infrastructure, with heudiconv operating on the same machine as subsequent analysis steps for data in a standardized and shareable representation. For more advanced usage at institutions with dedicated infrastructure, HeuDiConv can operate on an additional third machine, interfacing between the depicted two, and dedicated to data repositing, versioning, and backup.](figs/workflow.pdf)

## Exemplar heuristics

### Convertall

The [convertall heuristic](https://github.com/nipy/heudiconv/blob/v0.12.2/heudiconv/heuristics/convertall.py) is the simplest heuristic which expresses no knowledge or assumptions about anything and can be used as a template to develop new heuristic or to establish initial mapping for manual naming of the sequences in the "manual curation" step.

### StudyForrest phase 2

The [studyforrest_phase2 heuristic](https://github.com/nipy/heudiconv/blob/v0.12.2/heudiconv/heuristics/studyforrest_phase2.py) is a small sample heuristic developed for the StudyForrest [@studyforrest] project, and demonstrates custom conversion into BIDS dataset.

### ReproIn

The [ReproIn heuristic](https://github.com/nipy/heudiconv/blob/v0.12.2/heudiconv/heuristics/reproin.py) was initially developed at the Dartmouth Brain Imaging Center (DBIC) to automate data conversion into BIDS for any neuroimaging study performed using the center's facilities.
The core principle behind ReproIn is the reduction of operator interaction required to obtain BIDS datasets for acquired data.
It is achieved by ensuring that reference MRI sequences on the instrumentation are organized and named in a consistent and flexible way, such that upon usage in any experimental protocol they will encode the information required for fully automatic conversion and repositing of the resulting data.

In case of correct specification and absent operator errors, such as mis-typed subject or session IDs, it can be fully automated, and work is ongoing to make such deployments turnkey. Visit ReproIn project page http://reproin.repronim.org to discover more.

# Adoption and usage

HeuDiConv has [RRID:SCR_017427](https://scicrunch.org/resolver/RRID:SCR_017427) as of time of writing mentions already [6 mentions in papers](https://scicrunch.org/resolver/SCR_017427/mentions?q=&i=rrid:scr_017427).
There is a growing number of downloads from PyPI and uses of HeuDiConv (see \autoref{fig:usage}).
Over 40 BIDS datasets were converted using HeuDiConv with ReproIn heuristic over to BIDS at Dartmouth Brain Imaging Center (DBIC), where ReproIn heuristic being developed. 
HeuDiConv was found to be used for PET data conversion [@JZC+21:PET], shared as OpenNeuro ds003382 [@openneuro.ds003382.v1.0.0].
Moreover, HeuDiConv approach inspired development of `fw-heudiconv` (FlywheelTools: Software for HeuDiConv-Style BIDS Curation On Flywheel) [@TCB+21:fw-heudiconv].

![**Weekly downloads experienced an initial sharp rise after the 0.5.1 ReproNim training event in mid 2018, and have continued to grow along a positive trend.** Depicted are weekly download averages per month, with a 95% confidence interval.](figs/downloads.pdf)
![Usage](figs/etelemetry.pdf)


# External dependencies

HeuDiConv uses specialized tools and libraries: 

- [`datalad`](https://datalad.org) [@datalad] ([RRID: SCR_003931](https://scicrunch.org/resolver/RRID:SCR_003931)) enables managing produced datasets as version controlled repositories.
- [`dcm2niix`](https://github.com/rordenlab/dcm2niix) [@Li_2016] is used for the conversion from DICOM to NIfTI and initial versions of sidecar .json files,
- [`etelemetry`](https://github.com/sensein/etelemetry-client) and [`filelock`](https://github.com/tox-dev/py-filelock) are used as supplementary utilities,
- [`neurodocker`](https://github.com/ReproNim/neurodocker) [@zenodo:neurodocker] ([RRID:SCR_017426](https://scicrunch.org/resources/data/record/nlx_144509-1/SCR_017426/resolver?q=dcm2niix&l=dcm2niix&i=rrid:scr_017426)) is used to produce `Dockerfile` from which docker images are built,
- [`nipype`](https://nipype.readthedocs.org/) [@nipype] ([RRID:SCR_002502](https://scicrunch.org/resources/data/record/nlx_144509-1/SCR_002502/resolver)) to interface `dcm2niix` and extra metadata invocations,
- [`pydicom`](https://pydicom.github.io/) [@zenodo:pydicom] ([RRID:SCR_002573](https://scicrunch.org/resources/data/record/nlx_144509-1/SCR_002573/resolver)) and [`dcmstack`](https://github.com/moloney/dcmstack) for DICOM analysis and extraction of extra metadata to place to BIDS sidecar files,
- [`pytest`](https://pytest.org) formalizes unit and integration testing.

# Acknowledgments

We would like to extend our gratitude to
ADD YOUR NAME HERE
for notable contributions to the codebase, bug reports, recommendations, and promotion of HeuDiConv.

HeuDiConv development was primarily done under the umbrella of the NIH funded ReproNim [1P41EB019936-01A1](https://projectreporter.nih.gov/project_info_details.cfm?aid=8999833&map=y) and [2P41EB019936-06A1](https://projectreporter.nih.gov/project_info_details.cfm?aid=10334133&map=y) (PI: Kennedy).
Contributions of TODO1 were supported by TODO1, ...

# References
