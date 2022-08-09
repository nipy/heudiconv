=============
**HeuDiConv**
=============

`a heuristic-centric DICOM converter`

.. image:: https://img.shields.io/badge/docker-nipy/heudiconv:latest-brightgreen.svg?logo=docker&style=flat
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

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.1012598.svg
  :target: https://doi.org/10.5281/zenodo.1012598
  :alt: Zenodo (latest)

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

How to cite
-----------

Please use `Zenodo record <https://doi.org/10.5281/zenodo.1012598>`_ for
your specific version of HeuDiConv.  We also support gathering
all relevant citations via `DueCredit <http://duecredit.org>`_.


How to contribute
-----------------

HeuDiConv sources are managed with Git on `GitHub <https://github.com/nipy/heudiconv/>`_.
Please file issues and suggest changes via Pull Requests.

HeuDiConv requires installation of
`dcm2niix <https://github.com/rordenlab/dcm2niix/>`_ and optionally
`DataLad <https://datalad.org>`_.

For development you will need a non-shallow clone (so there is a
recent released tag) of the aforementioned repository. You can then
install all necessary development requirements using ``pip install -r
dev-requirements.txt``.  Testing is done using `pytest
<https://docs.pytest.org/>`_.  Releases are packaged using Intuit
auto.  Workflow for releases and preparation of Docker images is in
``.github/workflows/release.yml``.
