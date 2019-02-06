import os.path as op
import json

import pytest

from heudiconv.external.pydicom import dcm
from heudiconv.cli.run import main as runner
from heudiconv.dicoms import parse_private_csa_header, embed_nifti
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

    # 1) nifti does not exist
    out = embed_nifti(dcmfiles, 'nifti.nii', 'infofile.json', None, False)
    # string -> json
    out = json.loads(out)
    # should have created nifti file
    assert op.exists('nifti.nii')

    # 2) nifti exists
    nifti, info = embed_nifti(dcmfiles, 'nifti.nii', 'infofile.json', None, False)
    assert op.exists(nifti)
    assert op.exists(info)
    with open(info) as fp:
        out2 = json.load(fp)

    assert out == out2

    # 3) with existing metadata
    bids = {"existing": "data"}
    nifti, info = embed_nifti(dcmfiles, 'nifti.nii', 'infofile.json', bids, False)
    with open(info) as fp:
        out3 = json.load(fp)

    assert out3["existing"]
    del out3["existing"]
    assert out3 == out2 == out
