import os
import logging
from argparse import ArgumentParser

# TODO: set up logger

def get_parser():
    docstr = '\n'.join((__doc__,
                        """
                                   Example:

                                   heudiconv -d rawdata/{subject} -o . -f
                                   heuristic.py -s s1 s2
                        s3
                        """))
    parser = ArgumentParser(description=docstr)
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('-d', '--dicom_dir_template',
                        dest='dicom_dir_template',
                        required=False,
                        help='''location of dicomdir that can be indexed with
                        subject id {subject} and session {session}.
                        Tarballs (can be compressed) are supported
                        in addition to directory. All matching tarballs for a
                        subject are extracted and their content processed in
                        a single pass''')
    parser.add_argument('-s', '--subjects', dest='subjs',
                        type=str, nargs='*',
                        help='list of subjects. If not provided, DICOMS would '
                             'first be "sorted" and subject IDs deduced by the '
                             'heuristic')
    parser.add_argument('-c', '--converter', default='dcm2niix',
                        choices=('dcm2niix', 'none'),
                        help='''tool to use for dicom conversion. Setting to
                        "none" disables the actual conversion step -- useful
                        for testing heuristics.''')
    parser.add_argument('-o', '--outdir', default=os.getcwd(),
                        help='''output directory for conversion setup (for
                        further customization and future reference. This
                        directory will refer to non-anonymized subject IDs''')
    parser.add_argument('-a', '--conv-outdir', default=None,
                        help='''output directory for converted files. By
                        default this is identical to --outdir. This option is
                        most useful in combination with --anon-cmd''')
    parser.add_argument('--anon-cmd', default=None,
                        help='''command to run to convert subject IDs used for
                        DICOMs to anonymmized IDs. Such command must take a
                        single argument and return a single anonymized ID.
                        Also see --conv-outdir''')
    parser.add_argument('-f', '--heuristic', dest='heuristic_file',
                        required=True,
                        help='python script containing heuristic')
    parser.add_argument('-q', '--queue', default=None,
                        help='''select batch system to submit jobs to instead
                        of running the conversion serially''')
    parser.add_argument('-p', '--with-prov', action='store_true',
                        help='''Store additional provenance information.
                        Requires python-rdflib.''')
    parser.add_argument('-ss', '--ses', dest='session', default=None,
                        help='''session for longitudinal study_sessions,
                        default is none''')
    parser.add_argument('-b', '--bids', action='store_true',
                        help='''flag for output into BIDS structure''')
    parser.add_argument('--overwrite', action='store_true',
                        help='''flag to allow overwrite existing files''')
    parser.add_argument('--datalad', action='store_true',
                        help='''Store the entire collection as DataLad
                        dataset(s). Small files will be committed directly to
                        git, while large to annex. New version (6) of annex
                        repositories will be used in a "thin" mode so it would
                        look to mortals as just any other regular directory
                        (i.e. no symlinks to under .git/annex).  For now just
                        for BIDS mode.''')
    parser.add_argument('--dbg', action='store_true', dest='debug',
                        help='''Do not catch exceptions and show
                        exception traceback''')
    parser.add_argument('--command',
                        choices=('treat-json', 'ls', 'populate-templates'),
                        help='''custom actions to be performed on provided
                        files instead of regular operation.''')
    parser.add_argument('-g', '--grouping',
                        default='studyUID',
                        choices=('studyUID', 'accession_number'),
                        help='''How to group dicoms (default: by studyUID)''')
    parser.add_argument('files', nargs='*',
                        help='''Files (tarballs, dicoms) or directories
                        containing files to process. Specify one of the
                        --dicom_dir_template or files (not both)''')
    parser.add_argument('--minmeta', action='store_true',
                        help='''Exclude dcmstack's meta information in
                        sidecar jsons''')
    return parser
