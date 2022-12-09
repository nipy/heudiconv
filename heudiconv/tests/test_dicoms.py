import os.path as op
import json
from glob import glob

import pytest

from heudiconv.external.pydicom import dcm
from heudiconv.cli.run import main as runner
from heudiconv.convert import nipype_convert
from heudiconv.dicoms import (
    OrderedDict,
    embed_dicom_and_nifti_metadata,
    group_dicoms_into_seqinfos,
    parse_private_csa_header,
    get_datetime_from_dcm,
    get_timestamp_from_series
)
from .utils import (
    assert_cwd_unchanged,
    TESTS_DATA_PATH,
)

# Public: Private DICOM tags
DICOM_FIELDS_TO_TEST = {
    'ProtocolName': 'tProtocolName'
}

def test_private_csa_header(tmpdir):
    dcm_file = op.join(TESTS_DATA_PATH, 'axasc35.dcm')
    dcm_data = dcm.read_file(dcm_file, stop_before_pixels=True)
    for pub, priv in DICOM_FIELDS_TO_TEST.items():
        # ensure missing public tag
        with pytest.raises(AttributeError):
            dcm.pub
        # ensure private tag is found
        assert parse_private_csa_header(dcm_data, pub, priv) != ''
        # and quickly run heudiconv with no conversion
        runner(['--files', dcm_file, '-c' 'none', '-f', 'reproin'])


@assert_cwd_unchanged(ok_to_chdir=True)  # so we cd back after tmpdir.chdir
def test_embed_dicom_and_nifti_metadata(tmpdir):
    """Test dcmstack's additional fields"""
    tmpdir.chdir()
    # set up testing files
    dcmfiles = [op.join(TESTS_DATA_PATH, 'axasc35.dcm')]
    infofile = 'infofile.json'

    out_prefix = str(tmpdir / "nifti")
    # 1) nifti does not exist -- no longer supported
    with pytest.raises(NotImplementedError):
        embed_dicom_and_nifti_metadata(dcmfiles, out_prefix + '.nii.gz', infofile, None)

    # we should produce nifti using our "standard" ways
    nipype_out, prov_file = nipype_convert(
        dcmfiles, prefix=out_prefix, with_prov=False,
        bids_options=None, tmpdir=str(tmpdir))
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


def test_group_dicoms_into_seqinfos(tmpdir):
    """Tests for group_dicoms_into_seqinfos"""

    # 1) Check that it works for PhoenixDocuments:
    # set up testing files
    dcmfolder = op.join(TESTS_DATA_PATH, 'Phoenix')
    dcmfiles = glob(op.join(dcmfolder, '*', '*.dcm'))

    seqinfo = group_dicoms_into_seqinfos(dcmfiles, 'studyUID', flatten=True)

    assert type(seqinfo) is OrderedDict
    assert len(seqinfo) == len(dcmfiles)
    assert [s.series_description for s in seqinfo] == ['AAHead_Scout_32ch-head-coil', 'PhoenixZIPReport']



def test_get_datetime_from_dcm():
    import datetime
    typical_dcm = dcm.dcmread(op.join(TESTS_DATA_PATH, 'phantom.dcm'), stop_before_pixels=True)
    XA30_enhanced_dcm = dcm.dcmread(op.join(TESTS_DATA_PATH, 'MRI_102TD_PHA_S.MR.Chen_Matthews_1.3.1.2022.11.16.15.50.20.357.31204541.dcm'), stop_before_pixels=True)

    # do we try to grab from AcquisitionDate/AcquisitionTime first when available?
    assert type(get_datetime_from_dcm(typical_dcm)) is datetime.datetime
    assert get_datetime_from_dcm(typical_dcm) == datetime.datetime.strptime(
        typical_dcm.get("AcquisitionDate") + typical_dcm.get("AcquisitionTime"), 
        "%Y%m%d%H%M%S.%f"
        )

    # can we rely on AcquisitionDateTime if AcquisitionDate and AcquisitionTime not there?
    assert type(get_datetime_from_dcm(XA30_enhanced_dcm)) is datetime.datetime

    # if these aren't available, can we rely on AcquisitionDateTime?
    del XA30_enhanced_dcm.SeriesDate
    del XA30_enhanced_dcm.SeriesTime
    assert type(get_datetime_from_dcm(XA30_enhanced_dcm)) is datetime.datetime

    # and if there's no known source (e.g., after anonymization), are we still able to proceed?
    del XA30_enhanced_dcm.AcquisitionDateTime
    assert get_datetime_from_dcm(XA30_enhanced_dcm) is None


def test_get_timestamp_from_series(tmpdir):
    dcmfile = op.join(TESTS_DATA_PATH, 'phantom.dcm')

    assert type(get_timestamp_from_series([dcmfile])) is int

    # can this function return an int when we don't have any useable dates?
    typical_dcm = dcm.dcmread(op.join(TESTS_DATA_PATH, 'phantom.dcm'), stop_before_pixels=True)
    del typical_dcm.InstanceCreationDate
    del typical_dcm.StudyDate
    del typical_dcm.SeriesDate
    del typical_dcm.AcquisitionDate
    del typical_dcm.ContentDate
    del typical_dcm.PerformedProcedureStepStartDate
    tmp_dcmfile = tmpdir / "phantom.dcm" 
    dcm.dcmwrite(tmp_dcmfile, typical_dcm)

    assert type(get_timestamp_from_series([tmp_dcmfile])) is int



