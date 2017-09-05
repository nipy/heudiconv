def process_args(args):
    """Given a structure of arguments from the parser perform computation"""

    #
    # Deal with provided files or templates
    #

    #
    # pre-process provided list of files and possibly sort into groups/sessions
    #

    # Group files per each study/sid/session

    dicom_dir_template = args.dicom_dir_template
    files_opt = args.files
    session = args.session
    subjs = args.subjs
    outdir = os.path.abspath(args.outdir)
    grouping = args.grouping

    if args.command:
        # custom mode of operation
        if args.command == 'treat-json':
            for f in files_opt:
                treat_infofile(f)
        elif args.command == 'ls':
            heuristic = load_heuristic(os.path.realpath(args.heuristic_file))
            heuristic_ls = getattr(heuristic, 'ls', None)
            for f in files_opt:
                study_sessions = get_study_sessions(
                    dicom_dir_template, [f],
                    heuristic, outdir, session, subjs, grouping=grouping)
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
            heuristic = load_heuristic(os.path.realpath(args.heuristic_file))
            for f in files_opt:
                populate_bids_templates(
                    f,
                    getattr(heuristic, 'DEFAULT_FIELDS', {})
                )
        elif args.command == 'sanitize-jsons':
            tuneup_bids_json_files(files_opt)
        else:
            raise ValueError("Unknown command %s", args.command)
        return

    #
    # Load heuristic -- better do it asap to make sure it loads correctly
    #
    heuristic = load_heuristic(os.path.realpath(args.heuristic_file))
    # TODO: Move into a function!
    study_sessions = get_study_sessions(
        dicom_dir_template, files_opt,
        heuristic, outdir, session, subjs,
        grouping=grouping)
    # extract tarballs, and replace their entries with expanded lists of files
    # TODO: we might need to sort so sessions are ordered???
    lgr.info("Need to process %d study sessions", len(study_sessions))

    #
    # processed_studydirs = set()

    for (locator, session, sid), files_or_seqinfo in study_sessions.items():

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
            lgr.warning("Skipping  unknown  locator dataset")
            continue

        if args.queue:
            if seqinfo and not dicoms:
                # flatten them all and provide into batching, which again
                # would group them... heh
                dicoms = sum(seqinfo.values(), [])
                # so
                raise NotImplementedError(
                    "we already groupped them so need to add a switch to avoid "
                    "any groupping, so no outdir prefix doubled etc"
                )
            # TODO This needs to be updated to better scale with additional args
            progname = os.path.abspath(inspect.getfile(inspect.currentframe()))
            convertcmd = ' '.join(['python', progname,
                                   '-o', study_outdir,
                                   '-f', heuristic.filename,
                                   '-s', sid,
                                   '--anon-cmd', args.anon_cmd,
                                   '-c', args.converter])
            if session:
                convertcmd += " --ses '%s'" % session
            if args.with_prov:
                convertcmd += " --with-prov"
            if args.bids:
                convertcmd += " --bids"
            convertcmd += ["'%s'" % f for f in dicoms]

            script_file = 'dicom-%s.sh' % sid
            with open(script_file, 'wt') as fp:
                fp.writelines(['#!/bin/bash\n', convertcmd])
            outcmd = 'sbatch -J dicom-%s -p %s -N1 -c2 --mem=20G %s' \
                     % (sid, args.queue, script_file)
            os.system(outcmd)
            continue

        anon_sid = get_annonimized_sid(sid, args.anon_cmd)

        study_outdir = opj(outdir, locator or '')

        anon_outdir = args.conv_outdir or outdir
        anon_study_outdir = opj(anon_outdir, locator or '')

        # TODO: --datalad  cmdline option, which would take care about initiating
        # the outdir -> study_outdir datasets if not yet there
        if args.datalad:
            datalad_msg_suf = ' %s' % anon_sid
            if session:
                datalad_msg_suf += ", session %s" % session
            if seqinfo:
                datalad_msg_suf += ", %d sequences" % len(seqinfo)
            datalad_msg_suf += ", %d dicoms" % (
                len(sum(seqinfo.values(), [])) if seqinfo else len(dicoms)
            )
            from datalad.api import Dataset
            ds = Dataset(anon_study_outdir)
            if not exists(anon_outdir) or not ds.is_installed():
                add_to_datalad(
                    anon_outdir, anon_study_outdir,
                    msg="Preparing for %s" % datalad_msg_suf,
                    bids=args.bids)
        lgr.info("PROCESSING STARTS: {0}".format(
            str(dict(subject=sid, outdir=study_outdir, session=session))))
        convert_dicoms(
                   sid,
                   dicoms,
                   study_outdir,
                   heuristic=heuristic,
                   converter=args.converter,
                   anon_sid=anon_sid,
                   anon_outdir=anon_study_outdir,
                   with_prov=args.with_prov,
                   ses=session,
                   is_bids=args.bids,
                   seqinfo=seqinfo,
                   min_meta=args.minmeta)
        lgr.info("PROCESSING DONE: {0}".format(
            str(dict(subject=sid, outdir=study_outdir, session=session))))

        if args.datalad:
            msg = "Converted subject %s" % datalad_msg_suf
            # TODO:  whenever propagate to supers work -- do just
            # ds.save(msg=msg)
            #  also in batch mode might fail since we have no locking ATM
            #  and theoretically no need actually to save entire study
            #  we just need that
            add_to_datalad(outdir, study_outdir, msg=msg, bids=args.bids)

    # if args.bids:
    #     # Let's populate BIDS templates for folks to take care about
    #     for study_outdir in processed_studydirs:
    #         populate_bids_templates(study_outdir)
    #
    #         # TODO: record_collection of the sid/session although that information
    #         # is pretty much present in .heudiconv/SUBJECT/info so we could just poke there

    tempdirs.cleanup()
