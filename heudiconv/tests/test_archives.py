from glob import glob
import os
import os.path as op
from pathlib import Path
import stat
import typing


import pytest
import shutil
from .utils import TESTS_DATA_PATH
from ..parser import get_extracted_dicoms


@pytest.fixture
def get_dicoms_gztar(tmpdir: Path) -> typing.List[str]:
    tmp_file = tmpdir / "dicom"
    archive = shutil.make_archive(
        str(tmp_file),
        format="gztar", 
        root_dir=TESTS_DATA_PATH, 
        base_dir="01-anat-scout")
    return [archive]


@pytest.fixture
def get_dicoms_zip(tmpdir: Path) -> typing.List[str]:
    tmp_file = tmpdir / "dicom"
    archive = shutil.make_archive(
        str(tmp_file),
        format="zip", 
        root_dir=TESTS_DATA_PATH, 
        base_dir="01-anat-scout")
    return [archive]


@pytest.fixture
def get_dicoms_list() -> typing.List[str]:
    return glob(op.join(TESTS_DATA_PATH, "01-anat-scout", "*"))


def test_get_extracted_dicoms_single_session_is_none(get_dicoms_gztar: typing.List[str]):
    for session_, _ in get_extracted_dicoms(get_dicoms_gztar):
        assert session_ is None


def test_get_extracted_dicoms_multple_session_integers(get_dicoms_gztar: typing.List[str]):
    sessions = []
    for session, _ in get_extracted_dicoms(get_dicoms_gztar + get_dicoms_gztar):
        sessions.append(session)

    assert sessions == [0, 1]


def test_get_extracted_dicoms_from_tgz(get_dicoms_gztar: typing.List[str]):
    for _, files in get_extracted_dicoms(get_dicoms_gztar):
        # check that the only file is the one called "0001.dcm"
        assert all(file.endswith("0001.dcm") for file in files)


def test_get_extracted_dicoms_from_zip(get_dicoms_zip: typing.List[str]):
    for _, files in get_extracted_dicoms(get_dicoms_zip):
        # check that the only file is the one called "0001.dcm"
        assert all(file.endswith("0001.dcm") for file in files)


def test_get_extracted_dicoms_from_file_list(get_dicoms_list: typing.List[str]):
    for _, files in get_extracted_dicoms(get_dicoms_list):
        assert all(op.isfile(file) for file in files)


def test_get_extracted_have_correct_permissions(get_dicoms_gztar: typing.List[str]):
    for _, files in get_extracted_dicoms(get_dicoms_gztar):
        assert all(stat.S_IMODE(os.stat(file).st_mode) == 448 for file in files)


def test_get_extracted_are_absolute(get_dicoms_gztar: typing.List[str]):
    for _, files in get_extracted_dicoms(get_dicoms_gztar):
        assert all(op.isabs(file) for file in files)


def test_get_extracted_fails_when_mixing_archive_and_unarchived(
        get_dicoms_gztar: typing.List[str],
        get_dicoms_list: typing.List[str]):
    with pytest.raises(ValueError):
        get_extracted_dicoms(get_dicoms_gztar + get_dicoms_list)
