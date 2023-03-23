import logging
import os.path as op
import sys
from glob import glob

from . import __version__, __packagename__
from .bids import populate_bids_templates, tuneup_bids_json_files, populate_intended_for
from .convert import prep_conversion
from .due import due, Doi
from .parser import get_study_sessions
from .queue import queue_conversion
from .utils import anonymize_sid, load_heuristic, treat_infofile, SeqInfo

lgr = logging.getLogger(__name__)


INIT_MSG = "Running {packname} version {version} latest {latest}".format


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


def process_extra_commands(outdir, command, files, dicom_dir_template,
                           heuristic, session, subjs, grouping):
    """
    Perform custom command instead of regular operations. Supported commands:
    ['treat-json', 'ls', 'populate-templates', 'populate-intended-for']

    Parameters
    ----------
    outdir : str
        Output directory
    command : {'treat-json', 'ls', 'populate-templates', 'populate-intended-for'}
        Heudiconv command to run
    files : list of str
        List of files
    dicom_dir_template : str
        Location of dicomdir that can be indexed with subject id
        {subject} and session {session}. Tarballs (can be compressed)
        are supported in addition to directory. All matching tarballs
        for a subject are extracted and their content processed in a
        single pass. If multiple tarballs are found, each is assumed to
        be a separate session and the 'session' argument is ignored.
    heuristic : str
        Path to heuristic file or name of builtin heuristic.
    session : str
        Session identifier
    subjs : list of str
        List of subject identifiers
    grouping : {'studyUID', 'accession_number', 'all', 'custom'}
        How to group dicoms.
    """
    if command == 'treat-jsons':
        for f in files:
            treat_infofile(f)
    elif command == 'ls':
        ensure_heuristic_arg(heuristic)
        heuristic = load_heuristic(heuristic)
        heuristic_ls = getattr(heuristic, 'ls', None)
        for f in files:
            study_sessions = get_study_sessions(
                dicom_dir_template, [f], heuristic, outdir,
                session, subjs, grouping=grouping)
            print(f)
            for study_session, sequences in study_sessions.items():
                suf = ''
                if heuristic_ls:
                    suf += heuristic_ls(study_session, sequences)
                print(
                    "\t%s %d sequences%s"
                    % (str(study_session), len(sequences), suf)
                )
    elif command == 'ls-studysessions':
        ensure_heuristic_arg(heuristic)
        heuristic = load_heuristic(heuristic)
        # heuristic_ls = getattr(heuristic, 'ls', None)
        study_sessions = get_study_sessions(
            dicom_dir_template, files, heuristic, outdir,
            session, subjs, grouping=grouping)
        for ss, seqinfos in study_sessions.items():
            print(f"{ss}:")
            # deduce unique attributes
            from heudiconv.utils import get_dicts_intersection
            seqinfo_dicts = [s._asdict() for s in seqinfos]
            common_seqinfo = get_dicts_intersection(seqinfo_dicts)

            diff_seqinfo = []
            for sd in seqinfo_dicts:
                diff = {
                    k: v for k, v in sd.items()
                    if (k not in common_seqinfo) and
                        (k not in {'total_files_till_now', 'series_uid'})}
                # some transformations might be needed to please pyout
                for k, v in diff.items():
                    if isinstance(v, tuple):
                        diff[k] = ', '.join(v)
                diff_seqinfo.append(diff)

            if diff_seqinfo == [{}]:
                print(f" only common: {common_seqinfo}")
                continue
            from pyout import Tabular
            with Tabular(
                columns=['example_dcm_file', 'series_files', 'series_id', 'protocol_name', 'series_description'],
                style={"header_": dict(bold=True,),
                       "example_dcm_file": dict(bold=True,),
                       "image_type": dict(transform=str)},
                mode='final'
            ) as out:
                for diffs, files in zip(diff_seqinfo, seqinfos.values()):
                    out(diffs)
                    # print(f"{path_id} {diffs}")
    elif command == 'populate-templates':
        ensure_heuristic_arg(heuristic)
        heuristic = load_heuristic(heuristic)
        for f in files:
            populate_bids_templates(f, getattr(heuristic, 'DEFAULT_FIELDS', {}))
    elif command == 'sanitize-jsons':
        tuneup_bids_json_files(files)
    elif command == 'heuristics':
        from .utils import get_known_heuristics_with_descriptions
        for name_desc in get_known_heuristics_with_descriptions().items():
            print("- %s: %s" % name_desc)
    elif command == 'heuristic-info':
        ensure_heuristic_arg(heuristic)
        from .utils import get_heuristic_description
        print(get_heuristic_description(heuristic, full=True))
    elif command == 'populate-intended-for':
        kwargs = {}
        if heuristic:
            heuristic = load_heuristic(heuristic)
            kwargs = getattr(heuristic, 'POPULATE_INTENDED_FOR_OPTS', {})
        if not subjs:
            subjs = [
                # search outdir for 'sub-*'; if it is a directory (not a regular file), remove
                # the initial 'sub-':
                op.basename(s)[len('sub-'):] for s in glob(op.join(outdir, 'sub-*')) if op.isdir(s)
            ]
            # read the subjects from the participants.tsv file to compare:
            participants_tsv = op.join(outdir, 'participants.tsv')
            if op.lexists(participants_tsv):
                with open(participants_tsv, 'r') as f:
                    # read header line and find index for 'participant_id':
                    participant_id_index = f.readline().split('\t').index('participant_id')
                    # read all participants, removing the initial 'sub-':
                    known_subjects = [
                        l.split('\t')[participant_id_index][len('sub-'):] for l in f.readlines()
                    ]
                if not set(subjs) == set(known_subjects):
                    # issue a warning, but continue with the 'subjs' list (the subjects for
                    # which there is data):
                    lgr.warning(
                        "'participants.tsv' contents are not identical to subjects found "
                        "in the BIDS dataset %s", outdir
                    )

        for subj in subjs:
            subject_path = op.join(outdir, 'sub-' + subj)
            if session:
                session_paths = [op.join(subject_path, 'ses-' + session)]
            else:
                # check to see if the data for this subject is organized by sessions; if not
                # just use the subject_path
                session_paths = [
                    s for s in glob(op.join(subject_path, 'ses-*')) if op.isdir(s)
                ] or [subject_path]
            for session_path in session_paths:
                populate_intended_for(session_path, **kwargs)
    else:
        raise ValueError("Unknown command %s" % command)
    return


