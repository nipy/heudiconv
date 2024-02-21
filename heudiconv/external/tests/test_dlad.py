from __future__ import annotations

from pathlib import Path

import pytest

from ..dlad import mark_sensitive
from ...utils import create_tree

dl = pytest.importorskip("datalad.api")


def test_mark_sensitive(tmp_path: Path) -> None:
    ds = dl.Dataset(tmp_path).create(force=True)
    create_tree(
        str(tmp_path),
        {
            "f1": "d1",
            "f2": "d2",
            "g1": "d3",
            "g2": "d1",
        },
    )
    ds.save(".")
    mark_sensitive(ds, "f*")
    all_meta = dict(ds.repo.get_metadata("."))
    target_rec = {"distribution-restrictions": ["sensitive"]}
    # g2 since the same content
    assert not all_meta.pop("g1", None)  # nothing or empty record
    assert all_meta == {"f1": target_rec, "f2": target_rec, "g2": target_rec}


def test_mark_sensitive_subset(tmp_path: Path) -> None:
    ds = dl.Dataset(tmp_path).create(force=True)
    create_tree(
        str(tmp_path),
        {
            "f1": "d1",
            "f2": "d2",
            "g1": "d3",
            "g2": "d1",
        },
    )
    ds.save(".")
    mark_sensitive(ds, "f*", [str(tmp_path / "f1")])
    all_meta = dict(ds.repo.get_metadata("."))
    target_rec = {"distribution-restrictions": ["sensitive"]}
    # g2 since the same content
    assert not all_meta.pop("g1", None)  # nothing or empty record
    assert not all_meta.pop("f2", None)  # nothing or empty record
    assert all_meta == {"f1": target_rec, "g2": target_rec}
