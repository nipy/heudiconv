from __future__ import annotations

import csv
from io import StringIO
import logging
import os
import os.path as op
from os.path import join as opj
from pathlib import Path
import stat
from unittest.mock import patch

import pytest

from heudiconv import __version__
from heudiconv.bids import (
    SCANS_FILE_FIELDS,
    add_participant_record,
    add_rows_to_scans_keys_file,
    find_subj_ses,
    get_formatted_scans_key_row,
    populate_bids_templates,
)
from heudiconv.cli.run import main as runner
from heudiconv.external.dlad import MIN_VERSION, add_to_datalad
from heudiconv.main import process_extra_commands, workflow
from heudiconv.utils import create_file_if_missing, is_readonly, load_json, set_readonly

from .utils import TESTS_DATA_PATH


@patch("sys.stdout", new_callable=StringIO)
def test_main_help(stdout: StringIO) -> None:
    with pytest.raises(SystemExit):
        runner(["--help"])
    assert stdout.getvalue().startswith("usage: ")


@patch("sys.stdout", new_callable=StringIO)
def test_main_version(std: StringIO) -> None:
    with pytest.raises(SystemExit):
        runner(["--version"])
    assert std.getvalue().rstrip() == __version__


def test_create_file_if_missing(tmp_path: Path) -> None:
    tf = tmp_path / "README.txt"
    assert not tf.exists()
    create_file_if_missing(str(tf), "content")
    assert tf.exists()
    assert tf.read_text() == "content"
    create_file_if_missing(str(tf), "content2")
    # nothing gets changed
    assert tf.read_text() == "content"


def test_populate_bids_templates(tmp_path: Path) -> None:
    populate_bids_templates(str(tmp_path), defaults={"Acknowledgements": "something"})
    for f in "README", "dataset_description.json", "CHANGES":
        # Just test that we have created them and they all have stuff TODO
        assert "TODO" in (tmp_path / f).read_text()
    description_file = tmp_path / "dataset_description.json"
    assert "something" in description_file.read_text()

    # it should also be available as a command
    description_file.unlink()

    # it must fail if no heuristic was provided
    with pytest.raises(ValueError) as cme:
        runner(["--command", "populate-templates", "--files", str(tmp_path)])
    assert str(cme.value).startswith("Specify heuristic using -f. Known are:")
    assert "convertall," in str(cme.value)
    assert not description_file.exists()

    runner(
        [
            "--command",
            "populate-templates",
            "-f",
            "convertall",
            "--files",
            str(tmp_path),
        ]
    )
    assert "something" not in description_file.read_text()
    assert "TODO" in description_file.read_text()

    assert load_json(tmp_path / "scans.json") == SCANS_FILE_FIELDS


def test_add_participant_record(tmp_path: Path) -> None:
    tf = tmp_path / "participants.tsv"
    assert not tf.exists()
    add_participant_record(str(tmp_path), "sub01", "023Y", "M")
    # should create the file and place corrected record
    sub01 = tf.read_text()
    assert (
        sub01
        == """\
participant_id	age	sex	group
sub-sub01	23	M	control
"""
    )
    add_participant_record(str(tmp_path), "sub01", "023Y", "F")
    assert tf.read_text() == sub01  # nothing was added even though differs in values
    add_participant_record(str(tmp_path), "sub02", "2", "F")
    assert (
        tf.read_text()
        == """\
participant_id	age	sex	group
sub-sub01	23	M	control
sub-sub02	2	F	control
"""
    )


