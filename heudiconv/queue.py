import subprocess
import sys
import os

import logging

lgr = logging.getLogger(__name__)

def queue_conversion(pyscript, queue, studyid, queue_args=None):
    """
    Write out conversion arguments to file and submit to a job scheduler.
    Parses `sys.argv` for heudiconv arguments.

    Parameters
    ----------
    pyscript: file
        path to `heudiconv` script
    queue: string
        batch scheduler to use
    studyid: string
        identifier for conversion
    queue_args: string (optional)
        additional queue arguments for job submission

    Returns
    -------
    proc: int
        Queue submission exit code
    """

    SUPPORTED_QUEUES = {'SLURM': 'sbatch'}
    if queue not in SUPPORTED_QUEUES:
        raise NotImplementedError("Queuing with %s is not supported", queue)

    args = clean_args(sys.argv[1:])
    # make arguments executable
    args.insert(0, pyscript)
    pypath = sys.executable or "python"
    args.insert(0, pypath)
    convertcmd = " ".join(args)

    # will overwrite across subjects
    queue_file = os.path.abspath('heudiconv-%s.sh' % queue)
    with open(queue_file, 'wt') as fp:
        fp.write("#!/bin/bash\n")
        if queue_args:
            for qarg in queue_args.split():
                fp.write("#SBATCH %s\n" % qarg)
        fp.write(convertcmd + "\n")

    cmd = [SUPPORTED_QUEUES[queue], queue_file]
    proc = subprocess.call(cmd)
    return proc

def clean_args(hargs, keys=['-q', '--queue', '--queue-args']):
    """
    Filters out unwanted arguments

    :param hargs: Arguments passed
    :type hargs: Iterable
    :param keys: Unwanted arguments
    :type keys: Iterable
    :return: Filtered arguments 
    """
    indicies = []
    for i, arg in enumerate(hargs):
        if arg in keys:
            indicies.extend([i, i+1])
    for j in sorted(indicies, reverse=True):
        del hargs[j]
    return hargs

