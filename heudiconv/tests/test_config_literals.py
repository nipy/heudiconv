"""Focused checks for cached conversion-table parsing."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from heudiconv import utils


@pytest.mark.ai_generated
@pytest.mark.parametrize("executable", [False, True])
def test_read_config_accepts_only_literals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executable: bool
) -> None:
    path = tmp_path / "conversion.edit.txt"
    sentinel = Mock(return_value={})
    monkeypatch.setattr(utils, "_config_test_sentinel", sentinel, raising=False)
    mapping = {("sub-{subject}/anat", ("nii.gz",), None): ["1", "2"]}
    if executable:
        path.write_text("_config_test_sentinel()")
        with pytest.raises(ValueError):
            utils.read_config(str(path))
    else:
        utils.write_config(str(path), mapping)
        assert utils.read_config(str(path)) == mapping
    sentinel.assert_not_called()
