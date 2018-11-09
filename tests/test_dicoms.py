import os.path as op

import pytest

from heudiconv.external.pydicom import dcm
from heudiconv.cli.run import main as runner
from heudiconv.dicoms import parse_private_csa_header
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
