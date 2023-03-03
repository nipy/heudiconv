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

In order to support efficient and transparent processing, as provided by cutting-edge Free and/or Open Source (FOSS) tools, neuroimaging data must be formatted according to equally open and accessible standards.
The Brain Imaging Data Structure (BIDS) [@GAC+16] is an open standard designed for computational accessibility, operator legibility, and a wide and easily extendable scope of modalities — and is consequently used by numerous analysis and processing tools as the preferred input format.
HeuDiConv (Heuristic DICOM Converter) enables flexible and efficient conversion of spatially reconstructed neuroimaging data from the DICOM format (quasi-ubiquitous in biomedical image acquisition systems, particularly in clinical settings) to BIDS, as well as other file layouts.
This can be done either via a multi-stage operator input workflow (discovery, manual tuning, conversion) or via a fully automated process that can be seamlessly integrated into a data pipeline.
HeuDiConv is written in Python, and supports the DICOM specification for input parsing, and the BIDS specification for output construction.
The support for these standards is extensive, and HeuDiConv can handle complex organization scenarios such as arise for specific data types (e.g., multi-echo sequences, or single-band reference volumes).
In addition to generating valid BIDS outputs, additional support is offered for custom output layouts.
This is obtained via a set of example heuristiscs, which can be modified into supplemental heuristics expressed as simple Python functions, thus providing full flexibility and maintaining user accessibility.
HeuDiConv further integrates with DataLad [@datalad], and can automatically prepare DataLad datasets with optional obfuscation of sensitive data and metadata, including obfuscating patient visit timestamps in version control.
As a result, given its extensibility, large modality support, and integration with advanced data management technologies, HeuDiConv has become a mainstay in numerous neuroimaging workflows, and constitutes a powerful and highly adaptable tool of potential interest to large swathes of the neuroimaging community.


# Statement of Need

Neuroimaging is an empirical research area which relies heavily on efficient data acquisition, harmonization, and processing.
Neuroimaging data sourced from medical imaging equipment, and in particular magnetic resonance imaging (MRI) scanners, can be exported in numerous formats, among which DICOM (Digital Imaging and Communications in Medicine) is most prominent.
DICOM data are often transmitted to PACS (Picture Archiving and Communication Systems) servers for archiving or further processing.
Unlike in clinical settings, where data are interfaced with directly from PACS in the DICOM format, in neuroimaging research, tools typically require data files in the much simpler (and metadata-restricted) NIfTI [@nifticlib] format.
Tools such as `dcm2niix` [@Li_2016] can be used to convert *individual* DICOM files into named NIfTI files, and can extract metadata fields not covered by the NIfTI header into sidecar `.json` files.
However, the scope of such tools is limited, as it does not extend to organizing *multiple* files within a study.

HeuDiConv was developed to provide flexible tooling so that labs may rapidly and consistently convert collections of DICOM files into collections of NIfTI files in customizable file system hierarchies.
Since the inception of HeuDiConv in 2014, the BIDS standard [@GAC+16] was established.
This standard formalizes data file hierarchies and metadata storage in a fashion which, due to its community-driven nature, is both highly optimized and widely understood by analysis tools.
Since then, DICOM conversion to NIfTI files contained within a BIDS hierarchy has emerged as the most frequent use-case for HeuDiConv.

# Overview of HeuDiConv functionality

## Exemplar heuristics

### ReproIn heuristic

The ReproIn heuristic was initially developed at the Dartmouth Brain Imaging Center (DBIC) to automate data conversion into BIDS for any neuroimaging study performed using the center's facilities.
The core principle behind ReproIn is the reduction of operator interaction requirements by ensuring that reference MRI sequences on the instrumentation are named in such a way that upon usage in any experimental protocol they will encode the information required for fully automatic conversion and repositing of the resulting data.

It is *in principle* fully automat .... KIDS ...!!!

# Acknowledgements

We would like to extend our gratitude to
ADD YOUR NAME HERE
for notable contributions to the codebase, bug reports, recommendations, and promotion of HeuDiConv.

HeuDiConv development was primarily done under the umbrella of the NIH funded ReproNim [1P41EB019936-01A1](https://projectreporter.nih.gov/project_info_details.cfm?aid=8999833&map=y) and [TODO - renewal](TODO) (PI: Kennedy).
It also received contributions from the ...

# References
