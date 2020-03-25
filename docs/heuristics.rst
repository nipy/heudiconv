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