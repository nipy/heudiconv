=========
Heuristic
=========

The heuristic file controls how information about the DICOMs is used to convert
to a file system layout (e.g., BIDS). ``heudiconv`` includes some built-in
heuristics, including `ReproIn <https://github.com/ReproNim/reproin/blob/master/README.md>`_
(which is great to adopt if you will be starting your data collection!).

However, there is a large variety of data out there, and not all DICOMs will be
covered by the existing heuristics. This section will outline what makes up a
heuristic file, and some useful functions available when making one.


Components
==========

------------------------
``infotodict(seqinfos)``
------------------------

The only required function for a heuristic, `infotodict` is used to both define
the conversion outputs and specify the criteria for scan to output association.
Conversion outputs are defined as keys, a `tuple` consisting of a template path
used for the basis of outputs, as well as a `tuple` of output types. Valid types
include `nii`, `nii.gz`, and `dicom`.

.. note:: An example conversion key

    ``('sub-{subject}/func/sub-{subject}_task-test_run-{item}_bold', ('nii.gz', 'dicom'))``


The ``seqinfos`` parameter is a list of namedtuples which serves as a grouped and
stacked record of the DICOMs passed in. Each item in `seqinfo` contains DICOM
metadata that can be used to isolate the series, and assign it to a conversion
key.

A dictionary of {``conversion key``: ``seqinfo``} is returned.

---------------------------------
``create_key(template, outtype)``
---------------------------------

A common helper function used to create the conversion key in ``infotodict``.

--------------------
``filter_files(fl)``
--------------------

A utility function used to filter any input files.

If this function is included, every file found will go through this filter. Any
files where this function returns ``True`` will be filtered out.

--------------------------
``filter_dicom(dcm_data)``
--------------------------

A utility function used to filter any DICOMs.

If this function is included, every DICOM found will go through this filter. Any
DICOMs where this function returns ``True`` will be filtered out.

-------------------------------
``infotoids(seqinfos, outdir)``
-------------------------------

Further processing on ``seqinfos`` to deduce/customize subject, session, and locator.

A dictionary of {"locator": locator, "session": session, "subject": subject} is returned.

---------------------------------------------------------------
``grouping`` string or ``grouping(files, dcmfilter, seqinfo)``
---------------------------------------------------------------

Whenever ``--grouping custom`` (``-g custom``) is used, this attribute or callable
will be used to inform how to group the DICOMs into separate groups. From
`original PR#359 <https://github.com/nipy/heudiconv/pull/359>`_::

    grouping = 'AcquisitionDate'

or::

    def grouping(files, dcmfilter, seqinfo):
        seqinfos = collections.OrderedDict()
        ...
        return seqinfos  # ordered dict containing seqinfo objects: list of DICOMs


-------------------------------
``POPULATE_INTENDED_FOR_OPTS``
-------------------------------

Dictionary to specify options to populate the ``'IntendedFor'`` field of the ``fmap``
jsons.

When a BIDS session has ``fmaps``, they can automatically be assigned to be used for
susceptibility distortion correction of other non-``fmap`` images in the session
(populating the ``'IntendedFor'`` field in the ``fmap`` json file).

For this automated assignment, ``fmaps`` are taken as groups (``_phase`` and ``_phasediff``
images and the corresponding ``_magnitude`` images; consecutive Spin-Echo images collected
with opposite phase encoding polarity (``pepolar`` case); etc.).

This is achieved by checking, for every non-``fmap`` image in the session, which ``fmap``
groups are suitable candidates to correct for distortions in that image.  Then, if there is
more than one candidate (e.g., if there was a ``fmap`` collected at the beginning of the
session and another one at the end), the user can specify which one to use.

The parameters that can be specified and the allowed options are defined in ``bids.py``:
 - ``'matching_parameter'``: The imaging parameter that needs to match between the ``fmap``
   and an image for the ``fmap`` to be considered as a suitable to correct that image.
   Allowed options are:

   * ``'Shims'``: ``heudiconv`` will check the ``ShimSetting`` in the ``.json`` files and
     will only assign ``fmaps`` to images if the ``ShimSettings`` are identical for both.
   * ``'ImagingVolume'``: both ``fmaps`` and images will need to have the same the imaging
     volume (the header affine transformation: position, orientation and voxel size, as well
     as number of voxels along each dimensions).
   * ``'ModalityAcquisitionLabel'``: it checks for what modality (``anat``, ``func``, ``dwi``) each
     ``fmap`` is intended by checking the ``_acq-`` label in the ``fmap`` filename and finding
     corresponding modalities (e.g. ``_acq-fmri``, ``_acq-bold`` and ``_acq-func`` will be matched
     with the ``func`` modality)
   * ``'CustomAcquisitionLabel'``: it checks for what modality images each  ``fmap`` is intended
     by checking the ``_acq-`` custom label (e.g. ``_acq-XYZ42``) in the ``fmap`` filename, and
     matching it with:
     - the corresponding modality image ``_acq-`` label for modalities other than ``func``
     (e.g. ``_acq-XYZ42`` for ``dwi`` images)
     - the corresponding image ``_task-`` label for the ``func`` modality (e.g. ``_task-XYZ42``)
   * ``'Force'``: forces ``heudiconv`` to consider any ``fmaps`` in the session to be
     suitable for any image, no matter what the imaging parameters are.


 - ``'criterion'``: Criterion to decide which of the candidate ``fmaps`` will be assigned to
   a given file, if there are more than one. Allowed values are:

   * ``'First'``: The first matching ``fmap``.
   * ``'Closest'``: The closest in time to the beginning of the image acquisition.

.. note::
  Example::

    POPULATE_INTENDED_FOR_OPTS = {
            'matching_parameters': ['ImagingVolume', 'Shims'],
            'criterion': 'Closest'
    }

If ``POPULATE_INTENDED_FOR_OPTS`` is not present in the heuristic file, ``IntendedFor``
will not be populated automatically.
