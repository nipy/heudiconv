from pathlib import Path
import warnings

import pytest

from heudiconv.cli.run import main
from heudiconv.tests.utils import TESTS_DATA_PATH


@pytest.mark.ai_generated
@pytest.mark.parametrize("input_mode", ["files", "template"])
@pytest.mark.parametrize(
    "hook,keep,legacy_warning",
    [
        (
            "def filter_dicoms(dcm_data):\n    return dcm_data.Modality == 'MR'\n",
            True,
            False,
        ),
        (
            "def filter_dicoms(dcm_data):\n    return dcm_data.Modality != 'MR'\n",
            False,
            False,
        ),
        (
            "def filter_dicom(dcm_data):\n    return dcm_data.Modality != 'MR'\n",
            True,
            True,
        ),
        (
            "def filter_dicom(dcm_data):\n    return dcm_data.Modality == 'MR'\n",
            False,
            True,
        ),
        (
            "def filter_dicoms(dcm_data):\n    return False\n"
            "def filter_dicom(dcm_data):\n    raise AssertionError('legacy hook called')\n",
            False,
            False,
        ),
    ],
    ids=["keep", "drop", "legacy-keep", "legacy-drop", "prefer-new"],
)
def test_dicom_filter_hooks(
    tmp_path: Path, input_mode: str, hook: str, keep: bool, legacy_warning: bool
) -> None:
    # A unique module name keeps load_heuristic's normal import cache isolated.
    heuristic = tmp_path / (tmp_path.name.replace("-", "_") + "_heuristic.py")
    heuristic.write_text(
        "from heudiconv.heuristics.convertall import infotodict\n" + hook,
        encoding="utf-8",
    )
    output = tmp_path / "output"
    source = Path(TESTS_DATA_PATH) / "axasc35.dcm"
    args = ["-f", str(heuristic), "-o", str(output), "-s", "test", "-c", "none"]
    if input_mode == "files":
        args += ["--files", str(source)]
    else:
        subject_dir = tmp_path / "test"
        subject_dir.mkdir()
        (subject_dir / "sample.dcm").write_bytes(source.read_bytes())
        args += ["-d", str(tmp_path / "{subject}" / "*.dcm")]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        main(args)
    rows = sum(
        len(table.read_text().splitlines()) - 1
        for table in output.rglob("dicominfo*.tsv")
    )
    assert rows == int(keep)
    assert (
        any(
            isinstance(w.message, DeprecationWarning)
            and "filter_dicom" in str(w.message)
            for w in caught
        )
        is legacy_warning
    )
