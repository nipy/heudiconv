from pathlib import Path

import pydicom
from pydicom.uid import generate_uid
import pytest

from heudiconv.cli.run import main
from heudiconv.tests.utils import TESTS_DATA_PATH
from heudiconv.utils import load_json, read_config, write_config


@pytest.mark.ai_generated
@pytest.mark.parametrize("session", [None, "baseline"])
@pytest.mark.parametrize(
    "rerun,overwrite", [(False, False), (False, True), (True, False)]
)
def test_rerun_heuristic_uses_current_input_and_replaces_cached_edits(
    tmp_path: Path, session: str | None, rerun: bool, overwrite: bool
) -> None:
    first = Path(TESTS_DATA_PATH) / "axasc35.dcm"
    second = tmp_path / "second.dcm"
    dicom = pydicom.dcmread(first)
    # Deliberately make the bundled sample a distinct input series.
    dicom.SeriesNumber = 99
    dicom.SeriesInstanceUID = generate_uid()
    dicom.SOPInstanceUID = generate_uid()
    dicom.file_meta.MediaStorageSOPInstanceUID = dicom.SOPInstanceUID
    dicom.save_as(second)
    heuristic = tmp_path / "custom.py"
    heuristic.write_text(
        "def infotodict(seqinfo):\n"
        "    return {('sub-{subject}/anat/sub-{subject}_T1w', ('nii.gz',), None):\n"
        "            [s.series_id for s in seqinfo]}\n"
    )
    output = tmp_path / "out"
    common = [
        "-s",
        "01",
        "-f",
        str(heuristic),
        "-o",
        str(output),
        "-b",
        "notop",
        "-c",
        "none",
    ]
    if session is not None:
        common += ["--ses", session]
    main(["--files", str(first), *common])
    edit = next(output.rglob("*.edit.txt"))
    initial = read_config(str(edit))
    edited = {
        ("sub-{subject}/anat/sub-{subject}_acq-edited_T1w", ("nii.gz",), None): next(
            iter(initial.values())
        )
    }
    write_config(str(edit), edited)
    flags = (["--rerun-heuristic"] if rerun else []) + (
        ["--overwrite"] if overwrite else []
    )

    main(["--files", str(second), *common, *flags])

    table = read_config(str(edit))
    filegroup = load_json(next(output.rglob("filegroup*.json")))
    saved_files = [
        Path(filename).resolve() for files in filegroup.values() for filename in files
    ]
    assert saved_files == [(second if rerun else first).resolve()]
    if rerun:
        assert table != edited
        assert next(iter(table.values())) == list(filegroup)
        assert all(series.startswith("99-") for series in filegroup)
        assert read_config(str(next(output.rglob("*.auto.txt")))) == table
    else:
        assert table == edited
