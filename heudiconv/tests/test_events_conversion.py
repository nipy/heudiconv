"""Event templates belong to the current conversion, with BIDS inheritance."""

from __future__ import annotations

from pathlib import Path

import pytest

from heudiconv.bids import populate_aggregated_jsons
from heudiconv.convert import convert
from heudiconv.utils import save_json

from .utils import TESTS_DATA_PATH


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "bids_options,existing,create",
    [
        ("", None, True),
        ("notop", None, True),
        (None, None, False),
        ("", "task-rest_events.tsv", False),
        ("notop", "sub-01/sub-01_task-rest_events.tsv", False),
        ("", "sub-01/ses-01/sub-01_ses-01_task-rest_events.tsv", False),
        (
            "notop",
            "sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_events.tsv",
            False,
        ),
        ("", "task-other_events.tsv", True),
        ("notop", "task-rest_run-02_events.tsv", True),
        ("notop", "notes_events.tsv", True),
        ("", "../task-rest_events.tsv", True),
    ],
)
def test_conversion_events(
    tmp_path: Path, bids_options: str | None, existing: str | None, create: bool
) -> None:
    root = tmp_path / "bids"
    func = root / "sub-01" / "ses-01" / "func"
    func.mkdir(parents=True)
    old = root / "sub-02" / "func" / "sub-02_task-rest_bold.json"
    old.parent.mkdir(parents=True)
    save_json(old, {"RepetitionTime": 1.0, "TaskName": "rest"})
    contents = "onset\tduration\n0\t2\n"
    inherited = root / existing if existing else None
    if inherited is not None:
        inherited.parent.mkdir(parents=True, exist_ok=True)
        inherited.write_text(contents)

    prefix = func / "sub-01_ses-01_task-rest_run-01_bold"
    convert(
        [(str(prefix), ("nii.gz",), [str(Path(TESTS_DATA_PATH) / "axasc35.dcm")])],
        converter="dcm2niix",
        scaninfo_suffix=".json",
        custom_callable=None,
        with_prov=False,
        bids_options=bids_options,
        outdir=str(root),
        min_meta=True,
        overwrite=False,
    )
    assert prefix.with_suffix(".nii.gz").is_file()
    # This is the subsequent dataset-wide step, omitted by --bids notop.
    if bids_options == "":
        populate_aggregated_jsons(str(root))

    events = func / "sub-01_ses-01_task-rest_run-01_events.tsv"
    assert events.exists() == (create or events == inherited)
    if create:
        assert events.read_text().startswith("onset\tduration\t")
    if inherited is not None:
        assert inherited.read_text() == contents
    assert not old.with_name("sub-02_task-rest_events.tsv").exists()
