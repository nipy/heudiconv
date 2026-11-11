from __future__ import annotations

import csv
from glob import glob
from io import StringIO
import json
import os
import os.path as op
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import cast

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


@pytest.fixture
def metadata_archive(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """Archive a real DICOM, either at the root or in a series directory."""
    fmt, nested = request.param
    source = tmp_path / "source"
    member = source / "series" / "image.dcm" if nested else source / "image.dcm"
    member.parent.mkdir(parents=True)
    shutil.copyfile(Path(TESTS_DATA_PATH) / "axasc35.dcm", member)
    return Path(shutil.make_archive(str(tmp_path / "S01"), fmt, root_dir=source))


def _metadata_args(archive: Path, output: Path, template: bool) -> list[str]:
    source = (
        ["-d", str(archive).replace("S01", "{subject}")]
        if template
        else ["--files", str(archive)]
    )
    return ["-f", "convertall", "-s", "S01", "-o", str(output), *source]


def _run_heudiconv(args: list[str]) -> None:
    # Each invocation has its own extraction directories and process state.
    subprocess.run(
        [sys.executable, "-m", "heudiconv.cli.run", *args],
        env=dict(os.environ, NO_ET="1"),
        check=True,
    )


@pytest.mark.ai_generated
@pytest.mark.parametrize("template", [False, True], ids=["files", "template"])
@pytest.mark.parametrize(
    "metadata_archive",
    [(fmt, nested) for fmt in ("gztar", "zip") for nested in (False, True)],
    indirect=True,
)
def test_archive_metadata_is_reproducible(
    tmp_path: Path, metadata_archive: Path, template: bool
) -> None:
    metadata = []
    for name in ("first", "second"):
        output = tmp_path / name
        _run_heudiconv(
            [*_metadata_args(metadata_archive, output, template), "-c", "none"]
        )
        info = output / ".heudiconv" / "S01" / "info"
        metadata.append(
            {
                name: (info / name).read_bytes()
                for name in ("dicominfo.tsv", "filegroup.json")
            }
        )
    assert metadata[0] == metadata[1]
    assert b"heudiconvDCM" not in metadata[0]["filegroup.json"]
    assert b"heudiconvDCM" not in metadata[0]["dicominfo.tsv"]
    rows = list(
        csv.DictReader(StringIO(metadata[0]["dicominfo.tsv"].decode()), delimiter="\t")
    )
    assert len(rows) == 1
    expected_dir = (
        "series" if (tmp_path / "source" / "series").is_dir() else metadata_archive.name
    )
    assert rows[0]["dcm_dir_name"] == expected_dir


@pytest.mark.ai_generated
@pytest.mark.parametrize("template", [False, True], ids=["files", "template"])
@pytest.mark.parametrize(
    "metadata_archive", [("gztar", False), ("zip", True)], indirect=True
)
def test_archive_cached_conversion_uses_freshly_extracted_files(
    tmp_path: Path, metadata_archive: Path, template: bool
) -> None:
    if shutil.which("dcm2niix") is None:
        pytest.skip("dcm2niix is not installed")
    import nibabel as nib
    import numpy as np

    output = tmp_path / "converted"
    args = _metadata_args(metadata_archive, output, template)
    _run_heudiconv([*args, "-c", "dcm2niix", "--minmeta"])
    original = cast(
        nib.Nifti1Image, nib.load(output / "S01" / "run001.nii.gz")
    ).get_fdata()
    info = output / ".heudiconv" / "S01" / "info"
    metadata = (info / "filegroup.json").read_bytes()
    edit_file = info / "S01.edit.txt"
    edit_file.chmod(0o600)
    edit_file.write_text(edit_file.read_text().replace("run{item", "reused{item"))

    _run_heudiconv([*args, "-c", "dcm2niix", "--minmeta"])

    converted = cast(
        nib.Nifti1Image, nib.load(output / "S01" / "reused001.nii.gz")
    ).get_fdata()
    np.testing.assert_array_equal(original, converted)
    assert (info / "filegroup.json").read_bytes() == metadata
    assert "reused{item" in edit_file.read_text()


@pytest.mark.ai_generated
def test_archive_metadata_distinguishes_archives_and_preserves_direct_paths(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copyfile(Path(TESTS_DATA_PATH) / "axasc35.dcm", source / "image.dcm")
    archives = []
    for name in ("first", "second"):
        directory = tmp_path / name
        directory.mkdir()
        archives.append(
            shutil.make_archive(str(directory / "scan"), "gztar", root_dir=source)
        )
    direct = str(Path(TESTS_DATA_PATH) / "axasc35.dcm")
    output = tmp_path / "converted"
    _run_heudiconv(
        [
            "-f",
            "convertall",
            "-s",
            "S01",
            "-o",
            str(output),
            "-c",
            "none",
            "--files",
            *archives,
            direct,
        ]
    )
    filegroup = json.loads(
        (output / ".heudiconv" / "S01" / "info" / "filegroup.json").read_text()
    )
    paths = [path for group in filegroup.values() for path in group]
    assert direct in paths
    assert set(paths) == {
        direct,
        *(str(Path(archive) / "image.dcm") for archive in archives),
    }
