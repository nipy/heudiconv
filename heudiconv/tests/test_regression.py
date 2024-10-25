"""Testing conversion with conversion saved on datalad"""
from __future__ import annotations

from glob import glob
import os
import os.path as op
from pathlib import Path
import re
from typing import Optional

import pydicom as dcm
import pytest

from heudiconv.cli.run import main as runner
from heudiconv.parser import find_files
from heudiconv.utils import load_json

# testing utilities
from .utils import TESTS_DATA_PATH, fetch_data, gen_heudiconv_args

have_datalad = True
try:
    from datalad.support.exceptions import IncompleteResultsError
except ImportError:
    have_datalad = False


@pytest.mark.skipif(not have_datalad, reason="no datalad")
@pytest.mark.parametrize("subject", ["sid000143"])
@pytest.mark.parametrize("heuristic", ["reproin.py"])
@pytest.mark.parametrize("anon_cmd", [None, "anonymize_script.py"])
def test_conversion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    subject: str,
    heuristic: str,
    anon_cmd: Optional[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    try:
        datadir = fetch_data(
            tmp_path,
            "dbic/QA",  # path from datalad database root
            getpath=op.join("sourcedata", f"sub-{subject}"),
        )
    except IncompleteResultsError as exc:
        pytest.skip("Failed to fetch test data: %s" % str(exc))
    outdir = tmp_path / "out"
    outdir.mkdir()

    args = gen_heudiconv_args(
        datadir,
        str(outdir),
        subject,
        heuristic,
        anon_cmd,
        template="sourcedata/sub-{subject}/*/*/*.tgz",
        xargs=["--datalad"],
    )
    runner(args)  # run conversion

    # Get the possibly anonymized subject id and verify that it was
    # anonymized or not:
    subjects_maybe_anon = glob(f"{outdir}/sub-*")
    assert len(subjects_maybe_anon) == 1  # just one should be there
    subject_maybe_anon = op.basename(subjects_maybe_anon[0])[4:]

    if anon_cmd:
        assert subject_maybe_anon != subject
    else:
        assert subject_maybe_anon == subject

    # verify functionals were converted
    outfiles = sorted(
        [
            f[len(str(outdir)) :]
            for f in glob(f"{outdir}/sub-{subject_maybe_anon}/func/*")
        ]
    )
    assert outfiles
    datafiles = sorted(
        [f[len(datadir) :] for f in glob(f"{datadir}/sub-{subject}/ses-*/func/*")]
    )
    # original data has ses- but because we are converting only func, and not
    # providing any session, we will not "match". Let's strip away the session
    datafiles = [re.sub(r"[/\\_]ses-[^/\\_]*", "", f) for f in datafiles]
    if not anon_cmd:
        assert outfiles == datafiles
    else:
        assert outfiles != datafiles  # sid was anonymized
        assert len(outfiles) == len(datafiles)  # but we have the same number of files

    # compare some json metadata
    json_ = "{}/task-rest_acq-24mm64sl1000tr32te600dyn_bold.json".format
    orig, conv = (load_json(json_(datadir)), load_json(json_(outdir)))
    keys = ["EchoTime", "MagneticFieldStrength", "Manufacturer", "SliceTiming"]
    for key in keys:
        assert orig[key] == conv[key]

    # validate sensitive marking
    from datalad.api import Dataset

    ds = Dataset(outdir)
    all_meta = dict(ds.repo.get_metadata("."))
    target_rec = {"distribution-restrictions": ["sensitive"]}
    for pth, meta in all_meta.items():
        if "anat" in pth or "scans.tsv" in pth:
            assert meta == target_rec
        else:
            assert meta == {}


@pytest.mark.skipif(not have_datalad, reason="no datalad")
def test_multiecho(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    subject: str = "MEEPI",
    heuristic: str = "bids_ME.py",
) -> None:
    monkeypatch.chdir(tmp_path)
    try:
        datadir = fetch_data(tmp_path, "dicoms/velasco/MEEPI")
    except IncompleteResultsError as exc:
        pytest.skip("Failed to fetch test data: %s" % str(exc))

    outdir = tmp_path / "out"
    outdir.mkdir()
    args = gen_heudiconv_args(datadir, str(outdir), subject, heuristic)
    runner(args)  # run conversion

    # check if we have echo functionals
    echoes = glob(op.join("out", "sub-" + subject, "func", "*echo*nii.gz"))
    assert len(echoes) == 3

    # check EchoTime of each functional
    # ET1 < ET2 < ET3
    prev_echo = 0
    for echo in sorted(echoes):
        _json = echo.replace(".nii.gz", ".json")
        assert _json
        echotime = load_json(_json).get("EchoTime", None)
        assert echotime > prev_echo
        prev_echo = echotime

    events = glob(op.join("out", "sub-" + subject, "func", "*events.tsv"))
    for event in events:
        assert "echo-" not in event


@pytest.mark.parametrize("subject", ["merged"])
def test_grouping(tmp_path: Path, subject: str) -> None:
    dicoms = [op.join(TESTS_DATA_PATH, fl) for fl in ["axasc35.dcm", "phantom.dcm"]]
    # ensure DICOMs are different studies
    studyuids = {
        dcm.dcmread(fl, stop_before_pixels=True).StudyInstanceUID for fl in dicoms
    }
    assert len(studyuids) == len(dicoms)
    # symlink to common location
    outdir = tmp_path / "out"
    outdir.mkdir()
    datadir = tmp_path / subject
    datadir.mkdir()
    for fl in dicoms:
        os.symlink(fl, datadir / op.basename(fl))

    template = op.join("{subject}/*.dcm")
    hargs = gen_heudiconv_args(
        str(tmp_path), str(outdir), subject, "convertall.py", template=template
    )

    with pytest.raises(AssertionError):
        runner(hargs)

    # group all found DICOMs under subject, despite conflicts
    hargs += ["-g", "all"]
    runner(hargs)
    assert (
        len(
            list(
                find_files(
                    rf"(^|{re.escape(os.sep)})run0",
                    str(outdir),
                    exclude_vcs=False,
                    dirs=True,
                )
            )
        )
        == 4
    )
    tsv = outdir / "participants.tsv"
    assert tsv.exists()
    lines = tsv.open().readlines()
    assert len(lines) == 2
    assert lines[1].split("\t")[0] == "sub-{}".format(subject)
