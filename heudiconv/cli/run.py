import os
import os.path as op
from argparse import ArgumentParser
import sys

from .. import __version__, __packagename__
from ..parser import get_study_sessions
from ..utils import load_heuristic, anonymize_sid, treat_infofile, SeqInfo
from ..convert import prep_conversion
from ..bids import populate_bids_templates, tuneup_bids_json_files
from ..queue import queue_conversion

import inspect
import logging
lgr = logging.getLogger(__name__)

INIT_MSG = "Running {packname} version {version}".format


def is_interactive():
   """Return True if all in/outs are tty"""
   # TODO: check on windows if hasattr check would work correctly and add value:
   return sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()


def setup_exceptionhook():
    """
    Overloads default sys.excepthook with our exceptionhook handler.

    If interactive, our exceptionhook handler will invoke pdb.post_mortem;
    if not interactive, then invokes default handler.
    """
    def _pdb_excepthook(type, value, tb):
        if is_interactive():
            import traceback
            import pdb
            traceback.print_exception(type, value, tb)
            # print()
            pdb.post_mortem(tb)
        else:
            lgr.warning(
              "We cannot setup exception hook since not in interactive mode")

    sys.excepthook = _pdb_excepthook


def process_extra_commands(outdir, args):
    """
    Perform custom command instead of regular operations. Supported commands:
    ['treat-json', 'ls', 'populate-templates']

    Parameters
    ----------
    outdir : String
        Output directory
    args : Namespace
        arguments
    """
    if args.command == 'treat-jsons':
        for f in args.files:
            treat_infofile(f)
    elif args.command == 'ls':
        heuristic = load_heuristic(args.heuristic)
        heuristic_ls = getattr(heuristic, 'ls', None)
        for f in args.files:
            study_sessions = get_study_sessions(
                args.dicom_dir_template, [f], heuristic, outdir,
                args.session, args.subjs, grouping=args.grouping)
            print(f)
            for study_session, sequences in study_sessions.items():
                suf = ''
                if heuristic_ls:
                    suf += heuristic_ls(study_session, sequences)
                print(
                    "\t%s %d sequences%s"
                    % (str(study_session), len(sequences), suf)
                )
    elif args.command == 'populate-templates':
        heuristic = load_heuristic(args.heuristic)
        for f in args.files:
            populate_bids_templates(f, getattr(heuristic, 'DEFAULT_FIELDS', {}))
    elif args.command == 'sanitize-jsons':
        tuneup_bids_json_files(args.files)
    elif args.command == 'heuristics':
        from ..utils import get_known_heuristics_with_descriptions
        for name_desc in get_known_heuristics_with_descriptions().items():
            print("- %s: %s" % name_desc)
    elif args.command == 'heuristic-info':
        from ..utils import get_heuristic_description, get_known_heuristic_names
        if not args.heuristic:
            raise ValueError("Specify heuristic using -f. Known are: %s"
                             % ', '.join(get_known_heuristic_names()))
        print(get_heuristic_description(args.heuristic, full=True))
    else:
        raise ValueError("Unknown command %s", args.command)
    return


def main(argv=None):
    parser = get_parser()
    args = parser.parse_args(argv)
    # exit if nothing to be done
    if not args.files and not args.dicom_dir_template and not args.command:
        lgr.warning("Nothing to be done - displaying usage help")
        parser.print_help()
        sys.exit(1)
    # To be done asap so anything random is deterministic
    if args.random_seed is not None:
        import random
        random.seed(args.random_seed)
        import numpy
        numpy.random.seed(args.random_seed)
    if args.debug:
        lgr.setLevel(logging.DEBUG)
    # Should be possible but only with a single subject -- will be used to
    # override subject deduced from the DICOMs
    if args.files and args.subjs and len(args.subjs) > 1:
        raise ValueError(
            "Unable to processes multiple `--subjects` with files"
        )

    if args.debug:
        setup_exceptionhook()

    process_args(args)


