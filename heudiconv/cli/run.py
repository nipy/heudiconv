#!/usr/bin/env python
from __future__ import annotations

from argparse import ArgumentParser
import logging
import os
import sys
from typing import Optional

from .. import __version__
from ..main import workflow

lgr = logging.getLogger(__name__)


def main(argv: Optional[list[str]] = None) -> None:
    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=getattr(logging, os.environ.get("HEUDICONV_LOG_LEVEL", "INFO")),
    )
    parser = get_parser()
    args = parser.parse_args(argv)
    # exit if nothing to be done
    if not args.files and not args.dicom_dir_template and not args.command:
        lgr.warning("Nothing to be done - displaying usage help")
        parser.print_help()
        sys.exit(1)

    kwargs = vars(args)
    workflow(**kwargs)


def get_parser() -> ArgumentParser:
    docstr = """Example:
             heudiconv -d 'rawdata/{subject}' -o . -f heuristic.py -s s1 s2 s3"""
    parser = ArgumentParser(description=docstr)
    parser.add_argument("--version", action="version", version=__version__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-d",
        "--dicom_dir_template",
        dest="dicom_dir_template",
        help="Location of dicomdir that can be indexed with subject id "
        "{subject} and session {session}. Tarballs (can be compressed) "
        "are supported in addition to directory. All matching tarballs "
        "for a subject are extracted and their content processed in a "
        "single pass. If multiple tarballs are found, each is assumed to "
        "be a separate session and the --ses argument is ignored. Note "
        "that you might need to surround the value with quotes to avoid "
        "{...} being considered by shell",
    )
    group.add_argument(
        "--files",
        nargs="*",
        help="Files (tarballs, dicoms) or directories containing files to "
        "process. Cannot be provided if using --dicom_dir_template.",
    )
    parser.add_argument(
        "-s",
        "--subjects",
        dest="subjs",
        type=str,
        nargs="*",
        help="List of subjects - required for dicom template. If not "
        'provided, DICOMS would first be "sorted" and subject IDs '
        "deduced by the heuristic.",
    )
    parser.add_argument(
        "-c",
        "--converter",
        choices=("dcm2niix", "none"),
        default="dcm2niix",
        help='Tool to use for DICOM conversion. Setting to "none" disables '
        "the actual conversion step -- useful for testing heuristics.",
    )
    parser.add_argument(
        "-o",
        "--outdir",
        default=os.getcwd(),
        help="Output directory for conversion setup (for further "
        "customization and future reference. This directory will refer "
        "to non-anonymized subject IDs.",
    )
    parser.add_argument(
        "-l",
        "--locator",
        default=None,
        help="Study path under outdir. If provided, it overloads the value "
        "provided by the heuristic. If --datalad is enabled, every "
        "directory within locator becomes a super-dataset thus "
        'establishing a hierarchy. Setting to "unknown" will skip that '
        "dataset.",
    )
    parser.add_argument(
        "-a",
        "--conv-outdir",
        default=None,
        help="Output directory for converted files. By default this is "
        "identical to --outdir. This option is most useful in "
        "combination with --anon-cmd.",
    )
    parser.add_argument(
        "--anon-cmd",
        default=None,
        help="Command to run to convert subject IDs used for DICOMs to "
        "anonymized IDs. Such command must take a single argument and "
        "return a single anonymized ID. Also see --conv-outdir.",
    )
    parser.add_argument(
        "-f",
        "--heuristic",
        dest="heuristic",
        help="Name of a known heuristic or path to the Python script "
        "containing heuristic.",
    )
    parser.add_argument(
        "-p",
        "--with-prov",
        action="store_true",
        help="Store additional provenance information. Requires python-rdflib.",
    )
    parser.add_argument(
        "-ss",
        "--ses",
        dest="session",
        default=None,
        help="Session for longitudinal study_sessions. Default is None.",
    )
    parser.add_argument(
        "-b",
        "--bids",
        nargs="*",
        metavar=("BIDSOPTION1", "BIDSOPTION2"),
        choices=["notop"],
        dest="bids_options",
        help="Flag for output into BIDS structure. Can also take BIDS-"
        "specific options, e.g., --bids notop. The only currently "
        'supported options is "notop", which skips creation of '
        "top-level BIDS files. This is useful when running in batch "
        "mode to prevent possible race conditions.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite existing converted files.",
    )
    parser.add_argument(
        "--datalad",
        action="store_true",
        help="Store the entire collection as DataLad dataset(s). Small files "
        "will be committed directly to git, while large to annex. New "
        'version (6) of annex repositories will be used in a "thin" '
        "mode so it would look to mortals as just any other regular "
        "directory (i.e. no symlinks to under .git/annex). For now just "
        "for BIDS mode.",
    )
    parser.add_argument(
        "--dbg",
        action="store_true",
        dest="debug",
        help="Do not catch exceptions and show exception traceback.",
    )
    parser.add_argument(
        "--command",
        choices=(
            "heuristics",
            "heuristic-info",
            "ls",
            "populate-templates",
            "sanitize-jsons",
            "treat-jsons",
            "populate-intended-for",
        ),
        help="Custom action to be performed on provided files instead of "
        "regular operation.",
    )
    parser.add_argument(
        "-g",
        "--grouping",
        default="studyUID",
        choices=("studyUID", "accession_number", "all", "custom"),
        help="How to group dicoms (default: by studyUID).",
    )
    parser.add_argument(
        "--minmeta",
        action="store_true",
        help="Exclude dcmstack meta information in sidecar jsons.",
    )
    parser.add_argument(
        "--random-seed", type=int, default=None, help="Random seed to initialize RNG."
    )
    parser.add_argument(
        "--dcmconfig",
        default=None,
        help="JSON file for additional dcm2niix configuration.",
    )
    submission = parser.add_argument_group("Conversion submission options")
    submission.add_argument(
        "-q",
        "--queue",
        choices=("SLURM", None),
        default=None,
        help="Batch system to submit jobs in parallel.",
    )
    submission.add_argument(
        "--queue-args",
        dest="queue_args",
        default=None,
        help="Additional queue arguments passed as a single string of "
        "space-separated Argument=Value pairs.",
    )
    return parser


if __name__ == "__main__":
    main()
