==========================
Duration of an acquisition
==========================

Upon conversion to BIDS, HeuDiConv records in the ``duration`` column of
``_scans.tsv`` how long, in seconds, the stored data took to acquire: from
the onset of the first stored volume, which is what ``acq_time`` is, to the
end of the last one.  The preparation, reference and dummy scans which
precede the first stored volume are thus not meant to be counted, although
scanners count them in the durations they report.

All that HeuDiConv knows about establishing it is in
:mod:`heudiconv.duration`, so that the module could be replaced as a whole
should ``dcm2niix`` come to provide such a duration (see `Relation to
dcm2niix`_).  Where no source below applies, ``n/a`` is recorded: no
duration is preferred to a wrong one.

From DICOMs
===========

Upon conversion, and for a dataset converted earlier which has its DICOMs
under ``sourcedata/``, the first of these to apply is used:

1. **GE's private "Acquisition Duration"** (0019,105A).  It is of all the
   volumes planned (``NumberOfTemporalPositions``), so if fewer are stored,
   it is scaled to their share.  The acquisition times in GE files do not
   tell their volumes apart, hence this comes first.
2. **Onsets of the numbered volumes.**  Volumes are numbered by
   ``AcquisitionNumber`` (Siemens) or ``TemporalPositionIdentifier``
   (Philips), if the files have at least two of those, and their volumes
   follow in time as they do in number.  The duration is from the first
   onset to the end of the last volume, a volume taking as long as onsets
   are apart per their numbers.  This is the only source which leaves out
   what precedes the first stored volume.
3. **The AcquisitionDuration tag** (0018,9073), unless shorter than the
   acquisition times of the files span (then it is of a single volume),
   longer than 4 hours, or of UIH, which has it in milliseconds.
4. **The scan time declared in a Siemens protocol** (``lTotalScanTimeSec``),
   if the protocol is of a single volume.

Spectroscopy gets none: its ``AcquisitionDuration`` could be of each file.

With just two volumes which are numbered consecutively, how long a volume
takes cannot be told from how far apart they are, since what precedes the
second one (e.g. multiband reference scans) may be in between.  They get
two ``RepetitionTime`` if they are one apart, and ``n/a`` otherwise.

From a NIfTI and its sidecar
============================

Without DICOMs, ``--command populate-scans-duration`` goes by the converted
files: for more than one volume it is their number times ``RepetitionTime``,
and for a single one the ``AcquisitionDuration`` of the sidecar.  Volumes
which are not a ``RepetitionTime`` apart get ``n/a``: ASL, spectroscopy, and
anything with ``VolumeTiming``.

What the rules are based on
===========================

They were arrived at, and are checked, on the 404 series (36,768 DICOMs) of
the 51 ``dcm_qa*`` collections at https://github.com/neurolabusc (see `Li et
al., 2025 <https://doi.org/10.1038/s41597-025-05503-w>`_).  What
:mod:`heudiconv.duration` goes by for each of those series, and what it
gives, is recorded in ``heudiconv/tests/data/dcm_qa_durations.json``, which
the tests go through; with ``HEUDICONV_TEST_DCM_QA`` pointing to clones of
the collections, they also check that record against the DICOMs themselves.
269 series get a duration: 103 from the onsets of their volumes, 77 from
GE's tag (27 of them scaled), 42 from ``AcquisitionDuration``, and 47 from a
Siemens protocol.

**The tag counts more than what is stored.**  For complete Siemens XA runs it
exceeds what the onsets of their volumes span by an amount which depends on
the acceleration, the multiband factor and the sequence, and which no
standard attribute records:

==============================================  ==================
Run                                             Excess, in TRs
==============================================  ==================
ASL (``dcm_qa_xa30``)                           0.4
BOLD, GRAPPA 2 and 3 (``dcm_qa_xa60``)          5 and 7
BOLD (``dcm_qa_xa30``, ``dcm_qa_noRF``)         8 to 10
Diffusion (``dcm_qa_xa30``, ``dcm_qa_xa60``)    3 to 15
CMRR multiband 2 and 5 (``dcm_qa_xa60``)        12 to 16, 24 to 33
==============================================  ==================

