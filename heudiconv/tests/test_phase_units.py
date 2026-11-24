import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import pytest

from heudiconv.bids import HEUDICONV_VERSION_JSON_KEY, tuneup_bids_json_files
from heudiconv.tests.utils import TESTS_DATA_PATH
from heudiconv.utils import load_json


@pytest.fixture
def converter_metadata(tmp_path: Path) -> dict[str, Any]:
    subprocess.run(
        [
            "dcm2niix",
            "-b",
            "y",
            "-z",
            "n",
            "-s",
            "y",
            "-f",
            "converted",
            "-o",
            str(tmp_path),
            str(Path(TESTS_DATA_PATH) / "axasc35.dcm"),
        ],
        check=True,
        capture_output=True,
    )
    metadata = load_json(tmp_path / "converted.json")
    assert isinstance(metadata, dict)
    return metadata


@pytest.mark.ai_generated
@pytest.mark.skipif(shutil.which("dcm2niix") is None, reason="requires dcm2niix")
@pytest.mark.parametrize(
    "filename,existing,expected",
    [
        ("sub-01_echo-1_part-phase_MEGRE.json", None, "arbitrary"),
        ("sub-01_task-rest_part-phase_bold.json", "rad", "rad"),
        ("sub-01_part-phase_T1w.json", "arbitrary", "arbitrary"),
        ("sub-01_part-mag_MEGRE.json", None, None),
        ("sub-01_phasediff.json", "rad", "rad"),
        ("sub-01_acq-part-phase_MEGRE.json", None, None),
    ],
)
def test_phase_units(
    tmp_path: Path,
    converter_metadata: dict[str, Any],
    filename: str,
    existing: str | None,
    expected: str | None,
) -> None:
    # Vary the final BIDS name and units deliberately; the remaining metadata
    # comes from the bundled DICOM and the real converter.
    metadata = converter_metadata
    metadata.pop("Units", None)
    if existing is not None:
        metadata["Units"] = existing
    path = tmp_path / filename
    path.write_text(json.dumps(metadata))

    tuneup_bids_json_files([str(path)])

    actual = json.loads(path.read_text())
    assert actual.get("Units") == expected
    for key in ("ImageType", "RepetitionTime", "EchoTime"):
        assert actual.get(key) == metadata.get(key)
    assert HEUDICONV_VERSION_JSON_KEY in actual
