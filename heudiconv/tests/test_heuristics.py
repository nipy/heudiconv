from __future__ import annotations

import csv
from glob import glob
from io import StringIO
import logging
import os
import os.path as op
from os.path import dirname
from os.path import join as pjoin
from pathlib import Path
import re
from unittest.mock import patch

import pytest

from heudiconv.cli.run import main as runner

from .utils import TESTS_DATA_PATH
from .. import __version__
from ..bids import HEUDICONV_VERSION_JSON_KEY
from ..utils import load_json

lgr = logging.getLogger(__name__)

try:
    from datalad.api import Dataset
except ImportError:  # pragma: no cover
    Dataset = None


# this will fail if not in project's root directory
def test_smoke_convertall(tmp_path: Path) -> None:
    args = [
        "-c",
        "dcm2niix",
        "-o",
        str(tmp_path),
        "-b",
        "--datalad",
        "-s",
        "fmap_acq-3mm",
        "-d",
        f"{TESTS_DATA_PATH}/{{subject}}/*",
    ]

    # complain if no heurisitic
    with pytest.raises(RuntimeError):
        runner(args)

    args.extend(["-f", "convertall"])
    runner(args)


@pytest.mark.parametrize("heuristic", ["reproin", "convertall"])
@pytest.mark.parametrize(
    "invocation",
    [
        ["--files", TESTS_DATA_PATH],  # our new way with automated grouping
        ["-d", f"{TESTS_DATA_PATH}/{{subject}}/*", "-s", "01-fmap_acq-3mm"],
        # "old" way specifying subject
        # should produce the same results
    ],
)
@pytest.mark.skipif(Dataset is None, reason="no datalad")
def test_reproin_largely_smoke(tmp_path: Path, heuristic: str, invocation: str) -> None:
    is_bids = True if heuristic == "reproin" else False
    args = [
        "--random-seed",
        "1",
        "-f",
        heuristic,
        "-c",
        "dcm2niix",
        "-o",
        str(tmp_path),
    ]
    if is_bids:
        args.append("-b")
    args.append("--datalad")
    args.extend(invocation)

    # Test some safeguards
    if invocation[0] == "--files":
        # Multiple subjects must not be specified -- only a single one could
        # be overridden from the command line
        with pytest.raises(ValueError):
            runner(args + ["--subjects", "sub1", "sub2"])

        if heuristic != "reproin":
            # if subject is not overridden, raise error
            with pytest.raises(NotImplementedError):
                runner(args)
            return

    runner(args)
    ds = Dataset(tmp_path)
    assert ds.is_installed()
    assert not ds.repo.dirty
    head = ds.repo.get_hexsha()

    # and if we rerun -- should fail
    lgr.info(
        "RERUNNING, expecting to FAIL since the same everything "
        "and -c specified so we did conversion already"
    )
    with pytest.raises(RuntimeError):
        runner(args)

    # but there should be nothing new
    assert not ds.repo.dirty
    # TODO: remove whenever https://github.com/datalad/datalad/issues/6843
    # is fixed/released
    buggy_datalad = (ds.pathobj / ".gitmodules").read_text().splitlines().count(
        '[submodule "Halchenko"]'
    ) > 1
    assert head == ds.repo.get_hexsha() or buggy_datalad

    # unless we pass 'overwrite' flag
    runner(args + ["--overwrite"])
    # but result should be exactly the same, so it still should be clean
    # and at the same commit
    assert ds.is_installed()
    assert not ds.repo.dirty
    assert head == ds.repo.get_hexsha() or buggy_datalad


@pytest.mark.parametrize(
    "invocation",
    [
        ["--files", TESTS_DATA_PATH],  # our new way with automated grouping
    ],
)
def test_scans_keys_reproin(tmp_path: Path, invocation: list[str]) -> None:
    args = ["-f", "reproin", "-c", "dcm2niix", "-o", str(tmp_path), "-b"]
    args += invocation
    runner(args)
    # for now check it exists
    scans_keys = glob(pjoin(tmp_path, "*/*/*/*/*/*.tsv"))
    assert len(scans_keys) == 1
    with open(scans_keys[0]) as f:
        reader = csv.reader(f, delimiter="\t")
        for i, row in enumerate(reader):
            if i == 0:
                assert row == ["filename", "acq_time", "operator", "randstr"]
            assert len(row) == 4
            if i != 0:
                assert os.path.exists(pjoin(dirname(scans_keys[0]), row[0]))
                assert re.match(
                    r"^[\d]{4}-[\d]{2}-[\d]{2}T[\d]{2}:[\d]{2}:[\d]{2}.[\d]{6}$", row[1]
                )


@patch("sys.stdout", new_callable=StringIO)
def test_ls(stdout: StringIO) -> None:
    args = ["-f", "reproin", "--command", "ls", "--files", TESTS_DATA_PATH]
    runner(args)
    out = stdout.getvalue()
    assert "StudySessionInfo(locator=" in out
    assert "Halchenko/Yarik/950_bids_test4" in out


def test_scout_conversion(tmp_path: Path) -> None:
    args = ["-b", "-f", "reproin", "--files", TESTS_DATA_PATH, "-o", str(tmp_path)]
    runner(args)

    dspath = tmp_path / "Halchenko/Yarik/950_bids_test4"
    sespath = dspath / "sub-phantom1sid1/ses-localizer"

    assert not (sespath / "anat").exists()
    assert (
        dspath / "sourcedata/sub-phantom1sid1/ses-localizer/"
        "anat/sub-phantom1sid1_ses-localizer_scout.dicom.tgz"
    ).exists()

    # Let's do some basic checks on produced files
    j = load_json(
        sespath / "fmap/sub-phantom1sid1_ses-localizer_acq-3mm_phasediff.json"
    )
    # We store HeuDiConv version in each produced .json file
    # TODO: test that we are not somehow overwriting that version in existing
    # files which we have not produced in a particular run.
    assert j[HEUDICONV_VERSION_JSON_KEY] == __version__


@pytest.mark.parametrize(
    "bidsoptions",
    [
        ["notop"],
        [],
    ],
)
def test_notop(tmp_path: Path, bidsoptions: list[str]) -> None:
    args = [
        "-f",
        "reproin",
        "--files",
        TESTS_DATA_PATH,
        "-o",
        str(tmp_path),
        "-b",
    ] + bidsoptions
    runner(args)

    assert op.exists(pjoin(tmp_path, "Halchenko/Yarik/950_bids_test4"))
    for fname in [
        "CHANGES",
        "dataset_description.json",
        "participants.tsv",
        "README",
        "participants.json",
    ]:
        if "notop" in bidsoptions:
            assert not op.exists(
                pjoin(tmp_path, "Halchenko/Yarik/950_bids_test4", fname)
            )
        else:
            assert op.exists(pjoin(tmp_path, "Halchenko/Yarik/950_bids_test4", fname))


def test_phoenix_doc_conversion(tmp_path: Path) -> None:
    subID = "Phoenix"
    args = [
        "-c",
        "dcm2niix",
        "-o",
        str(tmp_path),
        "-b",
        "-f",
        "bids_PhoenixReport",
        "--files",
        pjoin(TESTS_DATA_PATH, "Phoenix"),
        "-s",
        subID,
    ]
    runner(args)

    # check that the Phoenix document has been extracted (as gzipped dicom) in
    # the sourcedata/misc folder:
    assert op.exists(
        pjoin(tmp_path, "sourcedata", "sub-%s", "misc", "sub-%s_phoenix.dicom.tgz")
        % (subID, subID)
    )
    # check that no "sub-<subID>/misc" folder has been created in the BIDS
    # structure:
    assert not op.exists(pjoin(tmp_path, "sub-%s", "misc") % subID)
