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

For the most efficient processing neuroimaging data must be formatted according to data standards used by researchers in the field, and supported by the analytics software.
HeuDiConv (Heuristic DICOM Converter) allows for flexible and efficient conversion of acquired neuroimaging data from DICOM format (used by the scanners and in clinical settings) to Brain Imaging Data Structure (BIDS) [@GAC+16] which is the community-driven standard in neuroimaging research. 
HeuDiConv allows for either two stage (discover, manually tune, perform conversion) or fully automated conversion of collections of DICOMs to BIDS, or if desired, some other files layouts.
HeuDiConv, written in Python, extracts metadata from DICOM files, groups those files into sessions for indepdent conversions, and provides extracted metadata to a provided or custom heuristic, also written in Python, to decide on how the output file needs to be named.
In case of conversion specifically to BIDS it follows up with additional logic to handle specific data types (e.g., multi-echo sequeneces, SBRef volumes).
HeuDiConv also integrates with DataLad [@datalad] to prepare DataLad datasets with settings to ensure that data and sensitive metadata (e.g. `_scans.tsv` files) are saved to `git-annex` and the rest to `git`, to provide fake commit dates to avoid leaking of sensitive "patient visit" dates, etc.
As a result, given that anyone can prepare a custom heuristic based on idiosyncracies of a specific study or entire imaging center, in tandem with implemented automatizations HeuDiConv can become a very flexible and powerful tool in every neuroimaging workflow. 

# Statement of need

Neuroimaging is an empirical field of science heavily relying on efficient data acquisition, harmonization, and processing.
Neuroimaging data acquired by MRI scanners usually are exported from them in a set of formats, with DICOM (Digital Imaging and Communications in Medicine) being a standard metadata-rich form.
Data in DICOM format is usually transmitted to PACS (Picture Archiving and Communication Systems) servers for archival and possibly further processing.
Unlike in clinical settings, where data is interfaced directly from PACS in DICOM format, in neuroimaging research tools typically expect data in much simpler NIfTI [@nifticlib] format.
Tools such as `dcm2niix` [@Li_2016] can be used to convert individual DICOM files into named NIfTI and even can extract some additional extra metadata into sidecar `.json` files. 
But NIfTI file format carries only basic metadata and `dcm2niix` does not instruct how to organize multiple files within a study.

HeuDiConv was developed to provide flexible tooling for labs to be able efficiently and consistently convert collections of DICOM files into collections of NIfTI (and compressed archives of DICOMs) files in desired file system hierarchies.
Since the inception of HeuDiConv in 2014, a community-driven standard Brain Imaging Data Structure (BIDS) [@GAC+16] was established, which formalized such datasets layout and storage of metadata.
Since then the most frequent use-case for HeuDiConv became conversion of DICOM files into BIDS datasets.
Standardization into BIDS facilitates not only reuse of already shared datasets but also streamlines data validation, curation, analysis, etc.

# Overview of HeuDiConv functionality

## Exemplar heuristics

### ReproIn heuristic

ReproIn heuristic was initially developed at Dartmouth Brain Imaging Center (DBIC) to maximally automate data conversion to BIDS for *any* neuroimaging study at the center.
The principle behind ReproIn is minimization of overall time effort by investing only negligible time at the beginning to organize and name of the MRI programs on the scanner in agreement with ReproIn specification.
As a result, later transmitted as DICOMs data could *in principle* be fully automatically placed into corresponding study datasets and fully automatically converted.
It is *in principle* fully automat .... KIDS ...!!!

# Acknowledgements

We would like to extend our gratitude to
ADD YOUR NAME HERE
for notable contributions to the codebase, bug reports, recommendations, and promotion of HeuDiConv.

HeuDiConv development was primarily done under the umbrella of the NIH funded ReproNim [1P41EB019936-01A1](https://projectreporter.nih.gov/project_info_details.cfm?aid=8999833&map=y) and [TODO - renewal](TODO) (PI: Kennedy).
It also received contributions from the ...

# References
