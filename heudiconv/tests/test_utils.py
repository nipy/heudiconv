from __future__ import annotations

from datetime import datetime
import io
import json
from json.decoder import JSONDecodeError
import logging
import os
import os.path as op
from pathlib import Path
from typing import IO, Any
from unittest.mock import patch

import pydicom as dcm
import pytest

from heudiconv.utils import (
    _safe_tar_members,
    as_finite_positive_float,
    create_tree,
    get_datetime,
    get_heuristic_description,
    get_known_heuristics_with_descriptions,
    json_dumps_pretty,
    load_heuristic,
    load_json,
    remove_prefix,
    remove_suffix,
    safe_extract_tar,
    sanitize_path,
    save_json,
    strptime_bids,
    strptime_dcm_da_tm,
    strptime_dcm_dt,
    strptime_micr,
    update_json,
)

from .utils import HEURISTICS_PATH


def test_get_known_heuristics_with_descriptions() -> None:
    d = get_known_heuristics_with_descriptions()
    assert {"reproin", "convertall"}.issubset(d)
    # ATM we include all, not only those two
    assert len(d) > 2
    assert len(d["reproin"]) > 50  # it has a good one
    assert len(d["reproin"].split(os.sep)) == 1  # but just one line


def test_get_heuristic_description() -> None:
    desc = get_heuristic_description("reproin", full=True)
    assert len(desc) > 1000
    # and we describe such details as
    assert "_ses-" in desc
    assert "_run-" in desc
    # and mention ReproNim ;)
    assert "ReproNim" in desc


def test_load_heuristic() -> None:
    by_name = load_heuristic("reproin")
    from_file = load_heuristic(op.join(HEURISTICS_PATH, "reproin.py"))

    assert by_name
    assert by_name.filename == from_file.filename

    with pytest.raises(ImportError):
        load_heuristic("unknownsomething")

    with pytest.raises(ImportError):
        load_heuristic(op.join(HEURISTICS_PATH, "unknownsomething.py"))


def test_json_dumps_pretty() -> None:
    pretty = json_dumps_pretty
    assert (
        pretty({"SeriesDescription": "Trace:Nov 13 2017 14-36-14 EST"})
        == '{\n  "SeriesDescription": "Trace:Nov 13 2017 14-36-14 EST"\n}'
    )
    assert pretty({}) == "{}"
    assert (
        pretty({"a": -1, "b": "123", "c": [1, 2, 3], "d": ["1.0", "2.0"]})
        == '{\n  "a": -1,\n  "b": "123",\n  "c": [1, 2, 3],\n  "d": ["1.0", "2.0"]\n}'
    )
    assert (
        pretty({"a": ["0.3", "-1.9128906358217845e-12", "0.2"]})
        == '{\n  "a": ["0.3", "-1.9128906358217845e-12", "0.2"]\n}'
    )
    # original, longer string
    tstr = (
        "f9a7d4be-a7d7-47d2-9de0-b21e9cd10755||"
        "Sequence: ve11b/master r/50434d5; "
        "Mar  3 2017 10:46:13 by eja"
    )
    # just the date which reveals the issue
    # tstr = 'Mar  3 2017 10:46:13 by eja'
    assert pretty({"WipMemBlock": tstr}) == '{\n  "WipMemBlock": "%s"\n}' % tstr