def get_parser():
    docstr = ("""Example:
             heudiconv -d rawdata/{subject} -o . -f heuristic.py -s s1 s2 s3""")
    parser = ArgumentParser(description=docstr)
    parser.add_argument('--version', action='version', version=__version__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-d', '--dicom_dir_template', dest='dicom_dir_template',
                       help='location of dicomdir that can be indexed with '
                       'subject id {subject} and session {session}. Tarballs '
                       '(can be compressed) are supported in addition to '
                       'directory. All matching tarballs for a subject are '
                       'extracted and their content processed in a single pass')
    group.add_argument('--files', nargs='*',
                       help='Files (tarballs, dicoms) or directories '
                       'containing files to process. Cannot be provided if '
                       'using --dicom_dir_template or --subjects')
    parser.add_argument('-s', '--subjects', dest='subjs', type=str, nargs='*',
                        help='list of subjects - required for dicom template. '
                        'If not provided, DICOMS would first be "sorted" and '
                        'subject IDs deduced by the heuristic')
    parser.add_argument('-c', '--converter',
                        default='dcm2niix',
                        choices=('dcm2niix', 'none'),
                        help='tool to use for DICOM conversion. Setting to '
                        '"none" disables the actual conversion step -- useful'
                        'for testing heuristics.')
    parser.add_argument('-o', '--outdir', default=os.getcwd(),
                        help='output directory for conversion setup (for '
                        'further customization and future reference. This '
                        'directory will refer to non-anonymized subject IDs')
    parser.add_argument('-l', '--locator', default=None,
                        help='study path under outdir.  If provided, '
                        'it overloads the value provided by the heuristic. '
                        'If --datalad is enabled, every directory within '
                        'locator becomes a super-dataset thus establishing a '
                        'hierarchy. Setting to "unknown" will skip that dataset')
    parser.add_argument('-a', '--conv-outdir', default=None,
                        help='output directory for converted files. By default '
                        'this is identical to --outdir. This option is most '
                        'useful in combination with --anon-cmd')
    parser.add_argument('--anon-cmd', default=None,
                        help='command to run to convert subject IDs used for '
                        'DICOMs to anonymized IDs. Such command must take a '
                        'single argument and return a single anonymized ID. '
                        'Also see --conv-outdir')
    parser.add_argument('-f', '--heuristic', dest='heuristic',
                        # some commands might not need heuristic
                        # required=True,
                        help='Name of a known heuristic or path to the Python'
                             'script containing heuristic')
    parser.add_argument('-p', '--with-prov', action='store_true',
                        help='Store additional provenance information. '
                        'Requires python-rdflib.')
    parser.add_argument('-ss', '--ses', dest='session', default=None,
                        help='session for longitudinal study_sessions, default '
                        'is none')
    parser.add_argument('-b', '--bids', action='store_true',
                        help='flag for output into BIDS structure')
    parser.add_argument('--overwrite', action='store_true', default=False,
                        help='flag to allow overwriting existing converted files')
    parser.add_argument('--datalad', action='store_true',
                        help='Store the entire collection as DataLad '
                        'dataset(s). Small files will be committed directly to '
                        'git, while large to annex. New version (6) of annex '
                        'repositories will be used in a "thin" mode so it '
                        'would look to mortals as just any other regular '
                        'directory (i.e. no symlinks to under .git/annex).  '
                        'For now just for BIDS mode.')
    parser.add_argument('--dbg', action='store_true', dest='debug',
                        help='Do not catch exceptions and show exception '
                        'traceback')
    parser.add_argument('--command',
                        choices=(
                            'heuristics', 'heuristic-info',
                            'ls', 'populate-templates',
                            'sanitize-jsons', 'treat-jsons',
                        ),
                        help='custom actions to be performed on provided '
                        'files instead of regular operation.')
    parser.add_argument('-g', '--grouping', default='studyUID',
                        choices=('studyUID', 'accession_number'),
                        help='How to group dicoms (default: by studyUID)')
    parser.add_argument('--minmeta', action='store_true',
                        help='Exclude dcmstack meta information in sidecar '
                        'jsons')
    parser.add_argument('--random-seed', type=int, default=None,
                        help='Random seed to initialize RNG')
    submission = parser.add_argument_group('Conversion submission options')
    submission.add_argument('-q', '--queue', default=None,
                            help='select batch system to submit jobs to instead'
                                 ' of running the conversion serially')
    submission.add_argument('--sbargs', dest='sbatch_args', default=None,
                            help='Additional sbatch arguments if running with '
                                 'queue arg')
    return parser


