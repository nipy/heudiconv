=================
Custom Heuristics
=================

A heuristic maps DICOM series to output filenames. This tutorial shows how to
inspect your series, write those rules, and reuse them for other subjects and
sessions. It is adapted from `Dianne Patterson's University of Arizona tutorials
<https://neuroimaging-core-docs.readthedocs.io/en/latest/pages/heudiconv.html#lesson-3-reproin-py>`_.

Prerequisites
*************

Install :ref:`HeuDiConv and dcm2niix <install_local>` and choose a representative
subject from your own DICOM data. The examples use this input layout::

    project/
    └── dicom/
        ├── 01/
        │   ├── baseline/
        │   │   └── ... DICOM files, possibly in subdirectories ...
        │   └── followup/
        │       └── ... DICOM files ...
        └── 02/
            └── baseline/
                └── ... DICOM files ...

Run the shell commands from ``project/``, replacing paths and labels to match
your data. Each subject/session directory in this example contains one DICOM
study. These are illustrative paths, not files supplied by the quickstart.
The :doc:`tutorials` page links to public sample data if you need it.

The workflow has three steps:

1. :ref:`Inspect a representative subject <heudiconv_step1>`.
2. :ref:`Write and check a heuristic <heudiconv_step2>`.
3. :ref:`Convert subjects and sessions <heudiconv_step3>`.

.. _heudiconv_step1:

Step 1: Inspect the DICOM series
****************************************

Use the bundled ``convertall`` heuristic with the ``none`` converter to generate
conversion information without producing NIfTI files::

    heudiconv --files dicom/01/baseline -o bids -f convertall -s 01 -ss baseline -c none -b

``--files`` accepts a directory and searches its contents recursively, so this
command does not depend on a particular DICOM filename extension. ``-s`` supplies
the subject label, ``-ss`` supplies the session label, and ``-b`` selects the BIDS
layout. Use alphanumeric labels without the ``sub-`` or ``ses-`` prefixes.

Inspect ``bids/.heudiconv/01/ses-baseline/info/``. In particular:

* ``dicominfo_ses-baseline.tsv`` describes the series and the fields available to
  your heuristic, including ``series_id``, ``protocol_name``, ``series_description``,
  dimensions and ``image_type``. Open it as a tab-separated table.
* ``heuristic.py`` is a copy of the heuristic used for this run.
* ``01_ses-baseline.auto.txt`` and ``01_ses-baseline.edit.txt`` contain conversion
  assignments; ``filegroup_ses-baseline.json`` records the associated DICOM paths.

Keep your working heuristic outside this generated information directory. For
example, copy the template to ``bids/code/custom_heuristic.py`` using your file
manager, or with these shell commands::

    mkdir -p bids/code
    cp bids/.heudiconv/01/ses-baseline/info/heuristic.py bids/code/custom_heuristic.py

.. _heudiconv_step2:

Step 2: Write and check a heuristic
****************************************

Replace the copied file's rules with rules for your acquisitions. The following
complete example selects T1-weighted, diffusion-weighted and resting-state BOLD
series. **The protocol names are examples**: replace them with values you have
checked in your own ``dicominfo`` table, and add criteria when a name alone does
not distinguish the series you want.

.. code-block:: python

    def create_key(template, outtype=("nii.gz",), annotation_classes=None):
        if not template:
            raise ValueError("Template must be a valid format string")
        return template, outtype, annotation_classes


    def infotodict(seqinfo):
        t1w = create_key(
            "{bids_subject_session_dir}/anat/"
            "{bids_subject_session_prefix}_run-{item:02d}_T1w"
        )
        dwi = create_key(
            "{bids_subject_session_dir}/dwi/"
            "{bids_subject_session_prefix}_run-{item:02d}_dwi"
        )
        rest = create_key(
            "{bids_subject_session_dir}/func/"
            "{bids_subject_session_prefix}_task-rest_run-{item:02d}_bold"
        )
        info = {t1w: [], dwi: [], rest: []}
        for s in seqinfo:
            if s.protocol_name == "t1_mprage":
                info[t1w].append(s.series_id)
            elif s.protocol_name == "dwi_ap":
                info[dwi].append(s.series_id)
            elif s.protocol_name == "rest" and not s.is_motion_corrected:
                info[rest].append(s.series_id)
        return info

Each key combines an output filename template and output types. ``infotodict``
returns a dictionary mapping those keys to lists of input series identifiers.
Series that are not added to any list are not converted.

The BIDS placeholders keep paths and filenames consistent:

* ``{bids_subject_session_dir}`` becomes ``sub-01/ses-baseline`` when a session is
  supplied, or ``sub-01`` when it is omitted.
* ``{bids_subject_session_prefix}`` becomes ``sub-01_ses-baseline`` or ``sub-01``,
  respectively.
