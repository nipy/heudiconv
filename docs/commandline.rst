=============
CLI Reference
=============

``heudiconv`` processes DICOM files and converts the output into user defined
paths.

Large DICOM collections
=======================

Pass a directory to ``--files`` instead of expanding every DICOM filename in
the shell. HeuDiConv searches that directory recursively. For example, preview
one subject's conversion assignments without converting images:

.. code-block:: console

   heudiconv --files "/data/dicom/01" -s 01 -f heuristic.py -o /data/bids -b -c none

Replace the paths and heuristic with your own. Choose a directory containing
the intended subject's data when supplying ``-s`` explicitly.

For a subject-based input layout, a quoted ``-d`` template lets HeuDiConv expand
the pattern after the process has started:

.. code-block:: console

   heudiconv -d "/data/dicom/{subject}/*.dcm" -s 01 -f heuristic.py -o /data/bids -b -c none

Keep the quotes around the whole template. An unquoted ``*.dcm`` can expand to
tens of thousands of shell arguments and trigger ``Argument list too long``
before HeuDiConv starts. Quoting a wildcard passed to ``--files`` is not a
substitute: use a directory with ``--files``, or a pattern with ``-d``.

These forms avoid the shell's argument limit; they do not reduce the amount of
DICOM data HeuDiConv must inspect. Keep the files belonging to each series
together. Once the preview is correct, use ``-c dcm2niix`` for conversion.

Command-line options
====================

.. argparse::
   :ref: heudiconv.cli.run.get_parser
   :prog: heudiconv
   :nodefault:
   :nodefaultconst:
