from collections.abc import Iterator
import os
from pathlib import Path

import pytest

from heudiconv.parser import find_files


@pytest.mark.ai_generated
@pytest.mark.parametrize("exclude_vcs", [False, True])
@pytest.mark.parametrize("dirs", [False, True])
def test_find_files_prunes_vcs_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exclude_vcs: bool, dirs: bool
) -> None:
    vcs_names = [".git", ".hg", ".svn", ".bzr"]
    folders = ["data", "ignored", "project.git", *vcs_names]
    for folder in folders:
        nested = tmp_path / folder / "nested"
        nested.mkdir(parents=True)
        (nested / "image.dcm").touch()
    (tmp_path / ".gitattributes").touch()

    visited: list[Path] = []
    original_walk = os.walk

    def recording_walk(top: str) -> Iterator[tuple[str, list[str], list[str]]]:
        for root, directories, filenames in original_walk(top):
            visited.append(Path(root))
            yield root, directories, filenames

    monkeypatch.setattr(os, "walk", recording_walk)
    found = set(
        find_files(
            ".*",
            str(tmp_path),
            # Matching a directory itself must not implicitly hide descendants.
            exclude=r"[/\\]ignored$",
            exclude_vcs=exclude_vcs,
            dirs=dirs,
        )
    )
    included = folders[:3] if exclude_vcs else folders
    expected = {str(tmp_path / folder / "nested" / "image.dcm") for folder in included}
    if not exclude_vcs:
        expected.add(str(tmp_path / ".gitattributes"))
    if dirs:
        expected.update(str(tmp_path / folder / "nested") for folder in included)
        expected.update(
            str(tmp_path / folder) for folder in included if folder != "ignored"
        )
    assert found == expected
    assert set(visited) == {
        tmp_path,
        *(tmp_path / folder for folder in included),
        *(tmp_path / folder / "nested" for folder in included),
    }
