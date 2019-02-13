import os.path as op
import json

import pytest

from heudiconv.external.pydicom import dcm
from heudiconv.cli.run import main as runner
from heudiconv.dicoms import parse_private_csa_header, extract_more_metadata_for_nifti
from .utils import TESTS_DATA_PATH

# Public: Private DICOM tags
DICOM_FIELDS_TO_TEST = {
    'ProtocolName': 'tProtocolName'
}

def test_private_csa_header(tmpdir):
    dcm_file = op.join(TESTS_DATA_PATH, 'axasc35.dcm')
    dcm_data = dcm.read_file(dcm_file)
    for pub, priv in DICOM_FIELDS_TO_TEST.items():
        # ensure missing public tag
        with pytest.raises(AttributeError):
            dcm.pub
        # ensure private tag is found
        assert parse_private_csa_header(dcm_data, pub, priv) != ''
        # and quickly run heudiconv with no conversion
        runner(['--files', dcm_file, '-c' 'none', '-f', 'reproin'])


def test_nifti_embed(tmpdir):
    """Test dcmstack's additional fields"""
    tmpdir.chdir()
    # set up testing files
    dcmfiles = [op.join(TESTS_DATA_PATH, 'axasc35.dcm')]
    infofile = 'infofile.json'

    # 1) nifti does not exist - no longer supported, not used
    with pytest.raises(IOError):
        out = extract_more_metadata_for_nifti(dcmfiles, 'nifti.nii', 'infofile.json', None, False)
    # should have NOT created nifti file
    assert not op.exists('nifti.nii')

    # 2) nifti exists
    # First - convert
    from heudiconv.convert import nipype_convert
    res, _ = nipype_convert(dcmfiles, str(tmpdir/'nifti'), tmpdir=str(tmpdir/'nipype'))
    nifti = res.outputs.converted_files
    assert op.exists(nifti)
    info = extract_more_metadata_for_nifti(dcmfiles, nifti, 'infofile.json', None, False)
    assert op.exists(info)
    with open(info) as fp:
        out = json.load(fp)

    assert out

    # 3) with existing metadata
    bids = {"existing": "data"}
    info = extract_more_metadata_for_nifti(dcmfiles, nifti, 'infofile.json', bids, False)
    with open(info) as fp:
        out2 = json.load(fp)

    assert out2["existing"]
    del out2["existing"]
    assert out2 == out