def test_load_json(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    # test invalid json
    ifname = "invalid.json"
    invalid_json_file = str(tmp_path / ifname)
    create_tree(str(tmp_path), {ifname: "I'm Jason Bourne"})

    with pytest.raises(JSONDecodeError):
        load_json(str(invalid_json_file))

    # and even if we ask to retry a few times -- should be the same
    with pytest.raises(JSONDecodeError):
        load_json(str(invalid_json_file), retry=3)

    with pytest.raises(FileNotFoundError):
        load_json("absent123not.there", retry=3)

    assert ifname in caplog.text

    # test valid json
    vcontent = {"secret": "spy"}
    vfname = "valid.json"
    valid_json_file = str(tmp_path / vfname)
    save_json(valid_json_file, vcontent)

    assert load_json(valid_json_file) == vcontent

    calls = [0]
    json_load = json.load

    def json_load_patched(fp: IO[str]) -> Any:
        calls[0] += 1
        if calls[0] == 1:
            # just reuse bad file
            load_json(str(invalid_json_file))
        elif calls[0] == 2:
            raise FileNotFoundError()
        else:
            return json_load(fp)

    with patch.object(json, "load", json_load_patched):
        assert load_json(valid_json_file, retry=3) == vcontent


def test_update_json(tmp_path: Path) -> None:
    """
    Test utils.update_json()
    """
    dummy_json_file = str(tmp_path / "dummy.json")
    some_content = {"name": "Jason", "age": 30, "city": "New York"}
    save_json(dummy_json_file, some_content, pretty=True)

    added_content = {
        "LastName": "Bourne",
        "Movies": [
            "The Bourne Identity",
            "The Bourne Supremacy",
            "The Bourne Ultimatum",
            "The Bourne Legacy",
            "Jason Bourne",
        ],
    }
    update_json(dummy_json_file, added_content)

    # check that it was added:
    with open(dummy_json_file) as f:
        data = json.load(f)
    some_content.update(added_content)
    assert data == some_content


def test_get_datetime() -> None:
    """
    Test utils.get_datetime()
    """
    assert get_datetime("20200512", "162130") == "2020-05-12T16:21:30"
    assert get_datetime("20200512", "162130.5") == "2020-05-12T16:21:30.500000"
    assert (
        get_datetime("20200512", "162130.5", microseconds=False)
        == "2020-05-12T16:21:30"
    )


@pytest.mark.parametrize(
    "dt, fmt",
    [
        ("20230310190100", "%Y%m%d%H%M%S"),
        ("2023-04-02T11:47:09", "%Y-%m-%dT%H:%M:%S"),
    ],
)
def test_strptime_micr(dt: str, fmt: str) -> None:
    with pytest.warns(DeprecationWarning):
        target = datetime.strptime(dt, fmt)
        assert strptime_micr(dt, fmt) == target
        assert strptime_micr(dt, fmt + "[.%f]") == target
        assert strptime_micr(dt + ".0", fmt + "[.%f]") == target
        assert strptime_micr(dt + ".000000", fmt + "[.%f]") == target
        assert strptime_micr(dt + ".1", fmt + "[.%f]") == datetime.strptime(
            dt + ".1", fmt + ".%f"
        )


@pytest.mark.parametrize(
    "dt, fmt",
    [
        ("2023-04-02T11:47:09", "%Y-%m-%dT%H:%M:%S"),
        ("2023-04-02T11:47:09.0", "%Y-%m-%dT%H:%M:%S.%f"),
        ("2023-04-02T11:47:09.000000", "%Y-%m-%dT%H:%M:%S.%f"),
        ("2023-04-02T11:47:09.1", "%Y-%m-%dT%H:%M:%S.%f"),
        ("2023-04-02T11:47:09-0900", "%Y-%m-%dT%H:%M:%S%z"),
        ("2023-04-02T11:47:09.1-0900", "%Y-%m-%dT%H:%M:%S.%f%z"),
    ],
)
def test_strptime_bids(dt: str, fmt: str) -> None:
    target = datetime.strptime(dt, fmt)
    assert strptime_bids(dt) == target


@pytest.mark.parametrize(
    "tm, tm_fmt",
    [
        ("114709.1", "%H%M%S.%f"),
        ("114709", "%H%M%S"),
        ("1147", "%H%M"),
        ("11", "%H"),
    ],
)
@pytest.mark.parametrize(
    "offset, offset_fmt",
    [
        ("-0900", "%z"),
        ("", ""),
    ],
)
def test_strptime_dcm_da_tm(tm: str, tm_fmt: str, offset: str, offset_fmt: str) -> None:
    da = "20230402"
    da_fmt = "%Y%m%d"
    target = datetime.strptime(da + tm + offset, da_fmt + tm_fmt + offset_fmt)
    ds = dcm.dataset.Dataset()
    ds["AcquisitionDate"] = dcm.DataElement("AcquisitionDate", "DA", da)
    ds["AcquisitionTime"] = dcm.DataElement("AcquisitionTime", "TM", tm)
    if offset:
        ds[(0x0008, 0x0201)] = dcm.DataElement((0x0008, 0x0201), "SH", offset)
    assert strptime_dcm_da_tm(ds, "AcquisitionDate", "AcquisitionTime") == target


@pytest.mark.parametrize(
    "dt, dt_fmt",
    [
        ("20230402114709.1-0400", "%Y%m%d%H%M%S.%f%z"),
        ("20230402114709-0400", "%Y%m%d%H%M%S%z"),
        ("202304021147-0400", "%Y%m%d%H%M%z"),
        ("2023040211-0400", "%Y%m%d%H%z"),
        ("20230402-0400", "%Y%m%d%z"),
        ("202304-0400", "%Y%m%z"),
        ("2023-0400", "%Y%z"),
        ("20230402114709.1", "%Y%m%d%H%M%S.%f"),
        ("20230402114709", "%Y%m%d%H%M%S"),
        ("202304021147", "%Y%m%d%H%M"),
        ("2023040211", "%Y%m%d%H"),
        ("20230402", "%Y%m%d"),
        ("202304", "%Y%m"),
        ("2023", "%Y"),
    ],
)
@pytest.mark.parametrize(
    "offset, offset_fmt",
    [
        ("-0900", "%z"),
        ("", ""),
    ],
)
def test_strptime_dcm_dt(dt: str, dt_fmt: str, offset: str, offset_fmt: str) -> None:
    target = None
    if dt_fmt[-2:] == "%z" and offset:
        target = datetime.strptime(dt, dt_fmt)
    else:
        target = datetime.strptime(dt + offset, dt_fmt + offset_fmt)
    ds = dcm.dataset.Dataset()
    ds["AcquisitionDateTime"] = dcm.DataElement("AcquisitionDateTime", "DT", dt)
    if offset:
        ds[(0x0008, 0x0201)] = dcm.DataElement((0x0008, 0x0201), "SH", offset)
    assert strptime_dcm_dt(ds, "AcquisitionDateTime") == target


def test_remove_suffix() -> None:
    """
    Test utils.remove_suffix()
    """
    s = "jason.bourne"
    assert remove_suffix(s, "") == s
    assert remove_suffix(s, "foo") == s
    assert remove_suffix(s, ".bourne") == "jason"


def test_remove_prefix() -> None:
    """
    Test utils.remove_prefix()
    """
    s = "jason.bourne"
    assert remove_prefix(s, "") == s
    assert remove_prefix(s, "foo") == s
    assert remove_prefix(s, "jason") == ".bourne"


@pytest.mark.parametrize("value", ["valid-name_123", "valid/name/123"])
def test_sanitize_path_valid(value: str) -> None:
    assert sanitize_path(value) == value


@pytest.mark.parametrize(
    "value,target",
    [
        ("in valid/na   me:123*?", "in_valid/na_me_123_"),
        ("   leading-and-trailing--- ", "_leading-and-trailing---_"),
        ("!!!", "_"),
        (" ! ", "_"),
    ],
)
def test_sanitize_path_invalid(
    value: str, target: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    assert sanitize_path(value) == target
    # should log about replacements only
    assert len(caplog.records) == 1
    msg = caplog.records[0].message
    assert value in msg
    assert target in msg
    assert "contained problematic character(s)" in msg


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "value,expected",
    [
        (12.5, 12.5),
        ("3.0", 3.0),
        (0, None),
        (-1.0, None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        (None, None),
        ("not-a-number", None),
        ([1, 2], None),
    ],
)
def test_as_finite_positive_float(value: Any, expected: float | None) -> None:
    assert as_finite_positive_float(value) == expected


@pytest.mark.ai_generated
def test_safe_extract_tar(tmp_path: Path) -> None:
    import tarfile

    src = tmp_path / "src"
    src.mkdir()
    (src / "file.txt").write_text("hello")
    tarball = tmp_path / "archive.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(src / "file.txt", arcname="file.txt")

    dest = tmp_path / "dest"
    dest.mkdir()
    safe_extract_tar(str(tarball), str(dest))
    assert (dest / "file.txt").read_text() == "hello"


@pytest.mark.ai_generated
def test_safe_tar_members_rejects_escaping_members(tmp_path: Path) -> None:
    import tarfile

    dest = tmp_path / "dest"
    dest.mkdir()

    tarball = tmp_path / "evil.tar"
    with tarfile.open(tarball, "w") as tar:
        # a legitimate member
        good = tarfile.TarInfo("good.txt")
        good.size = 5
        tar.addfile(good, io.BytesIO(b"hello"))
        # absolute path
        absolute = tarfile.TarInfo("/etc/passwd")
        absolute.size = 0
        tar.addfile(absolute, io.BytesIO(b""))
        # '..' traversal
        traversal = tarfile.TarInfo("../../escaped.txt")
        traversal.size = 0
        tar.addfile(traversal, io.BytesIO(b""))
        # symlink pointing outside dest
        symlink = tarfile.TarInfo("link")
        symlink.type = tarfile.SYMTYPE
        symlink.linkname = "../../outside"
        tar.addfile(symlink)

    with tarfile.open(tarball) as tar:
        safe = _safe_tar_members(tar, str(dest))

    assert [m.name for m in safe] == ["good.txt"]


@pytest.mark.ai_generated
def test_safe_extract_tar_manual_fallback_when_filter_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # simulate a tarfile.extractall() predating the filter= backport (a
    # TypeError on that keyword), and confirm safe_extract_tar() falls
    # back to vetting members itself rather than propagating the error
    import tarfile
    import warnings

    tarball = tmp_path / "evil.tar"
    with tarfile.open(tarball, "w") as tar:
        good = tarfile.TarInfo("good.txt")
        good.size = 5
        tar.addfile(good, io.BytesIO(b"hello"))
        traversal = tarfile.TarInfo("../escaped.txt")
        traversal.size = 0
        tar.addfile(traversal, io.BytesIO(b""))

    real_extractall = tarfile.TarFile.extractall

    def _extractall_without_filter_support(
        self: tarfile.TarFile, *args: Any, **kwargs: Any
    ) -> None:
        if "filter" in kwargs:
            raise TypeError("extractall() got an unexpected keyword argument 'filter'")
        # a genuinely old tarfile also predates the DeprecationWarning
        # tarfile.extractall() emits on a *current* interpreter when no
        # filter= is given -- that warning was introduced by the very same
        # security backport that added filter= support in the first place
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            real_extractall(self, *args, **kwargs)

    monkeypatch.setattr(
        tarfile.TarFile, "extractall", _extractall_without_filter_support
    )

    dest = tmp_path / "dest"
    dest.mkdir()
    safe_extract_tar(str(tarball), str(dest))

    assert (dest / "good.txt").read_text() == "hello"
    assert not (tmp_path / "escaped.txt").exists()