def test_prepare_for_datalad(tmp_path: Path) -> None:
    pytest.importorskip("datalad", minversion=MIN_VERSION)
    studydir = tmp_path / "PI" / "study"
    studydir_ = str(studydir)
    os.makedirs(studydir_)
    populate_bids_templates(studydir_)

    add_to_datalad(str(tmp_path), studydir_, None, None)

    from datalad.api import Dataset

    superds = Dataset(tmp_path)

    assert superds.is_installed()
    assert not superds.repo.dirty
    subdss = superds.subdatasets(recursive=True, result_xfm="relpaths")
    for ds_path in sorted(subdss):
        ds = Dataset(opj(superds.path, ds_path))
        assert ds.is_installed()
        assert not ds.repo.dirty

    # the last one should have been the study
    target_files = {
        ".bidsignore",
        ".gitattributes",
        ".datalad/config",
        ".datalad/.gitattributes",
        "dataset_description.json",
        "scans.json",
        "CHANGES",
        "README",
    }
    assert set(ds.repo.get_indexed_files()) == target_files
    # and all are under git
    for f in target_files:
        assert not ds.repo.is_under_annex(f)
    assert not ds.repo.is_under_annex(".gitattributes")

    # Above call to add_to_datalad does not create .heudiconv subds since
    # directory does not exist (yet).
    # Let's first check that it is safe to call it again
    add_to_datalad(str(tmp_path), studydir_, None, None)
    assert not ds.repo.dirty

    old_hexsha = ds.repo.get_hexsha()
    # Now let's check that if we had previously converted data so that
    # .heudiconv was not a submodule, we still would not fail
    dsh_path = os.path.join(ds.path, ".heudiconv")
    dummy_path = os.path.join(dsh_path, "dummy.nii.gz")

    create_file_if_missing(dummy_path, "")
    ds.save(dummy_path, message="added a dummy file")
    # next call must not fail, should just issue a warning
    add_to_datalad(str(tmp_path), studydir_, None, None)
    ds.repo.is_under_annex(dummy_path)
    assert not ds.repo.dirty
    assert ".heudiconv/dummy.nii.gz" in ds.repo.get_files()

    # Let's now roll back and make it a proper submodule
    ds.repo.call_git(["reset", "--hard", old_hexsha])
    # now we do not add dummy to git
    create_file_if_missing(dummy_path, "")
    add_to_datalad(str(tmp_path), studydir_, None, None)
    assert ".heudiconv" in ds.subdatasets(result_xfm="relpaths")
    assert not ds.repo.dirty
    assert ".heudiconv/dummy.nii.gz" not in ds.repo.get_files()


def test_get_formatted_scans_key_row() -> None:
    dcm_fn = (
        "%s/01-fmap_acq-3mm/1.3.12.2.1107.5.2.43.66112.2016101409263663466202201.dcm"
        % TESTS_DATA_PATH
    )

    row1 = get_formatted_scans_key_row(dcm_fn)
    assert len(row1) == 3
    assert row1[0] == "2016-10-14T09:26:34.692500"
    assert row1[1] == "n/a"
    prandstr1 = row1[2]

    # if we rerun - should be identical!
    row2 = get_formatted_scans_key_row(dcm_fn)
    prandstr2 = row2[2]
    assert prandstr1 == prandstr2
    assert row1 == row2
    # So it is consistent across pythons etc, we use explicit value here
    assert prandstr1 == "437fe57c"

    # but the prandstr should change when we consider another DICOM file
    row3 = get_formatted_scans_key_row("%s/01-anat-scout/0001.dcm" % TESTS_DATA_PATH)
    assert row3 != row1
    prandstr3 = row3[2]
    assert prandstr1 != prandstr3
    assert prandstr3 == "fae3befb"


# TODO: finish this
def test_add_rows_to_scans_keys_file(tmp_path: Path) -> None:
    fn = opj(tmp_path, "file.tsv")
    rows = {
        "my_file.nii.gz": ["2016adsfasd", "", "fasadfasdf"],
        "another_file.nii.gz": ["2018xxxxx", "", "fasadfasdf"],
    }
    add_rows_to_scans_keys_file(fn, rows)

    def _check_rows(fn: str, rows: dict[str, list[str]]) -> None:
        with open(fn, "r") as csvfile:
            reader = csv.reader(csvfile, delimiter="\t")
            rows_loaded = []
            for row in reader:
                rows_loaded.append(row)
        for i, row_ in enumerate(rows_loaded):
            if i == 0:
                assert row_ == ["filename", "acq_time", "operator", "randstr"]
            else:
                assert rows[row_[0]] == row_[1:]
        # dates, filename should be sorted (date "first", filename "second")
        dates = [(r[1], r[0]) for r in rows_loaded[1:]]
        assert dates == sorted(dates)

    _check_rows(fn, rows)
    # we no longer produce a sidecar .json file there and only generate
    # it while populating templates for BIDS
    assert not op.exists(opj(tmp_path, "file.json"))
    # add a new one
    extra_rows = {
        "a_new_file.nii.gz": ["2016adsfasd23", "", "fasadfasdf"],
        "my_file.nii.gz": ["2016adsfasd", "", "fasadfasdf"],
        "another_file.nii.gz": ["2018xxxxx", "", "fasadfasdf"],
    }
    add_rows_to_scans_keys_file(fn, extra_rows)
    _check_rows(fn, extra_rows)


def test__find_subj_ses() -> None:
    assert find_subj_ses(
        "950_bids_test4/sub-phantom1sid1/fmap/"
        "sub-phantom1sid1_acq-3mm_phasediff.json"
    ) == ("phantom1sid1", None)
    assert find_subj_ses("sub-s1/ses-s1/fmap/sub-s1_ses-s1_acq-3mm_phasediff.json") == (
        "s1",
        "s1",
    )
    assert find_subj_ses("sub-s1/ses-s1/fmap/sub-s1_ses-s1_acq-3mm_phasediff.json") == (
        "s1",
        "s1",
    )
    assert find_subj_ses("fmap/sub-01-fmap_acq-3mm_acq-3mm_phasediff.nii.gz") == (
        "01",
        None,
    )


