"""Collect conversion provenance without replacing user dataset metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from heudiconv.bids import populate_bids_templates
from heudiconv.utils import create_tree, load_json, save_json


@pytest.mark.ai_generated
@pytest.mark.parametrize("existing", [False, True])
def test_aggregate_generated_by(tmp_path: Path, existing: bool) -> None:
    converter = {"Name": "dcm2niix", "Version": "v1.0.20241211"}
    customized = {**converter, "Container": {"Type": "docker", "Tag": "study:1"}}
    manual = {"Name": "Manual", "Description": "Reviewed by the study team"}
    descriptor = tmp_path / "dataset_description.json"
    if existing:
        save_json(
            descriptor,
            {
                "Name": "Study",
                "Authors": ["Researcher"],
                "GeneratedBy": [manual, customized],
            },
        )
    create_tree(
        str(tmp_path),
        {
            "sub-01": {
                "func": {
                    "sub-01_task-rest_bold.json": {
                        "RepetitionTime": 1.0,
                        "HeudiconvVersion": "1.0.0",
                        "ConversionSoftware": converter["Name"],
                        "ConversionSoftwareVersion": converter["Version"],
                    }
                },
                "anat": {
                    "sub-01_T1w.json": {
                        "HeudiconvVersion": "0.13.2",
                        "ConversionSoftware": converter["Name"],
                        "ConversionSoftwareVersion": converter["Version"],
                    }
                },
            }
        },
    )
    populate_bids_templates(str(tmp_path))
    metadata = load_json(descriptor)
    records = metadata["GeneratedBy"]
    expected: set[tuple[str, str | None]] = {
        ("heudiconv", "1.0.0"),
        ("heudiconv", "0.13.2"),
        ("dcm2niix", converter["Version"]),
    }
    if existing:
        expected.add(("Manual", None))
    assert {(r["Name"], r.get("Version")) for r in records} == expected
    assert len(records) == (4 if existing else 3)
    if existing:
        assert records[:2] == [manual, customized]
        assert metadata["Name"] == "Study"
        assert metadata["Authors"] == ["Researcher"]
    original = descriptor.read_bytes()
    populate_bids_templates(str(tmp_path))
    assert descriptor.read_bytes() == original