def ensure_heuristic_arg(heuristic=None):
    """
    Check that the heuristic argument was provided.
    """
    from .utils import get_known_heuristic_names
    if not heuristic:
        raise ValueError("Specify heuristic using -f. Known are: %s"
                         % ', '.join(get_known_heuristic_names()))


@due.dcite(
    Doi('10.5281/zenodo.1012598'),
    path='heudiconv',
    description='Flexible DICOM converter for organizing brain imaging data',
    version=__version__,
    cite_module=True)
def workflow(*, dicom_dir_template=None, files=None, subjs=None,
             converter='dcm2niix', outdir='.', locator=None, conv_outdir=None,
             anon_cmd=None, heuristic=None, with_prov=False, session=None,
             bids_options=None, overwrite=False, datalad=False, debug=False,
             command=None, grouping='studyUID', minmeta=False,
             random_seed=None, dcmconfig=None, queue=None, queue_args=None):
    """Run the HeuDiConv conversion workflow.

    Parameters
    ----------
    dicom_dir_template : str or None, optional
        Location of dicomdir that can be indexed with subject id
        {subject} and session {session}. Tarballs (can be compressed)
        are supported in addition to directory. All matching tarballs
        for a subject are extracted and their content processed in a
        single pass. If multiple tarballs are found, each is assumed to
        be a separate session and the 'session' argument is ignored.
        Mutually exclusive with 'files'. Default is None.
    files : list or None, optional
        Files (tarballs, dicoms) or directories containing files to
        process. Mutually exclusive with 'dicom_dir_template'. Default is None.
    subjs : list or None, optional
        List of subjects - required for dicom template. If not
        provided, DICOMS would first be "sorted" and subject IDs
        deduced by the heuristic. Default is None.
    converter : {'dcm2niix', None}, optional
        Tool to use for DICOM conversion. Setting to None disables
        the actual conversion step -- useful for testing heuristics.
        Default is None.
    outdir : str, optional
        Output directory for conversion setup (for further
        customization and future reference. This directory will refer
        to non-anonymized subject IDs.
        Default is '.' (current working directory).
    locator : str or 'unknown' or None, optional
        Study path under outdir. If provided, it overloads the value
        provided by the heuristic. If 'datalad=True', every
        directory within locator becomes a super-dataset thus
        establishing a hierarchy. Setting to "unknown" will skip that
        dataset. Default is None.
    conv_outdir : str or None, optional
        Output directory for converted files. By default this is
        identical to --outdir. This option is most useful in
        combination with 'anon_cmd'. Default is None.
    anon_cmd : str or None, optional
        Command to run to convert subject IDs used for DICOMs to
        anonymized IDs. Such command must take a single argument and
        return a single anonymized ID. Also see 'conv_outdir'. Default is None.
    heuristic : str or None, optional
        Name of a known heuristic or path to the Python script containing
        heuristic. Default is None.
    with_prov : bool, optional
        Store additional provenance information. Requires python-rdflib.
        Default is False.
    session : str or None, optional
        Session for longitudinal study_sessions. Default is None.
    bids_options : str or None, optional
        Flag for output into BIDS structure. Can also take BIDS-
        specific options, e.g., --bids notop. The only currently
        supported options is "notop", which skips creation of
        top-level BIDS files. This is useful when running in batch
        mode to prevent possible race conditions. Default is None.
    overwrite : bool, optional
        Overwrite existing converted files. Default is False.
    datalad : bool, optional
        Store the entire collection as DataLad dataset(s). Small files
        will be committed directly to git, while large to annex. New
        version (6) of annex repositories will be used in a "thin"
        mode so it would look to mortals as just any other regular
        directory (i.e. no symlinks to under .git/annex). For now just
        for BIDS mode. Default is False.
    debug : bool, optional
        Do not catch exceptions and show exception traceback. Default is False.
    command : {'heuristics', 'heuristic-info', 'ls', 'populate-templates',
               'sanitize-jsons', 'treat-jsons', 'populate-intended-for', None}, optional
        Custom action to be performed on provided files instead of regular
        operation. Default is None.
    grouping : {'studyUID', 'accession_number', 'all', 'custom'}, optional
        How to group dicoms. Default is 'studyUID'.
    minmeta : bool, optional
        Exclude dcmstack meta information in sidecar jsons. Default is False.
    random_seed : int or None, optional
        Random seed to initialize RNG. Default is None.
    dcmconfig : str or None, optional
        JSON file for additional dcm2niix configuration. Default is None.
    queue : {'SLURM', None}, optional
        Batch system to submit jobs in parallel. Default is None.
        If set, will cause scheduling of conversion and return without performing
        any further action.
    queue_args : str or None, optional
        Additional queue arguments passed as single string of space-separated
        Argument=Value pairs. Default is None.

    Notes
    -----
    All parameters in this function must be called as keyword arguments.
    """

    # To be done asap so anything random is deterministic
    if random_seed is not None:
        import random
        random.seed(random_seed)
        import numpy
        numpy.random.seed(random_seed)
    # Ensure only supported bids options are passed
    if debug:
        lgr.setLevel(logging.DEBUG)
    # Should be possible but only with a single subject -- will be used to
    # override subject deduced from the DICOMs
    if files and subjs and len(subjs) > 1:
        raise ValueError(
            "Unable to processes multiple `--subjects` with files"
        )

    if debug:
        setup_exceptionhook()

    # Deal with provided files or templates
    # pre-process provided list of files and possibly sort into groups/sessions
    # Group files per each study/sid/session

    outdir = op.abspath(outdir)

    latest = None
    try:
        import etelemetry
        latest = etelemetry.get_project("nipy/heudiconv")
    except Exception as e:
        lgr.warning("Could not check for version updates: %s", str(e))

    lgr.info(INIT_MSG(packname=__packagename__,
                      version=__version__,
                      latest=(latest or {}).get("version", "Unknown")))

    if command:
        process_extra_commands(outdir, command, files, dicom_dir_template,
                               heuristic, session, subjs, grouping)
        return
    #
    # Load heuristic -- better do it asap to make sure it loads correctly
    #
    if not heuristic:
        raise RuntimeError("No heuristic specified - add to arguments and rerun")

    if queue:
        lgr.info("Queuing %s conversion", queue)
        iterarg, iterables = ("files", len(files)) if files else \
                             ("subjects", len(subjs))
        queue_conversion(queue, iterarg, iterables, queue_args)
        return

    heuristic = load_heuristic(heuristic)

    study_sessions = get_study_sessions(dicom_dir_template, files,
                                        heuristic, outdir, session,
                                        subjs, grouping=grouping)

    # extract tarballs, and replace their entries with expanded lists of files
    # TODO: we might need to sort so sessions are ordered???
    lgr.info("Need to process %d study sessions", len(study_sessions))

    # processed_studydirs = set()

    locator_manual, session_manual = locator, session
    for (locator, session, sid), files_or_seqinfo in study_sessions.items():

        # Allow for session to be overloaded from command line
        if session_manual is not None:
            session = session_manual
        if locator_manual is not None:
            locator = locator_manual
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

        anon_sid = anonymize_sid(sid, anon_cmd) if anon_cmd else None
        if anon_cmd:
            lgr.info('Anonymized {} to {}'.format(sid, anon_sid))

        study_outdir = op.join(outdir, locator or '')
        anon_outdir = conv_outdir or outdir
        anon_study_outdir = op.join(anon_outdir, locator or '')

        if datalad:
            from .external.dlad import prepare_datalad
            dlad_sid = sid if not anon_sid else anon_sid
            dl_msg = prepare_datalad(anon_study_outdir, anon_outdir, dlad_sid,
                                     session, seqinfo, dicoms,
                                     bids_options)

        lgr.info("PROCESSING STARTS: {0}".format(
            str(dict(subject=sid, outdir=study_outdir, session=session))))

        prep_conversion(sid,
                        dicoms,
                        study_outdir,
                        heuristic,
                        converter=converter,
                        anon_sid=anon_sid,
                        anon_outdir=anon_study_outdir,
                        with_prov=with_prov,
                        ses=session,
                        bids_options=bids_options,
                        seqinfo=seqinfo,
                        min_meta=minmeta,
                        overwrite=overwrite,
                        dcmconfig=dcmconfig,
                        grouping=grouping,)

        lgr.info("PROCESSING DONE: {0}".format(
            str(dict(subject=sid, outdir=study_outdir, session=session))))

        if datalad:
            from .external.dlad import add_to_datalad
            msg = "Converted subject %s" % dl_msg
            # TODO:  whenever propagate to supers work -- do just
            # ds.save(msg=msg)
            #  also in batch mode might fail since we have no locking ATM
            #  and theoretically no need actually to save entire study
            #  we just need that
            add_to_datalad(outdir, study_outdir, msg, bids_options)

    # if bids:
    #     # Let's populate BIDS templates for folks to take care about
    #     for study_outdir in processed_studydirs:
    #         populate_bids_templates(study_outdir)
    #
    # TODO: record_collection of the sid/session although that information
    # is pretty much present in .heudiconv/SUBJECT/info so we could just poke there
