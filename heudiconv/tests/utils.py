from __future__ import annotations

from glob import glob
import logging
import os.path as op
from pathlib import Path
from typing import Optional

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
