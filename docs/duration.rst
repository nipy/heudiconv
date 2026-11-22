==========================
Duration of an acquisition
==========================

Upon conversion to BIDS, HeuDiConv records in the ``duration`` column of
``_scans.tsv`` how long, in seconds, the stored data took to acquire: from
the onset of the first stored volume, which is what ``acq_time`` is, to the
end of the last one.  The preparation, reference and dummy scans which
precede the first stored volume are thus not counted, although scanners
count them in the durations they report.

All of it is done by :func:`heudiconv.duration.get_acquisition_duration`, the
only function of :mod:`heudiconv.duration` the rest of HeuDiConv uses, so that
the module could be replaced as a whole should ``dcm2niix`` come to provide
such a duration (see `Relation to dcm2niix`_).

Sources
=======

In order, the first one which applies being used:

1. **GE's private "Acquisition Duration"** (0019,105A).  ``AcquisitionTime``
   of GE files is not of their volumes, so there is nothing to check it
   against, or to tell by how much of it preceded the first volume.
2. **Timestamps of volumes**: if the distinct acquisition times of the files
   are whole numbers of ``RepetitionTime`` apart, the duration is from the
   earliest of them to the end of the volume of the latest.
3. **The AcquisitionDuration tag** (0018,9073), unless shorter than what the
   timestamps span.
4. **The scan time declared in a Siemens protocol** (``lTotalScanTimeSec``),
   if the protocol is of a single volume.
5. **Timestamps of whatever they are of**, e.g. of slices or echoes: from the
   earliest to a median interval past the latest, if they span more than a
   ``RepetitionTime``.

Otherwise ``n/a`` is recorded.

What the rules are based on
===========================

They were arrived at, and checked, on the 400 image series of the 51
``dcm_qa*`` collections of DICOMs at https://github.com/neurolabusc (see
`Li et al., 2025 <https://doi.org/10.1038/s41597-025-05503-w>`_), 55 of which
have both a duration tag and files acquired at different times.

**The tag counts more than what is stored.**  For complete Siemens XA runs it
exceeds what the timestamps of their volumes span by an amount which depends
on the acceleration, the multiband factor and the sequence, and which no
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
1 s apart, the tag is of 27.89 s.  Hence timestamps of volumes, where there
are such, are preferred to it.

**The tag is of what was planned.**  For a run which got aborted, as
``xa_4d_interrupted`` among the test data of HeuDiConv, it is of the full
protocol (602.7 s), whereas the 2 stored volumes are 36.2 s (20 TRs) apart.

**The tag may be of a single volume.**  For 3D EPI and ASL of Siemens XA60
(``dcm_qa_ep3d``, ``dcm_qa_asl``) it is about a second for runs of tens of
seconds.  Hence it is not used if shorter than what the timestamps span.

**Timestamps are not always of volumes.**  Those of GE files change within a
series just as a second passes (``dcm_qa_ge``, ``dcm_qa_trt``); with a file
per echo they are milliseconds apart (``dcm_qa_physio``, ``dcm_qa_jpg``);
with a file per slice they tell where within a ``RepetitionTime`` the slice
got acquired, e.g. spanning 0.4 s for a field map which took 54 s
(``dcm_qa_fmap``).  Hence the test for them being whole numbers of
``RepetitionTime`` apart, and hence a protocol of a single volume being
preferred to the timestamps which fail it.

Known limitations
=================

- Where the tag, GE's or the standard one, is what there is to go by, the
  duration includes what preceded the first stored volume.
- So does the one declared in a Siemens protocol, which moreover is of what
  was planned.  Diffusion protocols count as being of a single volume, so
  for an aborted diffusion run with a file per slice it would be too long.
- For volumes which take several ``RepetitionTime`` each (e.g. pairs of ASL
  volumes of ``dcm_qa_philips_asl``), the interval between them is taken for
  how long the last one took.  With just two timestamps that cannot be told
  from an aborted run, and a single ``RepetitionTime`` is assumed.

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
:mod:`heudiconv.duration` could give way to reading it from the sidecar.
