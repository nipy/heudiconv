from __future__ import annotations

from collections.abc import Sequence
import datetime
from glob import glob
import logging
import os.path as op
from pathlib import Path
from typing import Optional

import pydicom as dcm

import heudiconv.heuristics

HEURISTICS_PATH = op.join(heudiconv.heuristics.__path__[0])
TESTS_DATA_PATH = op.join(op.dirname(__file__), "data")
# Do relative to curdir to shorten in a typical application,
# and side-effect test that tests do not change curdir.
TEST_DICOM_PATHS = [
    op.relpath(x)
    for x in glob(op.join(TESTS_DATA_PATH, "**/*.dcm"), recursive=True)
    # exclude PhoenixDocuments
    if "PhoenixDocument" not in x
]

lgr = logging.getLogger(__name__)


def gen_heudiconv_args(
    datadir: str,
    outdir: str,
    subject: str,
    heuristic_file: str,
    anon_cmd: Optional[str] = None,
    template: Optional[str] = None,
    xargs: Optional[list[str]] = None,
) -> list[str]:
    heuristic = op.realpath(op.join(HEURISTICS_PATH, heuristic_file))

    if template:
        # use --dicom_dir_template
        args = ["-d", op.join(datadir, template)]
    else:
        args = ["--files", datadir]

    args.extend(
        [
            "-c",
            "dcm2niix",
            "-o",
            outdir,
            "-s",
            subject,
            "-f",
            heuristic,
            "--bids",
            "--minmeta",
        ]
    )
    if anon_cmd:
        args += ["--anon-cmd", op.join(op.dirname(__file__), anon_cmd), "-a", outdir]
    if xargs:
        args += xargs

    return args


def fetch_data(tmpdir: str | Path, dataset: str, getpath: Optional[str] = None) -> str:
    """
    Utility function to interface with datalad database.
    Performs datalad `install` and datalad `get` operations.

    Parameters
    ----------
    tmpdir : str or Path
        directory to temporarily store data
    dataset : str
        dataset path from `http://datasets-tests.datalad.org`
    getpath : str [optional]
        exclusive path to get

    Returns
    -------
    targetdir : str
        directory with installed dataset
    """
    from datalad import api

    targetdir = op.join(tmpdir, op.basename(dataset))
    ds = api.install(
        path=targetdir, source="http://datasets-tests.datalad.org/{}".format(dataset)
    )

    getdir = targetdir + (op.sep + getpath if getpath is not None else "")
    ds.get(getdir)
    return targetdir


def make_timed_dicoms(
    outdir: Path,
    offsets: Sequence[float],
    start: str = "2020-01-01T12:00:00",
    tz_offset: Optional[str] = None,
) -> list[str]:
    """Write copies of the phantom.dcm header (no pixel data) into `outdir`
    as f0.dcm, f1.dcm, ..., each acquired `offsets[i]` seconds after `start`
    (AcquisitionDate/AcquisitionTime) -- in timezone `tz_offset` (DICOM
    TimezoneOffsetFromUTC, e.g. "+0100") if given -- and return their paths
    in that order."""
    start_dt = datetime.datetime.fromisoformat(start)
    dicom_list = []
    for i, offset in enumerate(offsets):
        dcm_data = dcm.dcmread(
            op.join(TESTS_DATA_PATH, "phantom.dcm"), stop_before_pixels=True
        )
        acq_dt = start_dt + datetime.timedelta(seconds=offset)
        dcm_data.AcquisitionDate = acq_dt.strftime("%Y%m%d")
        dcm_data.AcquisitionTime = acq_dt.strftime("%H%M%S.%f")
        if tz_offset:
            dcm_data.TimezoneOffsetFromUTC = tz_offset
        out = outdir / f"f{i}.dcm"
        dcm.dcmwrite(str(out), dcm_data)
        dicom_list.append(str(out))
    return dicom_list
