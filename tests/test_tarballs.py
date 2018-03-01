import os
import pytest
import sys
import time

from mock import patch
from os.path import join as opj
from os.path import dirname
from six.moves import StringIO
from glob import glob

from heudiconv.dicoms import compress_dicoms
from heudiconv.utils import TempDirs, file_md5sum

tests_datadir = opj(dirname(__file__), 'data')


def test_reproducibility(tmpdir):
    prefix = str(tmpdir.join("precious"))
    args = [glob(opj(tests_datadir, '01-fmap_acq-3mm', '*')),
            prefix,
            TempDirs(),
            True]
    tarball = compress_dicoms(*args)
    md5 = file_md5sum(tarball)
    assert tarball
    # must not override, ensure overwrite is set to False
    args[-1] = False
    assert compress_dicoms(*args) is None
    # reset this
    args[-1] = True

    os.unlink(tarball)

    time.sleep(1.1)  # need to guarantee change of time
    tarball_ = compress_dicoms(*args)
    md5_ = file_md5sum(tarball_)
    assert tarball == tarball_
    assert md5 == md5_
