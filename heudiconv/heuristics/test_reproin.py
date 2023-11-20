#
# Tests for reproin.py
#
from __future__ import annotations

import re
from typing import NamedTuple
from unittest.mock import patch

import pytest

from . import reproin
from .reproin import (
    filter_files,
    fix_canceled_runs,
    fix_dbic_protocol,
    fixup_subjectid,
    get_dups_marked,
    get_unique,
    md5sum,
    parse_series_spec,
    sanitize_str,
)


class FakeSeqInfo(NamedTuple):
    accession_number: str
    study_description: str
    field1: str
    field2: str


def test_get_dups_marked() -> None:
    no_dups: dict[tuple[str, tuple[str, ...], None], list[int]] = {
        ("some", ("foo",), None): [1]
    }
    assert get_dups_marked(no_dups) == no_dups

    info: dict[tuple[str, tuple[str, ...], None], list[int | str]] = {
        ("bu", ("du",), None): [1, 2],
        ("smth", (), None): [3],
        ("smth2", ("apple", "banana"), None): ["a", "b", "c"],
    }

    assert (
        get_dups_marked(info)
        == get_dups_marked(info, True)
        == {
            ("bu__dup-01", ("du",), None): [1],
            ("bu", ("du",), None): [2],
            ("smth", (), None): [3],
            ("smth2__dup-01", ("apple", "banana"), None): ["a"],
            ("smth2__dup-02", ("apple", "banana"), None): ["b"],
            ("smth2", ("apple", "banana"), None): ["c"],
        }
    )

    assert get_dups_marked(info, per_series=False) == {
        ("bu__dup-01", ("du",), None): [1],
        ("bu", ("du",), None): [2],
        ("smth", (), None): [3],
        ("smth2__dup-02", ("apple", "banana"), None): ["a"],
        ("smth2__dup-03", ("apple", "banana"), None): ["b"],
        ("smth2", ("apple", "banana"), None): ["c"],
    }


def test_filter_files() -> None:
    # Filtering is currently disabled -- any sequence directory is Ok
    assert filter_files("/home/mvdoc/dbic/09-run_func_meh/0123432432.dcm")
    assert filter_files("/home/mvdoc/dbic/run_func_meh/012343143.dcm")


def test_md5sum() -> None:
    assert md5sum("cryptonomicon") == "1cd52edfa41af887e14ae71d1db96ad1"
    assert md5sum("mysecretmessage") == "07989808231a0c6f522f9d8e34695794"


def test_fix_canceled_runs() -> None:
    class FakeSeqInfo(NamedTuple):
        accession_number: str
        series_id: str
        protocol_name: str
        series_description: str

    seqinfo: list[FakeSeqInfo] = []
    runname = "func_run+"
    for i in range(1, 6):
        seqinfo.append(
            FakeSeqInfo("accession1", "{0:02d}-".format(i) + runname, runname, runname)
        )

    fake_accession2run = {"accession1": ["^01-", "^03-"]}

    with patch.object(reproin, "fix_accession2run", fake_accession2run):
        seqinfo_ = fix_canceled_runs(seqinfo)  # type: ignore[arg-type]

    for i, s in enumerate(seqinfo_, 1):
        output = runname
        if i == 1 or i == 3:
            output = "cancelme_" + output
        for key in ["series_description", "protocol_name"]:
            value = getattr(s, key)
            assert value == output
        # check we didn't touch series_id
        assert s.series_id == "{0:02d}-".format(i) + runname


def test_fix_dbic_protocol() -> None:
    accession_number = "A003"
    seq1 = FakeSeqInfo(
        accession_number,
        "mystudy",
        "02-anat-scout_run+_MPR_sag",
        "11-func_run-life2_acq-2mm692",
    )
    seq2 = FakeSeqInfo(accession_number, "mystudy", "nochangeplease", "nochangeeither")

    seqinfos = [seq1, seq2]
    protocols2fix = {
        md5sum("mystudy"): [
            (r"scout_run\+", "THESCOUT-runX"),
            ("run-life[0-9]", "run+_task-life"),
        ],
        re.compile("^my.*"): [("THESCOUT-runX", "THESCOUT")],
        # rely on 'catch-all' to fix up above scout
        "": [("THESCOUT", "scout")],
    }

    with patch.object(reproin, "protocols2fix", protocols2fix), patch.object(
        reproin, "series_spec_fields", ["field1"]
    ):
        seqinfos_ = fix_dbic_protocol(seqinfos)  # type: ignore[arg-type]
    assert seqinfos[1] == seqinfos_[1]  # type: ignore[comparison-overlap]
    # field2 shouldn't have changed since I didn't pass it
    assert seqinfos_[0] == FakeSeqInfo(  # type: ignore[comparison-overlap]
        accession_number, "mystudy", "02-anat-scout_MPR_sag", seq1.field2
    )

    # change also field2 please
    with patch.object(reproin, "protocols2fix", protocols2fix), patch.object(
        reproin, "series_spec_fields", ["field1", "field2"]
    ):
        seqinfos_ = fix_dbic_protocol(seqinfos)  # type: ignore[arg-type]
    assert seqinfos[1] == seqinfos_[1]  # type: ignore[comparison-overlap]
    # now everything should have changed
    assert seqinfos_[0] == FakeSeqInfo(  # type: ignore[comparison-overlap]
        accession_number,
        "mystudy",
        "02-anat-scout_MPR_sag",
        "11-func_run+_task-life_acq-2mm692",
    )


