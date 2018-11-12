# HeuDiConv - Heuristic DICOM Converter
[![Build Status](https://travis-ci.org/nipy/heudiconv.svg?branch=master)](https://travis-ci.org/nipy/heudiconv)
[![codecov](https://codecov.io/gh/nipy/heudiconv/branch/master/graph/badge.svg)](https://codecov.io/gh/nipy/heudiconv)

This is a flexible DICOM converter for organizing brain imaging data into
structured directory layouts.

- it allows flexible directory layouts and naming schemes through
  customizable heuristics implementations
- it only converts the necessary DICOMs, not everything in a directory
- you can keep links to DICOM files in the participant layout
- it's faster than parsesdicomdir or mri_convert if you use dcm2niix option
- it tracks the provenance of the conversion from DICOM to NIfTI in W3C
  PROV format
- it provides assistance in converting to [BIDS]
- it integrates with [DataLad] to place converted and original data
  under git/git-annex version control, while automatically annotating files
  with sensitive information (e.g., non-defaced anatomicals, etc)

### Heuristics

HeuDiConv operates using a heuristic, which provides information on
how your files should be converted. A number of example heuristics are
provided to address various use-cases

- the [cmrr_heuristic](heudiconv/heuristics/cmrr_heuristic.py) provides an
  example for a conversion to [BIDS]
- the [reproin](heudiconv/heuristics/reproin.py) could be used to establish
  a complete imaging center wide automation to convert all acquired
  data to [BIDS] following a simple naming
  [convention](https://goo.gl/o0YASC) for studies and sequences

## Install

### Released versions

Released versions of HeuDiConv are available from PyPI so you could
just `pip install heudiconv[all]` for the most complete installation, 
and it would require manual installation only
of the [dcm2niix](https://github.com/rordenlab/dcm2niix/).  On
Debian-based systems we recommend to use
[NeuroDebian](http://neuro.debian.net) providing
[heudiconv Debian package](http://neuro.debian.net/pkgs/heudiconv.html).

### From source

You can clone this directory and use `pip install .[all]` (with `--user`,
`-e` and other flags appropriate for your case), or

`pip install https://github.com/nipy/heudiconv/archive/master.zip`

## Dependencies

- pydicom
- dcmstack
- nipype
- nibabel
- dcm2niix

and should be checked/installed during `pip install` call, all but `dcm2niix`
which should be installed directly from upstream or using the distribution
manager appropriate for your OS.

## Tutorial with example conversion to BIDS format using Docker
Please read this tutorial to understand how heudiconv works in practice.

[Slides here](http://nipy.org/heudiconv/#1)

To generate lean BIDS output, consider using both the `-b` and the `--minmeta` flags 
to your heudiconv command. The `-b` flag generates a json file with BIDS keys, while
the `--minmeta` flag restricts the json file to only BIDS keys. Without `--minmeta`,
the json file and the associated Nifti file contains DICOM metadata extracted using
dicomstack.

### Other tutorials

- YouTube:
    - ["Heudiconv Example"](https://www.youtube.com/watch?v=O1kZAuR7E00) by [James Kent](https://github.com/jdkent)

## How it works (in some more detail)

Call `heudiconv` like this:

    heudiconv -d '{subject}*.tar*' -s xx05 -f ~/myheuristics/convertall.py

where `-d '{subject}*tar*'` is an expression used to find DICOM files
(`{subject}` expands to a subject ID so that the expression will match any
`.tar` files, compressed or not that start with the subject ID in their name).
An additional flag for session (`{session}`) can be included in the expression
as well. `-s od05` specifies a subject ID for the conversion (this could be a
list of multiple IDs), and `-f ~/myheuristics/convertall.py` identifies a
heuristic implementation for this conversion (see below) for details.

This call will locate the DICOMs (in any number of matching tarballs), extract
them to a temporary directory, search for any DICOM series it can find, and
attempts a conversion storing output in the current directory. The output
directory will contain a subdirectory per subject, which in turn contains an
`info` directory with a full protocol of detected DICOM series, and how their
are converted.

### The `info` directory

The `info` directory contains a copy of the heuristic script as well as the
dicomseries information. In addition there are two files NAME.auto.txt and
NAME.edit.txt. You can change series number assignments in NAME.edit.txt and
rerun the converter to apply the changes. To start from scratch remove the
participant directory.  

## Outlook

soon you'll be able to:
- add more tags to the metadata representation of the files
- and push the metadata to a provenance store

## The heuristic file

The heuristic file controls how information about the dicoms is used to convert
to a file system layout (e.g., BIDS). This is a python file that must have the
function `infotodict`, which takes a single argument `seqinfo`.  

### `seqinfo` and the `s` variable

`seqinfo` is a list of namedtuple objects, each containing the following fields:

* total_files_till_now
* example_dcm_file
* series_id
* dcm_dir_name
* unspecified2
* unspecified3
* dim1
* dim2
* dim3
* dim4
* TR
* TE
* protocol_name
* is_motion_corrected
* is_derived
* patient_id
* study_description
* referring_physician_name
* series_description
* image_type

```
128     125000-1-1.dcm  1       -       -       
-       160     160     128     1       0.00315 1.37    AAHScout        False
```

### The dictionary returned by `infotodict`

This dictionary contains as keys a 3-tuple `(template, a tuple of output types,
 annotation classes)`.

template - how the file should be relative to the base directory
tuple of output types - what format of output should be created - nii.gz, dicom,
 etc.,.
annotation classes - unused

```
Example: ('func/sub-{subject}_task-face_run-{item:02d}_acq-PA_bold', ('nii.gz',
        'dicom'), None)
```

A few fields are defined by default and can be used in the template:

- item: index within category
- subject: participant id
- seqitem: run number during scanning
- subindex: sub index within group
- session: session info for multi-session studies and when session has been
  defined as a parameter for heudiconv

Additional variables may be added and can be returned in the value of the
dictionary returned from the function.

`info[some_3-tuple] = [12, 14, 16]` would assign dicom sequence groups 12, 14
and 16 to be converted using the template specified in `some_3-tuple`.

if the template contained a non-sanctioned variable, it would have to be
provided in the values for that key.

```
some_3_tuple = ('func/sub-{subject}_task-face_run-{item:02d}_acq-{acq}_bold', ('nii.gz',
        'dicom'), None)
```

In the above example `{acq}` is not a standard variable. In this case, values
for this variable needs to be added.

```
info[some_3-tuple] = [{'item': 12, 'acq': 'AP'},
                      {'item': 14, 'acq': 'AP'},
                      {'item': 16, 'acq': 'PA'}]
```

[BIDS]: http://bids.neuroimaging.io
[DataLad]: http://datalad.org
