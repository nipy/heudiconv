from pathlib import Path

import pytest

from heudiconv.external.dlad import MIN_VERSION, add_to_datalad


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "existing,json_attribute",
    [
        ("*_scans.tsv annex.largefiles=anything\n", "nothing"),
        ("* annex.largefiles=(largerthan=100kb)\n", "nothing"),
        ("*.json annex.largefiles=anything\n", "anything"),
    ],
)
def test_default_attributes_preserve_specific_and_user_rules(
    tmp_path: Path, existing: str, json_attribute: str
) -> None:
    pytest.importorskip("datalad", minversion=MIN_VERSION)
    from datalad.api import create

    ds = create(tmp_path)
    attributes = tmp_path / ".gitattributes"
    with attributes.open("a") as stream:
        stream.write(existing)
    expected = {
        "sub-01/sub-01_scans.tsv": "anything",
        "participants.tsv": "nothing",
        "image.nii.gz": "anything",
        "sidecar.json": json_attribute,
        "other.dat": "(largerthan=100kb)",
    }
    for attempt in range(2):
        add_to_datalad(str(tmp_path), str(tmp_path), None, None)
        result = ds.repo.call_git(["check-attr", "annex.largefiles", "--", *expected])
        assert result.splitlines() == [
            f"{name}: annex.largefiles: {value}" for name, value in expected.items()
        ]
        if attempt == 0:
            first_content = attributes.read_bytes()
        else:
            assert attributes.read_bytes() == first_content
