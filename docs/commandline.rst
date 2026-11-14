=============
CLI Reference
=============

``heudiconv`` processes DICOM files and converts the output into user defined
paths.

.. argparse::
   :ref: heudiconv.cli.run.get_parser
   :prog: heudiconv
   :nodefault:
   :nodefaultconst:

Scan durations in ``_scans.tsv``
================================

Upon conversion to BIDS, the ``duration`` column of each ``_scans.tsv`` gets
the wallclock duration of the scan in seconds, and ``acq_time`` the time of its
earliest DICOM.  To add ``duration`` to a dataset converted before that, run::

    heudiconv --command populate-scans-duration --files /path/to/bids

It is taken from the DICOMs kept under ``sourcedata/`` or, without those,
estimated from the NIfTI and its JSON sidecar; ``n/a`` is recorded where
neither tells.  Rows which already have a duration are left alone unless
``--overwrite`` is given, and even then keep a value which could not be
re-established.

If ``acq_time`` of a (re)computed row is not the time of the earliest DICOM
(see `issue 876 <https://github.com/nipy/heudiconv/issues/876>`_), that is
reported; add ``--fix-acq-time`` to also correct it, along with
``AcquisitionTime`` in the JSON sidecar of the scan.
