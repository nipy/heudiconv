""" Helper functions for running of heudiconv """
import sys
import os

def is_interactive():
   """Return True if all in/outs are tty"""
   # TODO: check on windows if hasattr check would work correctly and add value:
   #
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
            print()
            pdb.post_mortem(tb)
        else:
            lgr.warn(
              "We cannot setup exception hook since not in interactive mode")
            _sys_excepthook(type, value, tb)

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
    if args.command == 'treat-json':
        for f in args.files:
            treat_infofile(f)
    elif args.command == 'ls':
        heuristic = load_heuristic(os.path.realpath(args.heuristic_file))
        heuristic_ls = getattr(heuristic, 'ls', None)
        for f in args.files:
            study_sessions = get_study_sessions(
                args.dicom_dir_template, [f], heuristic, outdir,
                args.session, args.subjs, grouping=args.grouping)
            # print(f)
            for study_session, sequences in study_sessions.items():
                suf = ''
                if heuristic_ls:
                    suf += heuristic_ls(study_session, sequences)
                print(
                    "\t%s %d sequences%s"
                    % (str(study_session), len(sequences), suf)
                )
    elif args.command == 'populate-templates':
        heuristic = load_heuristic(os.path.realpath(args.heuristic_file))
        for f in args.files:
            populate_bids_templates(f, getattr(heuristic, 'DEFAULT_FIELDS', {}))
    elif args.command == 'sanitize-jsons':
        tuneup_bids_json_files(args.files)
    else:
        raise ValueError("Unknown command %s", args.command)
    return
