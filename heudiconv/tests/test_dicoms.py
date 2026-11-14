from __future__ import annotations

import datetime
from glob import glob
import json
import os.path as op
from pathlib import Path
from typing import Any
import warnings

import pydicom as dcm
import pytest

from heudiconv.cli.run import main as runner
from heudiconv.convert import nipype_convert
from heudiconv.dicoms import (
    create_seqinfo,
    dw,
    embed_dicom_and_nifti_metadata,
    estimate_scan_duration_from_times,
    get_acquisition_duration,
    get_acquisition_timestamps,
    get_datetime_from_dcm,
    get_datetime_strings_from_dcm,
    get_dicom_acquisition_duration,
    get_dicom_declared_acquisition_duration,
    get_dicom_declared_repetitions,
    get_reproducible_int,
    group_dicoms_into_seqinfos,
    parse_private_csa_header,
    wrapper_from_file,
)

from .utils import TEST_DICOM_PATHS, TESTS_DATA_PATH, make_timed_dicoms

# An enhanced (multiframe) DICOM of a scout from Siemens XA30, with 3 frames,
# each in its own orientation
XA30_ENHANCED_DCM_PATH = op.join(
    TESTS_DATA_PATH,
    "MRI_102TD_PHA_S.MR.Chen_Matthews_1.3.1.2022.11.16.15.50.20.357.31204541.dcm",
)

# Public: Private DICOM tags
DICOM_FIELDS_TO_TEST = {"ProtocolName": "tProtocolName"}


def test_private_csa_header(tmp_path: Path) -> None:
    dcm_file = op.join(TESTS_DATA_PATH, "axasc35.dcm")
    dcm_data = dcm.dcmread(dcm_file, stop_before_pixels=True)
    for pub, priv in DICOM_FIELDS_TO_TEST.items():
        # ensure missing public tag
        with pytest.raises(AttributeError):
            getattr(dcm, pub)
        # ensure private tag is found
        assert parse_private_csa_header(dcm_data, pub, priv) != ""
        # and quickly run heudiconv with no conversion
        runner(
            ["--files", dcm_file, "-c", "none", "-f", "reproin", "-o", str(tmp_path)]
        )


def test_embed_dicom_and_nifti_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test dcmstack's additional fields"""
    monkeypatch.chdir(tmp_path)
    # set up testing files
    dcmfiles = [op.join(TESTS_DATA_PATH, "axasc35.dcm")]
    infofile = "infofile.json"

    out_prefix = str(tmp_path / "nifti")
    # 1) nifti does not exist -- no longer supported
    with pytest.raises(NotImplementedError):
        embed_dicom_and_nifti_metadata(dcmfiles, out_prefix + ".nii.gz", infofile, None)

    # we should produce nifti using our "standard" ways
    nipype_out, prov_file = nipype_convert(
        dcmfiles,
        prefix=out_prefix,
        with_prov=False,
        bids_options=None,
        tmpdir=str(tmp_path),
    )
    niftifile = nipype_out.outputs.converted_files

    assert op.exists(niftifile)
    # 2) nifti exists
    embed_dicom_and_nifti_metadata(dcmfiles, niftifile, infofile, None)
    assert op.exists(infofile)
    with open(infofile) as fp:
        out2 = json.load(fp)

    # 3) with existing metadata
    bids = {"existing": "data"}
    embed_dicom_and_nifti_metadata(dcmfiles, niftifile, infofile, bids)
    with open(infofile) as fp:
        out3 = json.load(fp)

    assert out3.pop("existing") == "data"
    assert out3 == out2


def test_group_dicoms_into_seqinfos() -> None:
    """Tests for group_dicoms_into_seqinfos"""

    # 1) Check that it works for PhoenixDocuments:
    # set up testing files
    dcmfolder = op.join(TESTS_DATA_PATH, "Phoenix")
    dcmfiles = glob(op.join(dcmfolder, "*", "*.dcm"))

    seqinfo = group_dicoms_into_seqinfos(dcmfiles, "studyUID", flatten=True)

    assert type(seqinfo) is dict
    assert len(seqinfo) == len(dcmfiles)
    assert [s.series_description for s in seqinfo] == [
        "AAHead_Scout_32ch-head-coil",
        "PhoenixZIPReport",
    ]


