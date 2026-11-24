from pathlib import Path

import pytest

from heudiconv.bids import populate_bids_templates


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "existing", [None, "README", "README.md", "README.txt", "README.rst"]
)
def test_readme_guidance_preserves_existing_files(
    tmp_path: Path, existing: str | None
) -> None:
    if existing:
        (tmp_path / existing).write_text("Study-specific information\n")
    populate_bids_templates(str(tmp_path))
    if existing:
        assert (tmp_path / existing).read_text() == "Study-specific information\n"
        assert list(tmp_path.glob("README*")) == [tmp_path / existing]
    else:
        content = (tmp_path / "README").read_text()
        assert "bids-starter-kit" in content
        assert "participants" in content
        assert "acquisition" in content
        assert "DataLad" in content
        populate_bids_templates(str(tmp_path))
        assert (tmp_path / "README").read_text() == content
