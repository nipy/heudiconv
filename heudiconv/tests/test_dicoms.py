from __future__ import annotations

import datetime
from glob import glob
import json
import os.path as op
from pathlib import Path
from typing import Any

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
    get_datetime_from_dcm,
    get_datetime_strings_from_dcm,
    get_dicom_acquisition_duration,
    get_dicom_declared_acquisition_duration,
    get_dicom_declared_repetitions,
    get_reproducible_int,
    group_dicoms_into_seqinfos,
    parse_private_csa_header,
)

from .utils import TEST_DICOM_PATHS, TESTS_DATA_PATH

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
        op.join(
            TESTS_DATA_PATH,
            "MRI_102TD_PHA_S.MR.Chen_Matthews_1.3.1.2022.11.16.15.50.20.357.31204541.dcm",
        ),
        stop_before_pixels=True,
    )
    dt = get_datetime_from_dcm(XA30_enhanced_dcm)
    assert dt == datetime.datetime.strptime(
        XA30_enhanced_dcm.get("AcquisitionDateTime"), "%Y%m%d%H%M%S.%f"
    )


def test_get_datetime_from_dcm_from_only_series_date_time() -> None:
    # if acquisition date/time/datetime not available, can we rely on SeriesDate & SeriesTime?
    XA30_enhanced_dcm = dcm.dcmread(
        op.join(
            TESTS_DATA_PATH,
            "MRI_102TD_PHA_S.MR.Chen_Matthews_1.3.1.2022.11.16.15.50.20.357.31204541.dcm",
        ),
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
        op.join(
            TESTS_DATA_PATH,
            "MRI_102TD_PHA_S.MR.Chen_Matthews_1.3.1.2022.11.16.15.50.20.357.31204541.dcm",
        ),
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
    mw = dw.wrapper_from_file(dcmfile)
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
        op.join(
            TESTS_DATA_PATH,
            "MRI_102TD_PHA_S.MR.Chen_Matthews_1.3.1.2022.11.16.15.50.20.357.31204541.dcm",
        ),
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
        op.join(
            TESTS_DATA_PATH,
            "MRI_102TD_PHA_S.MR.Chen_Matthews_1.3.1.2022.11.16.15.50.20.357.31204541.dcm",
        ),
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
        op.join(
            TESTS_DATA_PATH,
            "MRI_102TD_PHA_S.MR.Chen_Matthews_1.3.1.2022.11.16.15.50.20.357.31204541.dcm",
        ),
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
@pytest.mark.parametrize("dcmfile", TEST_DICOM_PATHS)
def test_create_seqinfo_date_time(dcmfile: str) -> None:
    # all our test DICOMs do carry some date/time information, and seqinfo
    # should expose it regardless of which tags it comes from
    mw = dw.wrapper_from_file(dcmfile)
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
        op.join(
            TESTS_DATA_PATH,
            "MRI_102TD_PHA_S.MR.Chen_Matthews_1.3.1.2022.11.16.15.50.20.357.31204541.dcm",
        ),
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
    ],
)
def test_get_dicom_acquisition_duration(
    tags: dict[tuple[int, int], tuple[str, Any]], expected: float
) -> None:
    dcm_data = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    for tag, (vr, value) in tags.items():
        dcm_data.add_new(tag, vr, value)
    assert get_dicom_acquisition_duration(dcm_data) == expected


@pytest.mark.ai_generated
def test_get_dicom_acquisition_duration_ge_tag_wrong_creator() -> None:
    # private group 0019 is used differently by different vendors -- an
    # element at the GE offset under an unrelated creator block must not be
    # mistaken for GE's Acquisition Duration
    dcm_data = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    dcm_data.add_new(_GE_CREATOR_TAG, "LO", "SOME_OTHER_VENDOR_01")
    dcm_data.add_new(_GE_DURATION_TAG, "FL", 3.0118515e08)
    assert get_dicom_acquisition_duration(dcm_data) is None


@pytest.mark.ai_generated
@pytest.mark.parametrize("value", [0.0, -5.0])
def test_get_dicom_acquisition_duration_non_positive(value: float) -> None:
    # e.g. some scanners write AcquisitionDuration = 0 when unpopulated;
    # that is not a usable duration
    dcm_data = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    dcm_data.add_new((0x0018, 0x9073), "FD", value)
    assert get_dicom_acquisition_duration(dcm_data) is None


@pytest.mark.ai_generated
def test_get_dicom_declared_acquisition_duration() -> None:
    # phantom.dcm is real Siemens data whose embedded CSA series header
    # protocol dump carries "lTotalScanTimeSec = 14"
    dcm_data = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    assert get_dicom_declared_acquisition_duration(dcm_data) == pytest.approx(14.0)


@pytest.mark.ai_generated
def test_get_dicom_declared_acquisition_duration_absent() -> None:
    # remove the CSA series header info to test the genuinely-absent case
    # (e.g. non-Siemens data, or anonymization having stripped it)
    dcm_data = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    del dcm_data[(0x0029, 0x1020)]
    assert get_dicom_declared_acquisition_duration(dcm_data) is None


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


@pytest.mark.ai_generated
def test_estimate_scan_duration_from_times() -> None:
    # 3 DICOMs, ~4.15s apart -- duration is the span plus one more interval
    dicom_list = sorted(glob(op.join(TESTS_DATA_PATH, "b0dwiForFmap", "*.dcm")))
    assert len(dicom_list) == 3
    assert estimate_scan_duration_from_times(dicom_list) == pytest.approx(12.45)


@pytest.mark.ai_generated
def test_estimate_scan_duration_from_times_even_intervals(tmp_path: Path) -> None:
    # 5 timestamps -> 4 intervals (an even count): 1, 2, 4, 1 seconds.
    # The true median is the average of the two middle (sorted) values,
    # (1 + 2) / 2 == 1.5 -- not just "the" middle element of a 4-item list,
    # which has no single middle element.
    offsets = [0, 1, 3, 7, 8]
    dicom_list = []
    for i, offset in enumerate(offsets):
        dcm_data = dcm.dcmread(
            op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
        )
        dcm_data.AcquisitionDate = "20200101"
        dcm_data.AcquisitionTime = "%06d.000000" % (120000 + offset)
        out = tmp_path / f"f{i}.dcm"
        dcm.dcmwrite(str(out), dcm_data)
        dicom_list.append(str(out))

    # span (8s) + median interval (1.5s)
    assert estimate_scan_duration_from_times(dicom_list) == pytest.approx(9.5)


@pytest.mark.ai_generated
def test_estimate_scan_duration_from_times_anchor_dt(tmp_path: Path) -> None:
    # Reproduces https://github.com/nipy/heudiconv/issues/875: interleaved
    # multiband slice acquisition means the file conventionally treated as
    # "first" (e.g. DICOM InstanceNumber 1, whatever dcm_fns[0] resolves to)
    # is not necessarily the earliest-acquired one. Here dicom_list[0] has
    # offset 2s, but the true earliest timestamp is offset 0s (dicom_list[1]).
    offsets = [2, 0, 4, 7]
    dicom_list = []
    for i, offset in enumerate(offsets):
        dcm_data = dcm.dcmread(
            op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
        )
        dcm_data.AcquisitionDate = "20200101"
        dcm_data.AcquisitionTime = "%06d.000000" % (120000 + offset)
        out = tmp_path / f"f{i}.dcm"
        dcm.dcmwrite(str(out), dcm_data)
        dicom_list.append(str(out))

    # without an anchor: span (0 to 7 = 7s) + median interval (2s) = 9s,
    # anchored on the true earliest timestamp (offset 0), not dicom_list[0]
    assert estimate_scan_duration_from_times(dicom_list) == pytest.approx(9.0)

    # anchored on dicom_list[0]'s own timestamp (offset 2, as acq_time would
    # be) instead: (7 - 2) + median interval (2s) = 7s -- consistent with
    # acq_time + duration landing exactly on the true last timestamp
    anchor_dt = datetime.datetime(2020, 1, 1, 12, 0, 2)
    assert estimate_scan_duration_from_times(
        dicom_list, anchor_dt=anchor_dt
    ) == pytest.approx(7.0)


@pytest.mark.ai_generated
def test_get_acquisition_duration_passes_through_anchor_dt(tmp_path: Path) -> None:
    # same interleaved-instance scenario as
    # test_estimate_scan_duration_from_times_anchor_dt, but through the
    # top-level get_acquisition_duration() entry point
    offsets = [2, 0, 4, 7]
    dicom_list = []
    for i, offset in enumerate(offsets):
        dcm_data = dcm.dcmread(
            op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
        )
        dcm_data.AcquisitionDate = "20200101"
        dcm_data.AcquisitionTime = "%06d.000000" % (120000 + offset)
        out = tmp_path / f"f{i}.dcm"
        dcm.dcmwrite(str(out), dcm_data)
        dicom_list.append(str(out))

    anchor_dt = datetime.datetime(2020, 1, 1, 12, 0, 2)
    assert get_acquisition_duration(dicom_list) == pytest.approx(9.0)
    assert get_acquisition_duration(dicom_list, anchor_dt=anchor_dt) == pytest.approx(
        7.0
    )


@pytest.mark.ai_generated
def test_estimate_scan_duration_from_times_skips_malformed_timestamp(
    tmp_path: Path,
) -> None:
    # a malformed date/time in one (non-first) file should be skipped with
    # a warning, not raise and abort the whole (best-effort) estimate
    import warnings

    import pydicom.config as dcm_config

    offsets = [0, 1, 3]
    dicom_list = []
    for i, offset in enumerate(offsets):
        dcm_data = dcm.dcmread(
            op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
        )
        dcm_data.AcquisitionDate = "20200101"
        if i == 1:
            # bypass pydicom's own VR validation so a genuinely malformed
            # value (as could come from a non-conformant scanner) can be
            # written out for this test
            old_mode = dcm_config.settings.writing_validation_mode
            dcm_config.settings.writing_validation_mode = dcm_config.IGNORE
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    dcm_data.AcquisitionTime = "not-a-time"
            finally:
                dcm_config.settings.writing_validation_mode = old_mode
        else:
            dcm_data.AcquisitionTime = "%06d.000000" % (120000 + offset)
        out = tmp_path / f"f{i}.dcm"
        dcm.dcmwrite(str(out), dcm_data)
        dicom_list.append(str(out))

    # the malformed file (offset 1) is skipped; span (3s) + median interval
    # of the remaining single interval (3s) between the two good timestamps
    assert estimate_scan_duration_from_times(dicom_list) == pytest.approx(6.0)


@pytest.mark.ai_generated
def test_estimate_scan_duration_from_times_single_file() -> None:
    dicom_list = sorted(glob(op.join(TESTS_DATA_PATH, "b0dwiForFmap", "*.dcm")))[:1]
    assert estimate_scan_duration_from_times(dicom_list) is None


@pytest.mark.ai_generated
def test_estimate_scan_duration_from_times_wo_dt(tmp_path: Path) -> None:
    # no usable date/time information (e.g. stripped by anonymization) --
    # use two distinct files, so this also rules out the "single unique
    # timestamp" case rather than just a single-file list
    outs = []
    for i in range(2):
        dcm_data = dcm.dcmread(
            op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
        )
        for field in (
            "AcquisitionDate",
            "AcquisitionTime",
            "AcquisitionDateTime",
            "SeriesDate",
            "SeriesTime",
        ):
            if field in dcm_data:
                delattr(dcm_data, field)
        out = tmp_path / f"no_dt_{i}.dcm"
        dcm.dcmwrite(str(out), dcm_data)
        outs.append(str(out))
    assert estimate_scan_duration_from_times(outs) is None


@pytest.mark.ai_generated
def test_get_acquisition_duration_empty() -> None:
    assert get_acquisition_duration([]) is None


@pytest.mark.ai_generated
def test_get_acquisition_duration_prefers_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # when a tag is present, the (more expensive) per-file timestamp scan
    # should not even be attempted
    def _boom(_dicom_list: list[str]) -> float:
        raise AssertionError("should not be called")

    monkeypatch.setattr("heudiconv.dicoms.estimate_scan_duration_from_times", _boom)
    dcm_data = dcm.dcmread(
        op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
    )
    dcm_data.add_new((0x0018, 0x9073), "FD", 12.5)
    out = tmp_path / "with_tag.dcm"
    dcm.dcmwrite(str(out), dcm_data)
    assert get_acquisition_duration([str(out)]) == pytest.approx(12.5)


@pytest.mark.ai_generated
def test_get_acquisition_duration_falls_back_to_times() -> None:
    dicom_list = sorted(glob(op.join(TESTS_DATA_PATH, "b0dwiForFmap", "*.dcm")))
    assert get_acquisition_duration(dicom_list) == pytest.approx(12.45)


@pytest.mark.ai_generated
def test_get_acquisition_duration_falls_back_to_declared_duration() -> None:
    # a single-volume 3D sequence (e.g. an MPRAGE T1w): every file shares
    # one AcquisitionTime, so estimate_scan_duration_from_times() cannot
    # find two distinct timestamps to work with -- Siemens' own declared
    # duration (embedded in this real fixture's CSA header) is the only
    # source left
    dcm_fn = op.join(TESTS_DATA_PATH, "phantom.dcm")
    assert get_acquisition_duration([dcm_fn]) == pytest.approx(14.0)


@pytest.mark.ai_generated
def test_get_acquisition_duration_prefers_times_over_declared_duration() -> None:
    # this fixture's own CSA header declares 591s (see test_dicoms data),
    # wildly more than its real per-file timestamp span (12.45s) -- since a
    # multi-file timestamp span IS available here, it must be preferred
    dicom_list = sorted(glob(op.join(TESTS_DATA_PATH, "b0dwiForFmap", "*.dcm")))
    assert get_acquisition_duration(dicom_list) == pytest.approx(12.45)


@pytest.mark.ai_generated
def test_get_acquisition_duration_does_not_guess_for_truncated_multivolume() -> None:
    # axasc35.dcm's protocol declares 'lRepetitions = 1' (2 volumes planned),
    # but only a single file/timestamp is available here -- e.g. an aborted
    # acquisition stopped after its first volume. Falling back to Siemens'
    # declared total scan time (17s) would report the full planned protocol
    # rather than the actual (much shorter) partial one, so this must be
    # left as unavailable instead of guessed.
    dcm_fn = op.join(TESTS_DATA_PATH, "axasc35.dcm")
    assert get_dicom_declared_acquisition_duration(
        dcm.dcmread(dcm_fn, stop_before_pixels=True)
    ) == pytest.approx(17.0)
    assert get_acquisition_duration([dcm_fn]) is None
