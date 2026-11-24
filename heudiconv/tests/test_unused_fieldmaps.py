import logging
from pathlib import Path

import pytest

from heudiconv.bids import populate_intended_for
from heudiconv.tests.test_bids import create_dummy_pepolar_bids_session
from heudiconv.utils import load_json, save_json


@pytest.mark.ai_generated
@pytest.mark.parametrize("unused", ["incompatible", "unselected", None])
def test_warns_for_unused_fieldmap_groups(
    tmp_path: Path, unused: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    session = tmp_path / "sub-01" / "ses-01"
    _, expected, groups, _ = create_dummy_pepolar_bids_session(str(session))
    unused_group = "sub-01_ses-01_acq-dwi_run-2_epi"
    if unused == "incompatible":
        for filename in groups[unused_group]:
            save_json(filename, {"ShimSetting": [-1] * 6})
    elif unused is None:
        for filename in groups[unused_group]:
            Path(filename).unlink()
            expected.pop(Path(filename).name)

    with caplog.at_level(logging.WARNING, logger="heudiconv.bids"):
        populate_intended_for(str(session), "Shims", "First")

    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == (1 if unused else 0)
    if unused:
        assert unused_group in warnings[0]
        assert "IntendedFor" in warnings[0]
    for filename, targets in expected.items():
        assert load_json(str(session / "fmap" / filename)).get("IntendedFor") == targets