E.g. for the 20 volumes of ``func-bold_task-fa_run-1`` of ``dcm_qa_xa30``,
1 s apart, the tag is of 27.89 s.

**The tag is of what was planned.**  For a run which got aborted, as
``xa_4d_interrupted`` among the test data of HeuDiConv, it is of the full
protocol (602.7 s), whereas the 2 stored volumes, numbered 1 and 21, are
36.2 s apart: 38.0 s.

**The tag may be of a single volume**, as for 3D EPI and ASL of Siemens XA60
(``dcm_qa_ep3d``, ``dcm_qa_asl``): about a second for runs of tens of them.

**Acquisition times alone do not tell volumes.**  Files of two echoes of a
field map may be a ``RepetitionTime`` apart (``dcm_qa_xa30``: 0.6025 s, for
a scan of 76.2 s), files of the echoes of a volume milliseconds apart
(``dcm_qa_me``, ``dcm_qa_physio``), and files of slices anywhere within a
``RepetitionTime``.  ``AcquisitionNumber`` is the same for all of those.  On
the 103 Siemens series with more than one ``AcquisitionNumber`` the duration
by their onsets matches the number of volumes which ``dcm2niix`` makes of
them times their ``RepetitionTime``, where that is a measure.

**GE's times are not of volumes.**  They change within a series just as a
second passes, also in the 32 series whose files do carry a
``TemporalPositionIdentifier``; hence the requirement for volumes to follow
in time as they do in number, which all 103 Siemens and 4 Philips series
meet and none of those does.  GE's tag is right where ``RepetitionTime``
is not: for the runs with a delay between volumes (``dcm_qa_trt``), going by
their trigger times.

Known limitations
=================

- From GE's tag, the ``AcquisitionDuration`` tag and a Siemens protocol the
  duration includes what preceded the first stored volume; e.g. 6.6 s for 3
  stored volumes 2 s apart of ``dcm_qa_ge``.  The latter two are moreover
  of what was planned.  How GE's tag is for a run aborted on the scanner
  was not checked.
- Times of the frames of a multi-frame (enhanced) file are not looked at,
  so a run stored in a single such file gets its tag: 16.4 s for the 4
  volumes 1.5 s apart of the Philips ``resting_state`` of ``dcm_qa_enh``,
  and 150 s for the 130 s of Canon's diffusion in ``dcm_qa_canon_enh``.
- Two volumes numbered consecutively, but not a ``RepetitionTime`` apart,
  get ``n/a`` even where their distance is how long each took (ASL,
  ``pasl_3d_m0`` of ``dcm_qa_asl``).
- From a NIfTI and its sidecar, the number of volumes times
  ``RepetitionTime`` leaves out any delay between volumes.
- Not represented in those collections, hence not checked: runs aborted on
  the scanner other than ``xa_4d_interrupted``; long runs (3 series have 50
  or more volumes); sparse, clustered or triggered acquisitions; PET; Bruker
  and other vendors.  The 26 CT series, Canon's and UIH's classic files get
  ``n/a``.

Relation to dcm2niix
====================

``dcm2niix`` passes the ``AcquisitionDuration`` tag (GE's private one taking
precedence) on to the JSON sidecar as is, whatever it is of (`#606
<https://github.com/rordenlab/dcm2niix/issues/606>`_, `#808
<https://github.com/rordenlab/dcm2niix/issues/808>`_), and uses the times of
volumes only to establish ``RepetitionTime``.  That such tags count dummy
scans, whose number is not recorded, was noted for Philips in `#369
<https://github.com/rordenlab/dcm2niix/issues/369>`_; a request for
``FrameAcquisitionDuration`` (`#991
<https://github.com/rordenlab/dcm2niix/issues/991>`_) was declined for BIDS
not defining such timing for it to follow.  The start of an acquisition was
taken up in `#1039 <https://github.com/rordenlab/dcm2niix/issues/1039>`_.
Should ``dcm2niix`` report the duration of the stored data, e.g. upon BIDS
defining it (`bids-specification#2508
<https://github.com/bids-standard/bids-specification/pull/2508>`_),
:func:`heudiconv.duration.from_sidecar` would read it, and the rest of the
module could go.
