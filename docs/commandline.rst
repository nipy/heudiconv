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
the :doc:`duration of the stored data <duration>` in seconds, and ``acq_time``
the time of its earliest DICOM.  To add ``duration`` to a dataset converted
before that, run::

    heudiconv --command populate-scans-duration --files /path/to/bids

It is taken from the DICOMs kept under ``sourcedata/`` or, without those,
estimated from the NIfTI and its JSON sidecar; ``n/a`` is recorded where
neither tells.  Rows which already have a duration are left alone unless
``--overwrite`` is given, and even then keep a value which could not be
re-established.

If ``acq_time`` of a row whose duration gets established is not the time of
the earliest DICOM under ``sourcedata/`` (see `issue 876
<https://github.com/nipy/heudiconv/issues/876>`_), that is reported.  With
``--fix-acq-time`` that is checked for every row, and corrected, along with
``AcquisitionTime`` in the scan's own JSON sidecar.  A difference of more than 12 hours is taken for
shifted (anonymized) dates and left alone.  The command also adds the
description of ``duration`` to ``scans.json``.
