=============
CLI Reference
=============

``heudiconv`` processes DICOM files and converts the output into user defined
paths.

Working with commands
---------------------

``--command`` selects an operation instead of DICOM conversion. Commands do not
need ``-c dcm2niix``. The meaning of the input path depends on the command:

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Command
     - Input
     - Operation
   * - ``heuristics``
     - None
     - List built-in heuristics and their descriptions.
   * - ``heuristic-info``
     - ``-f`` heuristic name or file
     - Print the heuristic's full description.
   * - ``ls``
     - ``--files`` DICOM files, directories, or archives; ``-f`` required
     - List study sessions and sequence counts using the heuristic and grouping.
   * - ``populate-templates``
     - ``--files`` BIDS dataset roots; ``-f`` required
     - Create missing dataset templates and aggregate task metadata.
   * - ``populate-intended-for``
     - ``-o`` BIDS dataset root; optional ``-s``, ``-ss``, and ``-f``
     - Match fieldmaps to existing images and update their ``IntendedFor`` fields.
   * - ``sanitize-jsons``
     - ``--files`` BIDS JSON sidecars
     - Remove acquisition/study/series dates, record the HeuDiConv version, and
       fill fieldmap echo times when the matching magnitude sidecars are present.
   * - ``treat-jsons``
     - ``--files`` metadata JSON files
     - Apply HeuDiConv's metadata cleanup and formatting to those files.

Discover and inspect heuristics::

    heudiconv --command heuristics
    heudiconv --command heuristic-info -f reproin
    heudiconv --command ls -f reproin --files /path/to/dicoms

To populate templates in an existing BIDS dataset, pass its root with
``--files``. ``-o`` does not select the dataset for this command::

    heudiconv --command populate-templates -f reproin --files /path/to/bids

The heuristic's optional ``DEFAULT_FIELDS`` supplies template defaults. Review
the generated placeholders in ``dataset_description.json``, ``README``, and
``CHANGES``. Existing template files are preserved; aggregated ``task-*.json``
files may be regenerated, and missing event templates may be created.

To recompute fieldmap assignments for one subject and session::

    heudiconv --command populate-intended-for -o /path/to/bids -s 01 -ss baseline -f heuristic.py

Subject and session arguments are labels without ``sub-`` and ``ses-``. Omitting
``-s`` processes subjects found under the dataset; omitting ``-ss`` processes
their sessions, or the subject directory for sessionless data. The optional
heuristic's ``POPULATE_INTENDED_FOR_OPTS`` controls matching, as described in
:doc:`heuristics`.

The JSON commands edit the explicitly supplied files in place::

    heudiconv --command sanitize-jsons --files /path/to/bids/sub-01/anat/sub-01_T1w.json
    heudiconv --command treat-jsons --files /path/to/metadata.json

``sanitize-jsons`` is intended for conversion sidecars, not every JSON file in a
dataset. It is separate from the broader metadata normalization in
``treat-jsons``.

All options
-----------

.. argparse::
   :ref: heudiconv.cli.run.get_parser
   :prog: heudiconv
   :nodefault:
   :nodefaultconst:
