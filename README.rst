=============
**HeuDiConv**
=============

`a heuristic-centric DICOM converter`

.. image:: https://img.shields.io/badge/docker-nipy/heudiconv:unstable-brightgreen.svg?logo=docker&style=flat
  :target: https://hub.docker.com/r/nipy/heudiconv/tags/
  :alt: Our Docker image

.. image:: https://travis-ci.org/nipy/heudiconv.svg?branch=master
  :target: https://travis-ci.org/nipy/heudiconv
  :alt: TravisCI

.. image:: https://codecov.io/gh/nipy/heudiconv/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/nipy/heudiconv
  :alt: CodeCoverage

.. image:: https://readthedocs.org/projects/heudiconv/badge/?version=latest
  :target: http://heudiconv.readthedocs.io/en/latest/?badge=latest
  :alt: Readthedocs

About
-----

``heudiconv`` is a flexible DICOM converter for organizing brain imaging data
into structured directory layouts.

- it allows flexible directory layouts and naming schemes through customizable heuristics implementations
- it only converts the necessary DICOMs, not everything in a directory
- you can keep links to DICOM files in the participant layout
- using dcm2niix under the hood, it's fast
- it can track the provenance of the conversion from DICOM to NIfTI in W3C PROV format
- it provides assistance in converting to `BIDS <http://bids.neuroimaging.io/>`_.
- it integrates with `DataLad <https://www.datalad.org/>`_ to place converted and original data under git/git-annex version control, while automatically annotating files with sensitive information (e.g., non-defaced anatomicals, etc)
