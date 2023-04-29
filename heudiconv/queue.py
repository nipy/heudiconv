from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Optional

from nipype.utils.filemanip import which

lgr = logging.getLogger(__name__)


def queue_conversion(
    queue: str, iterarg: str, iterables: int, queue_args: Optional[str] = None
) -> None:
    """
    Write out conversion arguments to file and submit to a job scheduler.
    Parses `sys.argv` for heudiconv arguments.

    Parameters
    ----------
    queue: string
        Batch scheduler to use
    iterarg: str
        Multi-argument to index (`subjects` OR `files`)
    iterables: int
        Number of `iterarg` arguments
    queue_args: string (optional)
        Additional queue arguments for job submission

    """

    SUPPORTED_QUEUES = {"SLURM": "sbatch"}
    if queue not in SUPPORTED_QUEUES:
        raise NotImplementedError("Queuing with %s is not supported", queue)

    for i in range(iterables):
        args = clean_args(sys.argv[1:], iterarg, i)
        # make arguments executable
        heudiconv_exec = which("heudiconv") or "heudiconv"
        args.insert(0, heudiconv_exec)
        convertcmd = " ".join(args)

        # will overwrite across subjects
        queue_file = os.path.abspath("heudiconv-%s.sh" % queue)
        with open(queue_file, "wt") as fp:
            fp.write("#!/bin/bash\n")
            if queue_args:
                for qarg in queue_args.split():
                    fp.write("#SBATCH %s\n" % qarg)
            fp.write(convertcmd + "\n")

        cmd = [SUPPORTED_QUEUES[queue], queue_file]
        subprocess.call(cmd)
    lgr.info("Submitted %d jobs", iterables)


def clean_args(hargs: list[str], iterarg: str, iteridx: int) -> list[str]:
    """
    Filters arguments for batch submission.

    Parameters
    ----------
    hargs: list
        Command-line arguments
    iterarg: str
        Multi-argument to index (`subjects` OR `files`)
    iteridx: int
        `iterarg` index to submit

    Returns
    -------
    cmdargs : list
        Filtered arguments for batch submission

    Example
    --------
    >>> from heudiconv.queue import clean_args
    >>> cmd = ['heudiconv', '-d', '/some/{subject}/path',
    ...                     '-q', 'SLURM',
    ...                     '-s', 'sub-1', 'sub-2', 'sub-3', 'sub-4']
    >>> clean_args(cmd, 'subjects', 0)
    ['heudiconv', '-d', '/some/{subject}/path', '-s', 'sub-1']
    """

    if iterarg == "subjects":
        iterargs = ["-s", "--subjects"]
    elif iterarg == "files":
        iterargs = ["--files"]
    else:
        raise ValueError("Cannot index %s" % iterarg)

    # remove these or cause an infinite loop
    queue_args = ["-q", "--queue", "--queue-args"]

    # control variables for multi-argument parsing
    is_iterarg = False
    itercount = 0

    indices = []
    cmdargs = hargs[:]

    for i, arg in enumerate(hargs):
        if arg.startswith("-") and is_iterarg:
            # moving on to another argument
            is_iterarg = False
        if is_iterarg:
            if iteridx != itercount:
                indices.append(i)
            itercount += 1
        if arg in iterargs:
            is_iterarg = True
        if arg in queue_args:
            indices.extend([i, i + 1])

    for j in sorted(indices, reverse=True):
        del cmdargs[j]
    return cmdargs