def process_args(args):
    """Given a structure of arguments from the parser perform computation"""

    # Deal with provided files or templates
    # pre-process provided list of files and possibly sort into groups/sessions
    # Group files per each study/sid/session

    outdir = op.abspath(args.outdir)

    if args.command:
        process_extra_commands(outdir, args)
        return

    lgr.info(INIT_MSG(packname=__packagename__,
                      version=__version__))


    #
    # Load heuristic -- better do it asap to make sure it loads correctly
    #
    if not args.heuristic:
        raise RuntimeError("No heuristic specified - add to arguments and rerun")

    heuristic = load_heuristic(args.heuristic)

    study_sessions = get_study_sessions(args.dicom_dir_template, args.files,
                                        heuristic, outdir, args.session,
                                        args.subjs, grouping=args.grouping)

    # extract tarballs, and replace their entries with expanded lists of files
    # TODO: we might need to sort so sessions are ordered???
    lgr.info("Need to process %d study sessions", len(study_sessions))

    # processed_studydirs = set()

    for (locator, session, sid), files_or_seqinfo in study_sessions.items():

        # Allow for session to be overloaded from command line
        if args.session is not None:
            session = args.session
        if args.locator is not None:
            locator = args.locator
        if not len(files_or_seqinfo):
            raise ValueError("nothing to process?")
        # that is how life is ATM :-/ since we don't do sorting if subj
        # template is provided
        if isinstance(files_or_seqinfo, dict):
            assert(isinstance(list(files_or_seqinfo.keys())[0], SeqInfo))
            dicoms = None
            seqinfo = files_or_seqinfo
        else:
            dicoms = files_or_seqinfo
            seqinfo = None

        if locator == 'unknown':
            lgr.warning("Skipping unknown locator dataset")
            continue

        if args.queue:
            if seqinfo and not dicoms:
                # flatten them all and provide into batching, which again
                # would group them... heh
                dicoms = sum(seqinfo.values(), [])
                raise NotImplementedError(
                    "we already grouped them so need to add a switch to avoid "
                    "any grouping, so no outdir prefix doubled etc")

            progname = op.abspath(inspect.getfile(inspect.currentframe()))

            queue_conversion(progname,
                             args.queue,
                             study_outdir,
                             heuristic.filename,
                             dicoms,
                             sid,
                             args.anon_cmd,
                             args.converter,
                             session,
                             args.with_prov,
                             args.bids)
            continue

        anon_sid = anonymize_sid(sid, args.anon_cmd) if args.anon_cmd else None
        if args.anon_cmd:
            lgr.info('Anonymized {} to {}'.format(sid, anon_sid))

        study_outdir = op.join(outdir, locator or '')
        anon_outdir = args.conv_outdir or outdir
        anon_study_outdir = op.join(anon_outdir, locator or '')

        # TODO: --datalad  cmdline option, which would take care about initiating
        # the outdir -> study_outdir datasets if not yet there
        if args.datalad:
            from ..external.dlad import prepare_datalad
            dlad_sid = sid if not anon_sid else anon_sid
            dl_msg = prepare_datalad(anon_study_outdir, anon_outdir, dlad_sid,
                                     session, seqinfo, dicoms, args.bids)

        lgr.info("PROCESSING STARTS: {0}".format(
            str(dict(subject=sid, outdir=study_outdir, session=session))))

        prep_conversion(sid,
                        dicoms,
                        study_outdir,
                        heuristic,
                        converter=args.converter,
                        anon_sid=anon_sid,
                        anon_outdir=anon_study_outdir,
                        with_prov=args.with_prov,
                        ses=session,
                        bids=args.bids,
                        seqinfo=seqinfo,
                        min_meta=args.minmeta,
                        overwrite=args.overwrite,)

        lgr.info("PROCESSING DONE: {0}".format(
            str(dict(subject=sid, outdir=study_outdir, session=session))))

        if args.datalad:
            from ..external.dlad import add_to_datalad
            msg = "Converted subject %s" % dl_msg
            # TODO:  whenever propagate to supers work -- do just
            # ds.save(msg=msg)
            #  also in batch mode might fail since we have no locking ATM
            #  and theoretically no need actually to save entire study
            #  we just need that
            add_to_datalad(outdir, study_outdir, msg, args.bids)

    # if args.bids:
    #     # Let's populate BIDS templates for folks to take care about
    #     for study_outdir in processed_studydirs:
    #         populate_bids_templates(study_outdir)
    #
    # TODO: record_collection of the sid/session although that information
    # is pretty much present in .heudiconv/SUBJECT/info so we could just poke there


if __name__ == "__main__":
    main()
