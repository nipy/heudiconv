from __future__ import annotations

from glob import glob
import os
from os.path import join as opj
from pathlib import Path
import time

from heudiconv.dicoms import compress_dicoms
from heudiconv.utils import TempDirs, file_md5sum

from .utils import TESTS_DATA_PATH


def test_reproducibility(tmp_path: Path) -> None:
    dicom_list = glob(opj(TESTS_DATA_PATH, "01-fmap_acq-3mm", "*"))
    prefix = str(tmp_path / "precious")
    tempdirs = TempDirs()

    tarball = compress_dicoms(dicom_list, prefix, tempdirs, True)
    assert tarball is not None
    md5 = file_md5sum(tarball)
    # must not override, ensure overwrite is set to False
    assert compress_dicoms(dicom_list, prefix, tempdirs, False) is None

    os.unlink(tarball)

    time.sleep(1.1)  # need to guarantee change of time
    tarball_ = compress_dicoms(dicom_list, prefix, tempdirs, True)
    assert tarball == tarball_
    md5_ = file_md5sum(tarball_)
    assert md5 == md5_
