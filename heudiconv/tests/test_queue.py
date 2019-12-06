import os
import sys
import subprocess

from heudiconv.cli.run import main as runner
from heudiconv.queue import clean_args, which
from .utils import TESTS_DATA_PATH
import pytest

@pytest.mark.skipif(bool(which("sbatch")), reason="skip a real slurm call")
@pytest.mark.parametrize(
    'invocation', [
        "--files %s/01-fmap_acq-3mm" % TESTS_DATA_PATH,    # our new way with automated groupping
        "-d %s/{subject}/* -s 01-fmap_acq-3mm" % TESTS_DATA_PATH # "old" way specifying subject
    ])
def test_queue_no_slurm(tmpdir, invocation):
    tmpdir.chdir()
    hargs = invocation.split(" ")
    hargs.extend(["-f", "reproin", "-b", "--minmeta", "--queue", "SLURM"])

    # simulate command-line call
    _sys_args = sys.argv
    sys.argv = ['heudiconv'] + hargs

    try:
        with pytest.raises(OSError):  # SLURM should not be installed
            runner(hargs)
        # should have generated a slurm submission script
        slurm_cmd_file = (tmpdir / 'heudiconv-SLURM.sh').strpath
        assert slurm_cmd_file
        # check contents and ensure args match
        with open(slurm_cmd_file) as fp:
            lines = fp.readlines()
        assert lines[0] == "#!/bin/bash\n"
        cmd = lines[1]

        # check that all flags we gave still being called
        for arg in hargs:
            # except --queue <queue>
            if arg in ['--queue', 'SLURM']:
                assert arg not in cmd
            else:
                assert arg in cmd
    finally:
        # revert before breaking something
        sys.argv = _sys_args

def test_argument_filtering(tmpdir):
    cmd_files = [
        'heudiconv',
        '--files',
        '/fake/path/to/files',
        '/another/fake/path',
        '-f',
        'convertall',
        '-q',
        'SLURM',
        '--queue-args',
        '--cpus-per-task=4 --contiguous --time=10'
    ]
    filtered = [
        'heudiconv',
        '--files',
        '/another/fake/path',
        '-f',
        'convertall',
    ]
    assert clean_args(cmd_files, 'files', 1) == filtered

    cmd_subjects = [
        'heudiconv',
        '-d',
        '/some/{subject}/path',
        '--queue',
        'SLURM',
        '--subjects',
        'sub1',
        'sub2',
        'sub3',
        'sub4',
        '-f',
        'convertall'
    ]
    filtered = [
        'heudiconv',
        '-d',
        '/some/{subject}/path',
        '--subjects',
        'sub3',
        '-f',
        'convertall'
    ]
    assert clean_args(cmd_subjects, 'subjects', 2) == filtered