def test_custom_seqinfo() -> None:
    """Tests for custom seqinfo extraction"""

    from heudiconv.heuristics.convertall_custom import custom_seqinfo

    dcmfiles = glob(op.join(TESTS_DATA_PATH, "phantom.dcm"))

    seqinfos = group_dicoms_into_seqinfos(
        dcmfiles, "studyUID", flatten=True, custom_seqinfo=custom_seqinfo
    )  # type: ignore

    seqinfo = list(seqinfos.keys())[0]

    assert hasattr(seqinfo, "custom")
    assert isinstance(seqinfo.custom, tuple)
    assert len(seqinfo.custom) == 2
    assert seqinfo.custom[1] == dcmfiles[0]


def test_get_datetime_from_dcm_from_acq_date_time() -> None:
    typical_dcm = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )

    # do we try to grab from AcquisitionDate/AcquisitionTime first when available?
    dt = get_datetime_from_dcm(typical_dcm)
    assert dt == datetime.datetime.strptime(
        typical_dcm.get("AcquisitionDate") + typical_dcm.get("AcquisitionTime"),
        "%Y%m%d%H%M%S.%f",
    )


def test_get_datetime_from_dcm_from_acq_datetime() -> None:
    # if AcquisitionDate and AcquisitionTime not there, can we rely on AcquisitionDateTime?
    XA30_enhanced_dcm = dcm.dcmread(
        XA30_ENHANCED_DCM_PATH,
        stop_before_pixels=True,
    )
    dt = get_datetime_from_dcm(XA30_enhanced_dcm)
    assert dt == datetime.datetime.strptime(
        XA30_enhanced_dcm.get("AcquisitionDateTime"), "%Y%m%d%H%M%S.%f"
    )


def test_get_datetime_from_dcm_from_only_series_date_time() -> None:
    # if acquisition date/time/datetime not available, can we rely on SeriesDate & SeriesTime?
    XA30_enhanced_dcm = dcm.dcmread(
        XA30_ENHANCED_DCM_PATH,
        stop_before_pixels=True,
    )
    del XA30_enhanced_dcm.AcquisitionDateTime
    dt = get_datetime_from_dcm(XA30_enhanced_dcm)
    assert dt == datetime.datetime.strptime(
        XA30_enhanced_dcm.get("SeriesDate") + XA30_enhanced_dcm.get("SeriesTime"),
        "%Y%m%d%H%M%S.%f",
    )


def test_get_datetime_from_dcm_wo_dt() -> None:
    # if there's no known source (e.g., after anonymization), are we still able to proceed?
    XA30_enhanced_dcm = dcm.dcmread(
        XA30_ENHANCED_DCM_PATH,
        stop_before_pixels=True,
    )
    del XA30_enhanced_dcm.AcquisitionDateTime
    del XA30_enhanced_dcm.SeriesDate
    del XA30_enhanced_dcm.SeriesTime
    assert get_datetime_from_dcm(XA30_enhanced_dcm) is None


@pytest.mark.parametrize("dcmfile", TEST_DICOM_PATHS)
def test_create_seqinfo(
    dcmfile: str,
) -> None:
    mw = wrapper_from_file(dcmfile)
    seqinfo = create_seqinfo(mw, [dcmfile], op.basename(dcmfile))
    assert seqinfo.sequence_name


@pytest.mark.ai_generated
def test_get_datetime_strings_from_dcm_acq_date_time() -> None:
    # AcquisitionDate/AcquisitionTime are taken as is whenever both are present
    typical_dcm = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    assert get_datetime_strings_from_dcm(typical_dcm) == (
        typical_dcm.get("AcquisitionDate"),
        typical_dcm.get("AcquisitionTime"),
    )


@pytest.mark.ai_generated
def test_get_datetime_strings_from_dcm_acq_datetime() -> None:
    # https://github.com/nipy/heudiconv/issues/537 -- some DICOMs (e.g. XA30
    # enhanced ones) have only AcquisitionDateTime, and we should still be able
    # to provide date and time
    XA30_enhanced_dcm = dcm.dcmread(
        XA30_ENHANCED_DCM_PATH,
        stop_before_pixels=True,
    )
    assert "AcquisitionDate" not in XA30_enhanced_dcm
    assert "AcquisitionTime" not in XA30_enhanced_dcm

    date, time = get_datetime_strings_from_dcm(XA30_enhanced_dcm)
    acq_datetime = XA30_enhanced_dcm.get("AcquisitionDateTime")
    assert date == acq_datetime[:8]
    assert date is not None and time is not None
    assert datetime.datetime.strptime(
        date + time, "%Y%m%d%H%M%S.%f"
    ) == datetime.datetime.strptime(acq_datetime, "%Y%m%d%H%M%S.%f")


@pytest.mark.ai_generated
def test_get_datetime_strings_from_dcm_series_date_time() -> None:
    # fall back to SeriesDate/SeriesTime if no acquisition date/time/datetime
    XA30_enhanced_dcm = dcm.dcmread(
        XA30_ENHANCED_DCM_PATH,
        stop_before_pixels=True,
    )
    del XA30_enhanced_dcm.AcquisitionDateTime
    date, time = get_datetime_strings_from_dcm(XA30_enhanced_dcm)
    assert date == XA30_enhanced_dcm.get("SeriesDate")
    assert date is not None and time is not None
    assert datetime.datetime.strptime(
        date + time, "%Y%m%d%H%M%S.%f"
    ) == datetime.datetime.strptime(
        XA30_enhanced_dcm.get("SeriesDate") + XA30_enhanced_dcm.get("SeriesTime"),
        "%Y%m%d%H%M%S.%f",
    )


@pytest.mark.ai_generated
def test_get_datetime_strings_from_dcm_wo_dt() -> None:
    # no date/time information whatsoever (e.g. after anonymization) -- no error
    XA30_enhanced_dcm = dcm.dcmread(
        XA30_ENHANCED_DCM_PATH,
        stop_before_pixels=True,
    )
    del XA30_enhanced_dcm.AcquisitionDateTime
    del XA30_enhanced_dcm.SeriesDate
    del XA30_enhanced_dcm.SeriesTime
    assert get_datetime_strings_from_dcm(XA30_enhanced_dcm) == (None, None)


@pytest.mark.ai_generated
def test_get_datetime_strings_from_dcm_partial() -> None:
    # if only a date is known and nothing else -- return it with time being None
    typical_dcm = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    acq_date = typical_dcm.get("AcquisitionDate")
    del typical_dcm.AcquisitionTime
    del typical_dcm.SeriesDate
    del typical_dcm.SeriesTime
    assert get_datetime_strings_from_dcm(typical_dcm) == (acq_date, None)


@pytest.mark.ai_generated
def test_multi_orientation_seqinfo() -> None:
    # nibabel >= 5.5.0 by default would warn (our pytest configuration turns
    # warnings into errors) and retain only the frames of the first orientation.
    # We want all the frames, and thus the same seqinfo, with any nibabel.
    mw = wrapper_from_file(XA30_ENHANCED_DCM_PATH, force=True, stop_before_pixels=True)
    assert isinstance(mw, dw.MultiframeWrapper)
    assert len(mw.frames) == 3
    assert mw.image_shape == (162, 162, 3)

    # and that is what we get through the code path used while converting
    seqinfos = group_dicoms_into_seqinfos(
        [XA30_ENHANCED_DCM_PATH], "studyUID", flatten=True
    )
    (seqinfo,) = seqinfos
    assert (seqinfo.dim1, seqinfo.dim2, seqinfo.dim3, seqinfo.dim4) == (162, 162, 3, 1)


@pytest.mark.ai_generated
def test_known_nibabel_frame_filters() -> None:
    # wrapper_from_file deliberately does not follow the default frame filters
    # of nibabel.  Fail whenever nibabel gains a default filter we have not
    # considered yet, so we make a conscious decision on either to adopt it in
    # wrapper_from_file (it could change seqinfo) or to list it here.
    default_filters = getattr(
        dw,
        "DEFAULT_FRAME_FILTERS",
        # was misspelled before nibabel 5.5.0
        getattr(dw, "DEFUALT_FRAME_FILTERS", None),
    )
    assert (
        default_filters is not None
    ), "nibabel no longer exposes default frame filters under a known name"
    assert {type(f).__name__ for f in default_filters} <= {
        "FilterMultiStack",
        "FilterDwiIso",
        # added in 5.5.0, intentionally not used by wrapper_from_file
        "FilterMultiOrient",
    }


@pytest.mark.ai_generated
@pytest.mark.parametrize("dcmfile", TEST_DICOM_PATHS)
def test_create_seqinfo_date_time(dcmfile: str) -> None:
    # all our test DICOMs do carry some date/time information, and seqinfo
    # should expose it regardless of which tags it comes from
    mw = wrapper_from_file(dcmfile)
    seqinfo = create_seqinfo(mw, [dcmfile], op.basename(dcmfile))
    assert seqinfo.date is not None
    assert seqinfo.time is not None
    assert datetime.datetime.strptime(
        seqinfo.date + seqinfo.time, "%Y%m%d%H%M%S.%f"
    ) == get_datetime_from_dcm(mw.dcm_data)


@pytest.mark.parametrize("dcmfile", TEST_DICOM_PATHS)
def test_get_reproducible_int(dcmfile: str) -> None:
    assert type(get_reproducible_int([dcmfile])) is int


@pytest.mark.skip(
    reason="This test was mistakenly marked as a fixture, and removing the fixture decorator led to the test failing.  Don't know how to fix."
)
def test_get_reproducible_int_wo_dt(tmp_path: Path) -> None:
    # can this function return an int when we don't have any usable dates?
    typical_dcm = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    del typical_dcm.SeriesDate
    del typical_dcm.AcquisitionDate
    dcm.dcmwrite(tmp_path, typical_dcm)

    assert type(get_reproducible_int([str(tmp_path)])) is int


@pytest.mark.skip(
    reason="This test was mistakenly marked as a fixture, and removing the fixture decorator led to the test failing.  Don't know how to fix."
)
def test_get_reproducible_int_raises_assertion_wo_dt(tmp_path: Path) -> None:
    # if there's no known source (e.g., after anonymization), is AssertionError Raised?
    XA30_enhanced_dcm = dcm.dcmread(
        XA30_ENHANCED_DCM_PATH,
        stop_before_pixels=True,
    )
    del XA30_enhanced_dcm.AcquisitionDateTime
    del XA30_enhanced_dcm.SeriesDate
    del XA30_enhanced_dcm.SeriesTime
    dcm.dcmwrite(tmp_path, XA30_enhanced_dcm)
    with pytest.raises(AssertionError):
        get_reproducible_int([str(tmp_path)])


@pytest.mark.ai_generated
@pytest.mark.parametrize("dcmfile", TEST_DICOM_PATHS)
def test_get_dicom_acquisition_duration_absent(dcmfile: str) -> None:
    # none of our test DICOMs carry AcquisitionDuration-like tags
    dcm_data = dcm.dcmread(dcmfile, stop_before_pixels=True, force=True)
    assert get_dicom_acquisition_duration(dcm_data) is None


# GE private tag block is only recognized under its own private creator, so
# every case which sets (0019,105A) also sets (0019,0010) accordingly.
_GE_CREATOR_TAG = (0x0019, 0x0010)
_GE_DURATION_TAG = (0x0019, 0x105A)
_GE_CREATOR = "GEMS_ACQU_01"


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "tags,expected",
    [
        # standard tag alone
        pytest.param({(0x0018, 0x9073): ("FD", 12.5)}, 12.5, id="standard"),
        # GE private tag alone, under its recognized private creator
        pytest.param(
            {
                _GE_CREATOR_TAG: ("LO", _GE_CREATOR),
                _GE_DURATION_TAG: ("FL", 3.0118515e08),
            },
            pytest.approx(301.185, rel=1e-3),
            id="ge_private",
        ),
        # both present -- the standard tag takes precedence
        pytest.param(
            {
                (0x0018, 0x9073): ("FD", 12.5),
                _GE_CREATOR_TAG: ("LO", _GE_CREATOR),
                _GE_DURATION_TAG: ("FL", 999e6),
            },
            12.5,
            id="prefers_standard",
        ),
        # private group 0019 is used differently by different vendors -- an
        # element at the GE offset under an unrelated creator block must not
        # be mistaken for GE's Acquisition Duration
        pytest.param(
            {
                _GE_CREATOR_TAG: ("LO", "SOME_OTHER_VENDOR_01"),
                _GE_DURATION_TAG: ("FL", 3.0118515e08),
            },
            None,
            id="ge_wrong_creator",
        ),
        # e.g. some scanners write AcquisitionDuration = 0 when unpopulated;
        # that is not a usable duration
        pytest.param({(0x0018, 0x9073): ("FD", 0.0)}, None, id="zero"),
        pytest.param({(0x0018, 0x9073): ("FD", -5.0)}, None, id="negative"),
    ],
)
def test_get_dicom_acquisition_duration(
    tags: dict[tuple[int, int], tuple[str, Any]], expected: float | None
) -> None:
    dcm_data = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    for tag, (vr, value) in tags.items():
        dcm_data.add_new(tag, vr, value)
    assert get_dicom_acquisition_duration(dcm_data) == expected


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "strip_csa_header,expected",
    [
        # phantom.dcm is real Siemens data whose embedded CSA series header
        # protocol dump carries "lTotalScanTimeSec = 14"
        pytest.param(False, pytest.approx(14.0), id="present"),
        # remove the CSA series header info to test the genuinely-absent
        # case (e.g. non-Siemens data, or anonymization having stripped it)
        pytest.param(True, None, id="absent"),
    ],
)
def test_get_dicom_declared_acquisition_duration(
    strip_csa_header: bool, expected: float | None
) -> None:
    dcm_data = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    if strip_csa_header:
        del dcm_data[(0x0029, 0x1020)]
    assert get_dicom_declared_acquisition_duration(dcm_data) == expected


@pytest.mark.ai_generated
def test_get_dicom_declared_repetitions() -> None:
    # phantom.dcm's protocol dump omits 'lRepetitions' entirely, as Siemens
    # does for a single-volume (single-measurement) sequence
    dcm_data = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    assert get_dicom_declared_repetitions(dcm_data) == 0

    # axasc35.dcm's protocol dump declares 'lRepetitions = 1' (2 volumes)
    dcm_data = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "axasc35.dcm"), stop_before_pixels=True
    )
    assert get_dicom_declared_repetitions(dcm_data) == 1


def _timestamps(offsets: list[float]) -> list[datetime.datetime]:
    start = datetime.datetime(2020, 1, 1, 12)
    return [start + datetime.timedelta(seconds=offset) for offset in offsets]


def _edit_dicom(fn: str, **tags: Any) -> None:
    """Set `tags` in the DICOM `fn`; a tag given as None is removed."""
    dcm_data = dcm.dcmread(fn, stop_before_pixels=True)
    with warnings.catch_warnings():
        # pydicom >= 2.3 warns about an invalid value
        warnings.simplefilter("ignore")
        for tag, value in tags.items():
            if value is not None:
                setattr(dcm_data, tag, value)
            elif tag in dcm_data:
                delattr(dcm_data, tag)
    dcm.dcmwrite(fn, dcm_data)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "offsets,expected",
    [
        # span plus the median interval, which for an even number of
        # intervals (1, 2, 4, 1) is the mean of the two middle ones
        ([0, 1, 3, 7, 8], 9.5),
        # the first is not necessarily the earliest, e.g. interleaved
        # multiband slices: https://github.com/nipy/heudiconv/issues/876
        ([2, 0, 4, 7], 9.0),
        ([3, 3], None),  # need two distinct ones
        ([3], None),
        ([], None),
    ],
)
def test_estimate_scan_duration_from_times(
    offsets: list[float], expected: float | None
) -> None:
    assert estimate_scan_duration_from_times(_timestamps(offsets)) == expected


@pytest.mark.ai_generated
@pytest.mark.parametrize("tz_offset", [None, "+0100"])
def test_get_acquisition_timestamps(tmp_path: Path, tz_offset: str | None) -> None:
    dicom_list = make_timed_dicoms(tmp_path, [2, 0, 4, 7], tz_offset=tz_offset)
    timestamps = get_acquisition_timestamps(dicom_list)
    # in dicom_list order, and exactly what a full header read gives -- in
    # particular equally timezone-aware, so the two can be compared
    assert timestamps == [
        get_datetime_from_dcm(dcm.dcmread(f, stop_before_pixels=True))
        for f in dicom_list
    ]
    assert [t.second for t in timestamps] == [2, 0, 4, 7]
    assert all((t.tzinfo is not None) == bool(tz_offset) for t in timestamps)