def test_sanitize_str() -> None:
    assert sanitize_str("super@duper.faster") == "superduperfaster"
    assert sanitize_str("perfect") == "perfect"
    assert sanitize_str("never:use:colon:!") == "neverusecolon"


def test_fixupsubjectid() -> None:
    assert fixup_subjectid("abra") == "abra"
    assert fixup_subjectid("sub") == "sub"
    assert fixup_subjectid("sid") == "sid"
    assert fixup_subjectid("sid000030") == "sid000030"
    assert fixup_subjectid("sid0000030") == "sid000030"
    assert fixup_subjectid("sid00030") == "sid000030"
    assert fixup_subjectid("sid30") == "sid000030"
    assert fixup_subjectid("SID30") == "sid000030"


def test_parse_series_spec() -> None:
    pdpn = parse_series_spec

    assert pdpn("nondbic_func-bold") == {}
    assert pdpn("cancelme_func-bold") == {}

    assert (
        pdpn("bids_func-bold")
        == pdpn("func-bold")
        == {"datatype": "func", "datatype_suffix": "bold"}
    )

    # pdpn("bids_func_ses+_task-boo_run+") == \
    # order and PREFIX: should not matter, as well as trailing spaces
    assert (
        pdpn(" PREFIX:bids_func_ses+_task-boo_run+  ")
        == pdpn("PREFIX:bids_func_ses+_task-boo_run+")
        == pdpn("WIP func_ses+_task-boo_run+")
        == pdpn("bids_func_ses+_run+_task-boo")
        == {
            "datatype": "func",
            # 'datatype_suffix': 'bold',
            "session": "+",
            "run": "+",
            "task": "boo",
        }
    )

    # TODO: fix for that
    assert (
        pdpn("bids_func-pace_ses-1_task-boo_acq-bu_bids-please_run-2__therest")
        == pdpn("bids_func-pace_ses-1_run-2_task-boo_acq-bu_bids-please__therest")
        == pdpn("func-pace_ses-1_task-boo_acq-bu_bids-please_run-2")
        == {
            "datatype": "func",
            "datatype_suffix": "pace",
            "session": "1",
            "run": "2",
            "task": "boo",
            "acq": "bu",
            "bids": "bids-please",
        }
    )

    assert pdpn("bids_anat-scout_ses+") == {
        "datatype": "anat",
        "datatype_suffix": "scout",
        "session": "+",
    }

    assert pdpn("anat_T1w_acq-MPRAGE_run+") == {
        "datatype": "anat",
        "run": "+",
        "acq": "MPRAGE",
        "datatype_suffix": "T1w",
    }

    # Check for currently used {date}, which should also should get adjusted
    # from (date) since Philips does not allow for {}
    assert (
        pdpn("func_ses-{date}")
        == pdpn("func_ses-(date)")
        == {"datatype": "func", "session": "{date}"}
    )

    assert pdpn("fmap_dir-AP_ses-01") == {
        "datatype": "fmap",
        "session": "01",
        "dir": "AP",
    }


def test_get_unique() -> None:
    accession_number = "A003"
    acqs = [
        FakeSeqInfo(accession_number, "mystudy", "nochangeplease", "nochangeeither"),
        FakeSeqInfo(accession_number, "mystudy2", "nochangeplease", "nochangeeither"),
    ]

    assert get_unique(acqs, "accession_number") == accession_number  # type: ignore[arg-type]
    with pytest.raises(AssertionError) as ce:
        get_unique(acqs, "study_description")  # type: ignore[arg-type]
    assert (
        str(ce.value)
        == "Was expecting a single value for attribute 'study_description' but got: mystudy, mystudy2"
    )
