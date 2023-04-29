from __future__ import annotations

from glob import glob
import os
import os.path as op
from pathlib import Path
import shutil
import stat

import pytest

from .utils import TESTS_DATA_PATH
from ..parser import get_extracted_dicoms


def _get_dicoms_archive(tmpdir: Path, fmt: str) -> list[str]:
    tmp_file = tmpdir / "dicom"
    archive = shutil.make_archive(
        str(tmp_file), format=fmt, root_dir=TESTS_DATA_PATH, base_dir="01-anat-scout"
    )
    return [archive]


@pytest.fixture
def get_dicoms_archive(tmpdir: Path, request: pytest.FixtureRequest) -> list[str]:
    return _get_dicoms_archive(tmpdir, fmt=request.param)


@pytest.fixture
def get_dicoms_gztar(tmpdir: Path) -> list[str]:
    return _get_dicoms_archive(tmpdir, "gztar")


@pytest.fixture
def get_dicoms_list() -> list[str]:
    return glob(op.join(TESTS_DATA_PATH, "01-anat-scout", "*"))


def test_get_extracted_dicoms_single_session_is_none(
    get_dicoms_gztar: list[str],
) -> None:
    for session_, _ in get_extracted_dicoms(get_dicoms_gztar):
        assert session_ is None


def test_get_extracted_dicoms_multple_session_integers(
    get_dicoms_gztar: list[str],
) -> None:
    sessions = [
        session
        for session, _ in get_extracted_dicoms(get_dicoms_gztar + get_dicoms_gztar)
    ]

    assert sessions == ["0", "1"]


@pytest.mark.parametrize(
    "get_dicoms_archive", ("tar", "gztar", "zip", "bztar", "xztar"), indirect=True
)
def test_get_extracted_dicoms_from_archives(get_dicoms_archive: list[str]) -> None:
    for _, files in get_extracted_dicoms(get_dicoms_archive):
        # check that the only file is the one called "0001.dcm"
        endswith = all(file.endswith("0001.dcm") for file in files)

        # check that permissions were set
        mode = all(stat.S_IMODE(os.stat(file).st_mode) == 448 for file in files)

        # check for absolute paths
        absolute = all(op.isabs(file) for file in files)

        assert all([endswith, mode, absolute])


def test_get_extracted_dicoms_from_file_list(get_dicoms_list: list[str]) -> None:
    for _, files in get_extracted_dicoms(get_dicoms_list):
        assert all(op.isfile(file) for file in files)


def test_get_extracted_dicoms_from_mixed_list(
    get_dicoms_list: list[str], get_dicoms_gztar: list[str]
) -> None:
    for _, files in get_extracted_dicoms(get_dicoms_list + get_dicoms_gztar):
        assert all(op.isfile(file) for file in files)


def test_get_extracted_from_empty_list() -> None:
    assert not len(get_extracted_dicoms([]))