* ``{item:02d}`` numbers the entries assigned to a key, starting at ``01``. It is
  not the scanner's series number. Check that this ordering matches your study's
  intended run labels.

For example, the first T1w series for subject ``01`` at ``baseline`` is written
under ``sub-01/ses-baseline/anat/`` with the prefix
``sub-01_ses-baseline_run-01_T1w``. Add or change keys for your other acquisitions
using the `BIDS MRI specification
<https://bids-specification.readthedocs.io/en/stable/modality-specific-files/magnetic-resonance-imaging-data.html>`_.
Fieldmaps, multi-echo and complex images need rules appropriate to those
acquisitions; the three keys above are not a complete protocol for every study.
See :doc:`heuristics` for the available hooks and template fields.

Choosing criteria
=================

Use fields from the table together when necessary. For example,
``"mprage" in s.protocol_name`` tests a case-sensitive substring, whereas
``s.dim3 == 176`` tests a numerical value. Dimensions and protocol names can vary
between scanners and visits; do not copy these values without checking them.

``image_type`` is a tuple of strings, so ``"DERIVED" in s.image_type`` tests for
an entire tuple element, not a substring. Combine such checks with ``and``,
``or`` and ``not`` to distinguish original, derived, magnitude, phase or motion
corrected data as appropriate. Use parentheses to make mixed conditions clear.

Check the assignments without conversion by writing to a separate preview
directory::

    heudiconv --files dicom/01/baseline -o preview -f bids/code/custom_heuristic.py -s 01 -ss baseline -c none -b

Review the new ``*.auto.txt`` and ``*.edit.txt`` files and compare their series
identifiers with the ``dicominfo`` table. An empty assignment list means that no
series matched that key. Editing the TSV itself does not change the heuristic's
input or its assignments.

Cached conversion information
=============================

Keep ``.heudiconv`` as a record of the heuristic, assignments and source paths
used for conversion. Existing ``*.edit.txt`` assignments can be reused when the
heuristic is unchanged. If the heuristic file's contents change, HeuDiConv
detects the changed hash and regenerates the tables, including the edit file.
Preserve any manual edits you need before doing that.

Use a fresh preview output directory when you need to inspect changed input data
with the same heuristic. ``--overwrite`` permits replacing converted files; it
does not itself force regeneration of the cached assignments. There is no need
to delete the entire dataset's ``.heudiconv`` directory to try a new heuristic.

.. _heudiconv_step3:

Step 3: Convert subjects and sessions
****************************************

Once the assignments are correct, select the converter::

    heudiconv --files dicom/01/baseline -o bids -f bids/code/custom_heuristic.py -s 01 -ss baseline -c dcm2niix -b --minmeta

``-b`` requests BIDS output, including JSON sidecars and dataset templates.
``--minmeta`` omits the additional metadata extracted by dcmstack; it retains
dcm2niix's sidecar metadata. It is not a substitute for reviewing metadata before
sharing data. Fill in the generated ``README`` and ``dataset_description.json``
and check participant information, events and other study-specific metadata.

If all three example rules match one series each, the image paths include::

    bids/
    └── sub-01/
        └── ses-baseline/
            ├── anat/sub-01_ses-baseline_run-01_T1w.nii.gz
            ├── dwi/sub-01_ses-baseline_run-01_dwi.nii.gz
            └── func/sub-01_ses-baseline_task-rest_run-01_bold.nii.gz

There will also be sidecars and other BIDS files. Inspect the images, verify
their dimensions and metadata, and run the `BIDS validator
<https://bids-standard.github.io/bids-validator/>`_.
For unexpected conversion results, compare with dcm2niix run directly on the
affected series.

Process another subject or session by changing both the input path and its
labels::

    heudiconv --files dicom/02/baseline -o bids -f bids/code/custom_heuristic.py -s 02 -ss baseline -c dcm2niix -b --minmeta
    heudiconv --files dicom/01/followup -o bids -f bids/code/custom_heuristic.py -s 01 -ss followup -c dcm2niix -b --minmeta

With ``--files``, supply at most one subject label per invocation. A literal
``{subject}`` in a ``--files`` path is not expanded by HeuDiConv. For multiple
subjects in one invocation, use the separate ``-d/--dicom_dir_template`` workflow
described in :doc:`commandline`, with a template matching your actual files or
archives. Omit ``-ss`` throughout if your dataset does not use sessions; the BIDS
placeholders above handle both layouts.

Review the results for each subject: acquisition names, available series and
their order may differ. Directory names help you organize input, but do not
change DICOM header fields such as ``StudyDescription``. Keep distinct studies
separate unless your heuristic explicitly handles their identities.

Use ``--overwrite`` only when you intend to replace existing converted files.
During development, a separate output directory lets you compare results before
replacing them. Keep the working heuristic under version control alongside the
study's conversion instructions.
