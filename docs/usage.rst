=====
Usage
=====

``heudiconv`` processes DICOM files and converts the output into user defined 
paths.

CommandLine Arguments
======================

.. argparse::
   :ref: heudiconv.cli.run.get_parser
   :prog: heudiconv
   :nodefault:
   :nodefaultconst:
   

Support
=======

All bugs, concerns and enhancement requests for this software can be submitted here:
https://github.com/nipy/heudiconv/issues.

If you have a problem or would like to ask a question about how to use ``heudiconv``,
please submit a question to `NeuroStars.org <http://neurostars.org/tags/heudiconv>`_ with a ``heudiconv`` tag.
NeuroStars.org is a platform similar to StackOverflow but dedicated to neuroinformatics.

All previous ``heudiconv`` questions are available here:
http://neurostars.org/tags/heudiconv/


Batch example
=============

``heudiconv`` can greatly facilitate large scale conversions


*******************************************************************************************
*******************************************************************************************
*******************************************************************************************
*******************************************************************************************

Call `heudiconv` like this:

    heudiconv -d '{subject}*.tar*' -s xx05 -f ~/myheuristics/convertall.py

where `-d '{subject}*tar*'` is an expression used to find DICOM files
(`{subject}` expands to a subject ID so that the expression will match any
`.tar` files, compressed or not that start with the subject ID in their name).
An additional flag for session (`{session}`) can be included in the expression
as well. `-s od05` specifies a subject ID for the conversion (this could be a
list of multiple IDs), and `-f ~/myheuristics/convertall.py` identifies a
heuristic implementation for this conversion (see below) for details.

This call will locate the DICOMs (in any number of matching tarballs), extract
them to a temporary directory, search for any DICOM series it can find, and
attempts a conversion storing output in the current directory. The output
directory will contain a subdirectory per subject, which in turn contains an
`info` directory with a full protocol of detected DICOM series, and how their
are converted.


To generate lean BIDS output, consider using both the `-b` and the `--minmeta` flags
to your heudiconv command. The `-b` flag generates a json file with BIDS keys, while
the `--minmeta` flag restricts the json file to only BIDS keys. Without `--minmeta`,
the json file and the associated Nifti file contains DICOM metadata extracted using
dicomstack.
