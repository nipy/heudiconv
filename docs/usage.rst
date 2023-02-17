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


Batch jobs
==========

``heudiconv`` can natively handle multi-subject, multi-session conversions
although it will do these conversions in a linear manner, i.e. one subject and one session at a time.
To speed up these conversions, multiple ``heudiconv``
processes can be spawned concurrently, each converting a different subject and/or
session.

The following example uses SLURM and Singularity to submit every subjects'
DICOMs as an independent ``heudiconv`` execution.

The first script aggregates the DICOM directories and submits them to
``run_heudiconv.sh`` with SLURM as a job array.

If using bids, the ``notop`` bids option suppresses creation of
top-level files in the bids directory (e.g.,
``dataset_description.json``) to avoid possible race conditions.
These files may be generated later with ``populate_templates.sh``
below (except for ``participants.tsv``, which must be created
manually).

.. code:: shell

    #!/bin/bash

    set -eu

    # where the DICOMs are located
    DCMROOT=/dicom/storage/voice
    # where we want to output the data
    OUTPUT=/converted/data/voice

    # find all DICOM directories that start with "voice"
    DCMDIRS=(`find ${DCMROOT} -maxdepth 1 -name voice* -type d`)

    # submit to another script as a job array on SLURM
    sbatch --array=0-`expr ${#DCMDIRS[@]} - 1` run_heudiconv.sh ${OUTPUT} ${DCMDIRS[@]}


The second script processes a DICOM directory with ``heudiconv`` using the built-in
`reproin` heuristic.

.. code:: shell

    #!/bin/bash
    set -eu

    OUTDIR=${1}
    # receive all directories, and index them per job array
    DCMDIRS=(${@:2})
    DCMDIR=${DCMDIRS[${SLURM_ARRAY_TASK_ID}]}
    echo Submitted directory: ${DCMDIR}

    IMG="/singularity-images/heudiconv-latest-dev.sif"
    CMD="singularity run -B ${DCMDIR}:/dicoms:ro -B ${OUTDIR}:/output -e ${IMG} --files /dicoms/ -o /output -f reproin -c dcm2niix -b notop --minmeta -l ."

    printf "Command:\n${CMD}\n"
    ${CMD}
    echo "Successful process"

This script creates the top-level bids files (e.g.,
``dataset_description.json``)

.. code:: shell

    #!/bin/bash
    set -eu

    OUTDIR=${1}
    IMG="/singularity-images/heudiconv-latest-dev.sif"
    CMD="singularity run -B ${OUTDIR}:/output -e ${IMG} --files /output -f reproin --command populate-templates"

    printf "Command:\n${CMD}\n"
    ${CMD}
    echo "Successful process"