def test_make_readonly(tmp_path: Path) -> None:
    # we could test it all without torturing a poor file, but for going all
    # the way, let's do it on a file
    path = tmp_path / "f"
    pathname = str(path)
    with open(pathname, "w"):
        pass

    for orig, ro, rw in [
        (0o600, 0o400, 0o600),  # fully returned
        (0o624, 0o404, 0o606),  # it will not get write bit where it is not readable
        (0o1777, 0o1555, 0o1777),  # and other bits should be preserved
    ]:
        os.chmod(pathname, orig)
        assert not is_readonly(pathname)
        assert set_readonly(pathname) == ro
        assert is_readonly(pathname)
        assert stat.S_IMODE(os.lstat(pathname).st_mode) == ro
        # and it should go back if we set it back to non-read_only
        assert set_readonly(pathname, read_only=False) == rw
        assert not is_readonly(pathname)


def test_cache(tmp_path: Path) -> None:
    args = [
        "-f",
        "convertall",
        "--files",
        f"{TESTS_DATA_PATH}/axasc35.dcm",
        "-s",
        "S01",
        "-o",
        str(tmp_path),
    ]
    runner(args)

    cachedir = tmp_path / ".heudiconv" / "S01" / "info"
    assert cachedir.exists()

    # check individual files
    assert (cachedir / "heuristic.py").exists()
    assert (cachedir / "filegroup.json").exists()
    assert (cachedir / "dicominfo.tsv").exists()
    assert (cachedir / "S01.auto.txt").exists()
    assert (cachedir / "S01.edit.txt").exists()

    # check dicominfo has "time" as last column:
    with open(cachedir / "dicominfo.tsv", "r") as f:
        cols = f.readline().split()
    assert cols[26] == "time"


def test_no_etelemetry() -> None:
    # smoke test at large - just verifying that no crash if no etelemetry
    # must not fail if etelemetry no found
    with patch.dict("sys.modules", {"etelemetry": None}):
        workflow(outdir="/dev/null", command="ls", heuristic="reproin", files=[])


# Test two scenarios:
# -study without sessions
# -study with sessions
# The "expected_folder" is the session folder without the tmpdir
@pytest.mark.parametrize(
    "session, expected_folder",
    [("", "foo/sub-{sID}"), ("pre", "foo/sub-{sID}/ses-pre")],
)
def test_populate_intended_for(
    tmp_path: Path, session: str, expected_folder: str, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Tests for "process_extra_commands" when the command is
    'populate-intended-for'
    """
    # Because the function .utils.populate_intended_for already has its own
    # tests, here we just test that "process_extra_commands", when 'command'
    # is 'populate_intended_for' does what we expect (loop through the list of
    # subjects and calls 'populate_intended_for' using the 'POPULATE_INTENDED_FOR_OPTS'
    # defined in the heuristic file 'example.py'). We call it using folders
    # that don't exist, and check that the output is the expected.
    bids_folder = expected_folder.split("sub-")[0]
    subjects = ["1", "2"]
    caplog.set_level(logging.INFO)
    process_extra_commands(
        bids_folder,
        "populate-intended-for",
        [],
        "example",
        session,
        subjects,
        "all",
    )
    for s in subjects:
        expected_info = (
            'Adding "IntendedFor" to the fieldmaps in ' + expected_folder.format(sID=s)
        )
        assert any(expected_info in co.message for co in caplog.records)

    # try the same, but without specifying the subjects or the session.
    # the code in main should find any subject in the output folder and call
    # populate_intended_for on each of them (or for each of the sessions, if
    # the data for that subject is organized in sessions):
    # TODO: Add a 'participants.tsv' file with one of the subjects missing;
    #  the 'process_extra_commands' call should print out a warning
    caplog.clear()
    outdir = opj(tmp_path, bids_folder)
    for subj in subjects:
        subj_dir = opj(outdir, "sub-" + subj)
        print("Creating output dir: %s", subj_dir)
        os.makedirs(subj_dir)
        if session:
            os.makedirs(opj(subj_dir, "ses-" + session))
    process_extra_commands(
        outdir, "populate-intended-for", [], "example", None, [], "all"
    )
    for s in subjects:
        expected_info = 'Adding "IntendedFor" to the fieldmaps in ' + opj(
            tmp_path, expected_folder.format(sID=s)
        )
        assert any(expected_info in co.message for co in caplog.records)
