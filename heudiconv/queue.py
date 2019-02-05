import subprocess
import sys

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

        args = sys.argv[1:]
        print(sys.argv)
        # search args for queue flag
        for i, arg in enumerate(args):
            if arg in ["-q", "--queue"]:
                break
        if i == len(args) - 1:
            raise RuntimeError(
                "Queue flag not found (must be provided as a command-line arg)"
            )
        # remove queue flag and value
        del args[i:i+2]

        # make arguments executable again
        args.insert(0, pyscript)
        pypath = sys.executable or "python"
        args.insert(0, pypath)
        convertcmd = " ".join(args)

        # will overwrite across subjects
        queue_file = 'heudiconv-%s.sh' % queue
        with open(queue_file, 'wt') as fp:
            fp.writelines(['#!/bin/bash\n', convertcmd, '\n'])

        cmd = [SUPPORTED_QUEUES[queue], queue_file]
        if queue_args:
            cmd.insert(1, queue_args)
        proc = subprocess.call(cmd)
        return proc
