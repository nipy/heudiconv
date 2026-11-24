from pathlib import Path
import shutil

import pytest

from heudiconv.convert import nipype_convert, save_converted_files
from heudiconv.tests.utils import TESTS_DATA_PATH
from heudiconv.utils import load_json, save_json


@pytest.mark.ai_generated
@pytest.mark.skipif(shutil.which("dcm2niix") is None, reason="requires dcm2niix")
@pytest.mark.parametrize("last_coil", [None, "", "HC3"])
def test_save_uncombined_images_with_missing_coil_metadata(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, last_coil: str | None
) -> None:
    converted = tmp_path / "converted"
    converted.mkdir()
    dicoms = [str(Path(TESTS_DATA_PATH) / "axasc35.dcm")]
    result, _ = nipype_convert(
        dicoms, str(converted / "sample"), False, "", str(tmp_path / "work")
    )
    source = Path(result.outputs.converted_files)
    expected_image = source.read_bytes()
    metadata = load_json(result.outputs.bids)
    images = []
    sidecars = []
    # Deliberately vary only the coil metadata on real converter output to
    # represent a group containing known channels and an unidentified image.
    for index, coil in enumerate(["HC1", "HC2", last_coil], 1):
        image = converted / f"channel{index}.nii.gz"
        sidecar = converted / f"channel{index}.json"
        shutil.copyfile(source, image)
        values = dict(metadata)
        values.pop("CoilString", None)
        if coil is not None:
            values["CoilString"] = coil
        save_json(sidecar, values)
        images.append(str(image))
        sidecars.append(str(sidecar))
    result.outputs.converted_files = images
    result.outputs.bids = sidecars
    output = tmp_path / "output"
    output.mkdir()
    prefix = str(output / "sub-01_T1w")

    saved = save_converted_files(
        result, dicoms, "", "nii.gz", prefix, prefix + ".json", False
    )

    expected = ["sub-01_ch-01_T1w", "sub-01_ch-02_T1w"]
    expected.append("sub-01_ch-03_T1w" if last_coil else "sub-01_T1w3")
    assert [Path(path).stem for path in saved] == expected
    for name, coil in zip(expected, ["HC1", "HC2", last_coil]):
        assert (output / (name + ".nii.gz")).read_bytes() == expected_image
        assert load_json(output / (name + ".json")).get("CoilString") == coil
    assert ("Cannot add a channel entity without CoilString" in caplog.text) == (
        not last_coil
    )
