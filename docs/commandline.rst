=============
CLI Reference
=============

``heudiconv`` processes DICOM files and converts the output into user defined
paths.

To inspect inputs before choosing a conversion heuristic, use::

    heudiconv --command ls --files /path/to/dicoms

Without ``-f``, this lists the DICOM study identifiers and sequence counts for
each input path. No subject identifier is required and no conversion output is
created. Directories and supported archives are expanded as for conversion;
``--grouping`` controls the grouping (``custom`` still requires a heuristic).
Supply ``-f`` to use a heuristic's subject/session identification, filters and
optional ``ls`` display hook instead.

.. argparse::
   :ref: heudiconv.cli.run.get_parser
   :prog: heudiconv
   :nodefault:
   :nodefaultconst:
