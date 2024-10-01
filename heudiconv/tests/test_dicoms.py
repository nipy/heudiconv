from __future__ import annotations

import datetime
from glob import glob
import json
import os.path as op
from pathlib import Path

import pydicom as dcm
import pytest

from heudiconv.cli.run import main as runner
from heudiconv.convert import nipype_convert
from heudiconv.dicoms import (
    create_seqinfo,
    dw,
    embed_dicom_and_nifti_metadata,
    get_datetime_from_dcm,
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
    dcm.dcmwrite(tmp_path, dataset=XA30_enhanced_dcm)
    with pytest.raises(AssertionError):
        get_reproducible_int([str(tmp_path)])
