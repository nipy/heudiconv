import os
import pytest
import sys
import time

from mock import patch
from os.path import join as opj
from os.path import dirname
from six.moves import StringIO
from glob import glob

from . import heudiconv
from .utils import md5sum

tests_datadir = opj(dirname(__file__), 'data')


def test_reproducibility(tmpdir):
    #heudiconv.compress_dicoms(dicom_list, prefix, sourcedir)
    prefix = str(tmpdir.join("precious"))
    args = [glob(opj(tests_datadir, '01-fmap_acq-3mm', '*')), prefix]
    tarball = heudiconv.compress_dicoms(*args)
    md5 = md5sum(tarball)
    assert tarball
    # must not override by default
    with pytest.raises(RuntimeError):
        heudiconv.compress_dicoms(*args)
    os.unlink(tarball)

    time.sleep(1.1)  # need to guarantee change of time
    tarball_ = heudiconv.compress_dicoms(*args)
    md5_ = md5sum(tarball_)
    assert tarball == tarball_
    assert md5 == md5_
