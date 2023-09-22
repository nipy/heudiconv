from __future__ import annotations

from pathlib import Path
import sys

from nipype.utils.filemanip import which
import pytest

from heudiconv.cli.run import main as runner
from heudiconv.queue import clean_args

from .utils import TESTS_DATA_PATH


@pytest.mark.skipif(bool(which("sbatch")), reason="skip a real slurm call")
@pytest.mark.parametrize(
    "hargs",
    [
        # our new way with automated grouping
        ["--files", f"{TESTS_DATA_PATH}/01-fmap_acq-3mm"],
        # "old" way specifying subject
        ["-d", f"{TESTS_DATA_PATH}/{{subject}}/*", "-s", "01-fmap_acq-3mm"],
    ],
)
def test_queue_no_slurm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, hargs: list[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    hargs.extend(["-f", "reproin", "-b", "--minmeta", "--queue", "SLURM"])

    # simulate command-line call
    monkeypatch.setattr(sys, "argv", ["heudiconv"] + hargs)

    with pytest.raises(OSError):  # SLURM should not be installed
        runner(hargs)
    # should have generated a slurm submission script
    slurm_cmd_file = str(tmp_path / "heudiconv-SLURM.sh")
    assert slurm_cmd_file
    # check contents and ensure args match
    with open(slurm_cmd_file) as fp:
        lines = fp.readlines()
    assert lines[0] == "#!/bin/bash\n"
    cmd = lines[1]

    # check that all flags we gave still being called
    for arg in hargs:
        # except --queue <queue>
        if arg in ["--queue", "SLURM"]:
            assert arg not in cmd
        else:
            assert arg in cmd


def test_argument_filtering() -> None:
    cmd_files = [
        "heudiconv",
        "--files",
        "/fake/path/to/files",
        "/another/fake/path",
        "-f",
        "convertall",
        "-q",
        "SLURM",
        "--queue-args",
        "--cpus-per-task=4 --contiguous --time=10",
    ]
    filtered = [
        "heudiconv",
        "--files",
        "/another/fake/path",
        "-f",
        "convertall",
    ]
    assert clean_args(cmd_files, "files", 1) == filtered

    cmd_subjects = [
        "heudiconv",
        "-d",
        "/some/{subject}/path",
        "--queue",
        "SLURM",
        "--subjects",
        "sub1",
        "sub2",
        "sub3",
        "sub4",
        "-f",
        "convertall",
    ]
    filtered = [
        "heudiconv",
        "-d",
        "/some/{subject}/path",
        "--subjects",
        "sub3",
        "-f",
        "convertall",
    ]
    assert clean_args(cmd_subjects, "subjects", 2) == filtered