_NO_DATETIME = dict.fromkeys(
    ["AcquisitionDate", "AcquisitionTime", "AcquisitionDateTime", "SeriesDate"]
    + ["SeriesTime"]
)
_SERIES_TIME_ONLY = dict(
    AcquisitionTime=None, SeriesDate="20200101", SeriesTime="115930.000000"
)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "edits,expected_seconds",
    [
        # a file with a malformed, or without any, date/time is skipped
        pytest.param({1: dict(AcquisitionTime="not-a-time")}, [0, 2], id="malformed"),
        pytest.param({1: _NO_DATETIME}, [0, 2], id="no-datetime"),
        pytest.param(dict.fromkeys(range(3), _NO_DATETIME), [], id="no-datetimes"),
        # and so is one with only the (earlier) start time of the series
        # (https://github.com/nipy/heudiconv/issues/878) ...
        pytest.param({2: _SERIES_TIME_ONLY}, [0, 1], id="series-time"),
        # ... unless that is all there is
        pytest.param(
            dict.fromkeys(range(3), _SERIES_TIME_ONLY), [30] * 3, id="series-times"
        ),
    ],
)
def test_get_acquisition_timestamps_of_odd_files(
    tmp_path: Path, edits: dict[int, dict[str, Any]], expected_seconds: list[int]
) -> None:
    dicom_list = make_timed_dicoms(tmp_path, [0, 1, 2])
    for i, tags in edits.items():
        _edit_dicom(dicom_list[i], **tags)
    timestamps = get_acquisition_timestamps(dicom_list)
    assert [t.second for t in timestamps] == expected_seconds


@pytest.mark.ai_generated
def test_get_acquisition_timestamps_mixed_timezone_awareness(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # DICOMs of a run do not always agree on carrying TimezoneOffsetFromUTC,
    # and a mix of aware and naive datetimes could not be compared
    dicom_list = make_timed_dicoms(tmp_path, [2, 0, 4, 7], tz_offset="+0100")
    _edit_dicom(dicom_list[1], TimezoneOffsetFromUTC=None)

    timestamps = get_acquisition_timestamps(dicom_list)
    assert timestamps == _timestamps([2, 0, 4, 7])
    assert "timezone-naive" in caplog.text
    assert get_acquisition_duration(dicom_list, timestamps) == 9.0


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "dicoms,expected",
    [
        ([], None),
        # 3 files ~4.15s apart: their timestamps are preferred over the 591s
        # which the CSA header declares
        ("b0dwiForFmap/*.dcm", 12.45),
        # a single volume, so only Siemens' declared duration is left
        ("phantom.dcm", 14.0),
        # as for the 17s this one declares: its protocol is of 2 volumes
        # (lRepetitions = 1), so with a single file it looks truncated
        ("axasc35.dcm", None),
    ],
)
def test_get_acquisition_duration(dicoms: str, expected: float | None) -> None:
    dicom_list = sorted(glob(op.join(TESTS_DATA_PATH, dicoms))) if dicoms else []
    assert get_acquisition_duration(dicom_list) == (
        expected and pytest.approx(expected)
    )


@pytest.mark.ai_generated
def test_get_acquisition_duration_of_given_timestamps(tmp_path: Path) -> None:
    dicom_list = make_timed_dicoms(tmp_path, [2, 0, 4, 7])
    assert get_acquisition_duration(dicom_list, _timestamps([0, 1, 2])) == 3.0


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "offsets,tag,expected",
    [
        ([0], 12.5, 12.5),  # nothing to cross-check the tag against
        # timestamps span 7s, estimate 7s + 2s median interval = 9s
        ([2, 0, 4, 7], 10.0, 10.0),  # the tag is plausible
        ([2, 0, 4, 7], 602.0, 9.0),  # e.g. the full protocol of an aborted run
        ([2, 0, 4, 7], 2.0, 9.0),  # shorter than what was acquired
    ],
)
def test_get_acquisition_duration_cross_checks_tag(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    offsets: list[int],
    tag: float,
    expected: float,
) -> None:
    dicom_list = make_timed_dicoms(tmp_path, offsets)
    for fn in dicom_list:
        _edit_dicom(fn, AcquisitionDuration=tag)
    assert get_acquisition_duration(dicom_list) == expected
    assert ("AcquisitionDuration tag declares" in caplog.text) == (tag != expected)


@pytest.mark.ai_generated
def test_get_acquisition_duration_of_truncated_acquisition(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # AcquisitionDuration is of the full planned protocol, of which only 2
    # files, 36.2s apart, were acquired
    dicom_list = sorted(glob(op.join(TESTS_DATA_PATH, "xa_4d_interrupted", "*")))
    tag = get_dicom_acquisition_duration(
        dcm.dcmread(dicom_list[0], stop_before_pixels=True, force=True)
    )
    assert tag == pytest.approx(602.735)
    duration = get_acquisition_duration(dicom_list)
    assert duration is not None and 36.2 <= duration < 100
    assert "AcquisitionDuration tag declares 602.735s" in caplog.text
