import os

from collections import defaultdict

import logging
lgr = logging.getLogger('heudiconv')


def create_key(subdir, file_suffix, outtype=('nii.gz', 'dicom'),
               annotation_classes=None):
    if not subdir:
        raise ValueError('subdir must be a valid format string')
    # may be even add "performing physician" if defined??
    template = "{bids_subject_session_dir}/" \
               "%s/{bids_subject_session_prefix}_%s" % (subdir, file_suffix)
    return template, outtype, annotation_classes


# XXX we killed session indicator!  what should we do now?!!!
# WE DON:T NEED IT -- it will be provided into conversion_info as `session`
# So we just need subdir and file_suffix!
def infotodict(seqinfo):
    """Heuristic evaluator for determining which runs belong where
    
    allowed template fields - follow python string module: 
    
    item: index within category 
    subject: participant id 
    seqitem: run number during scanning
    subindex: sub index within group
    session: scan index for longitudinal acq
    """
    lgr.info("Processing %d seqinfo entries", len(seqinfo))
    and_dicom = ('dicom', 'nii.gz')

    info = defaultdict(list)
    skipped, skipped_unknown = [], []
    current_run = 0
    run_label = None   # run-

    for s in seqinfo:
        template = None
        suffix = ''
        seq = []

        # figure out type of image from s.image_info -- just for checking ATM
        # since we primarily rely on encoded in the protocol name information
        image_type_modality = {
            'P': 'fmap',
            'FMRI': 'func',
            'MPR': 'anat',
            # 'M': 'func',  -- can be for scout, anat, bold
            'DIFFUSION': 'dwi',
            'MIP_SAG': 'anat',  # angiography
            'MIP_COR': 'anat',  # angiography
            'MIP_TRA': 'anat',  # angiography
        }.get(s.image_type[2], None)

        protocol_name_tuned = s.protocol_name
        # Few common replacements
        if protocol_name_tuned in {'AAHead_Scout'}:
            protocol_name_tuned = 'anat-scout'

        regd = parse_dbic_protocol_name(protocol_name_tuned)

        if s.image_type[2].startswith('MIP'):
            regd['acq'] = regd.get('acq', '') + s.image_type[2]

        if not regd:
            skipped_unknown.append(s.series_id)
            continue

        modality = regd.pop('modality')
        modality_label = regd.pop('modality_label', None)

        if image_type_modality and modality != image_type_modality:
            lgr.warning(
                "Deduced modality to be %s from DICOM, but got %s out of %s",
                image_type_modality, modality, protocol_name_tuned)

        if s.is_derived:
            # Let's for now stash those close to original images
            # TODO: we might want a separate tree for all of this!?
            # so more of a parameter to the create_key
            modality += '/derivative'
            # just keep it lower case and without special characters
            # XXXX what for???
            seq.append(s.series_description.lower())

        # analyze s.protocol_name (series_id is based on it) for full name mapping etc
        if modality == 'func' and not modality_label:
            if '_pace_' in protocol_name_tuned:
                modality_label = 'pace'  # or should it be part of seq-
            else:
                # assume bold by default
                modality_label = 'bold'

        run = regd.get('run')
        if run is not None:
            # so we have an indicator for a run
            if run == '+':
                current_run += 1
            elif run == '=':
                pass
            elif run.isdigit():
                current_run_ = int(run)
                if current_run_ < current_run:
                    lgr.warning(
                        "Previous run (%s) was larger than explicitly specified %s",
                        current_run, current_run_)
                current_run = current_run_
            else:
                raise ValueError(
                    "Don't know how to deal with run specification %s" % repr(run))
            if isinstance(current_run, str) and current_run.isdigit():
                current_run = int(current_run)
            run_label = "run-" + ("%02d" % current_run
                                  if isinstance(current_run, int)
                                  else current_run)

        suffix_parts = [
            None if not regd.get('task') else "task-%s" % regd['task'],
            None if not regd.get('acq') else "acq-%s" % regd['acq'],
            regd.get('bids'),
            run_label,
            modality_label,
        ]
        # filter tose which are None, and join with _
        suffix = '_'.join(filter(bool, suffix_parts))

        # # .series_description in case of
        # sdesc = s.study_description
        # # temporary aliases for those phantoms which we already collected
        # # so we rename them into this
        # #MAPPING
        #
        # # the idea ias to have sequence names in the format like
        # # bids_<subdir>_bidsrecord
        # # in bids record we could have  _run[+=]
        # #  which would say to either increment run number from already encountered
        # #  or reuse the last one
        # if seq:
        #     suffix += 'seq-%s' % ('+'.join(seq))

        # some are ok to skip and not to whine
        if "_Scout" in s.series_description:
            skipped.append(s.series_id)
            lgr.debug("Ignoring %s", s.series_id)
        else:
            template = create_key(modality, suffix)
            info[template].append(s.series_id)

    info = dict(info)  # convert to dict since outside functionality depends on it being a basic dict
    if skipped:
        lgr.info("Skipped %d sequences: %s" % (len(skipped), skipped))
    if skipped_unknown:
        lgr.warning("Could not figure out where to stick %d sequences: %s" %
                    (len(skipped_unknown), skipped_unknown))
    return info


def get_unique(seqinfos, attr):
    """Given a list of seqinfos, which must have come from a single study
    get specific attr, which must be unique across all of the entries

    If not -- fail!

    """
    values = set(getattr(si, attr) for si in seqinfos)
    assert (len(values) == 1)
    return values.pop()


# TODO: might need to do groupping per each session and return here multiple
# hits, or may be we could just somehow demarkate that it will be multisession
# one and so then later value parsed (again) in infotodict  would be used???
def infotoids(seqinfos, outputdir):
    # decide on subjid and session based on patient_id
    lgr.info("Processing sequence infos to deduce study/session")
    study_description = get_unique(seqinfos, 'study_description')
    subject = get_unique(seqinfos, 'patient_id')
    # TODO:  fix up subject id if missing some 0s
    locator = study_description.replace('^', '/')

    # TODO: actually check if given study is study we would care about
    # and if not -- we should throw some ???? exception

    # So -- use `outputdir` and locator etc to see if for a given locator/subject
    # and possible ses+ in the sequence names, so we would provide a sequence
    # So might need to go through  parse_dbic_protocol_name(s.protocol_name)
    # to figure out presence of sessions.
    ses_markers = [
        parse_dbic_protocol_name(s.protocol_name).get('session', None) for s in seqinfos
        ]
    ses_markers = filter(bool, ses_markers)  # only present ones

    session = None
    if ses_markers:
        # we have a session or possibly more than one even
        # let's figure out which case we have
        nonsign_vals = set(ses_markers).difference('+=')
        if nonsign_vals:
            if set(ses_markers).intersection('+='):
                raise NotImplementedError(
                    "Should not mix hardcoded session markers with incremental ones (+=)"
                )
            # although we might want an explicit '=' to note the same session as
            # mentioned before?
            if len(nonsign_vals) > 1:
                raise NotImplementedError(
                    "Cannot deal with multiple sessions in the same study yet!")
            assert len(ses_markers) == 1
            session = ses_markers[0]
        else:
            # TODO - I think we are doomed to go through the sequence and split
            # ... actually the same as with nonsign_vals, we just would need to figure
            # out initial one if sign ones, and should make use of knowing
            # outputdir
            #raise NotImplementedError()
            # Let's be lazy for now just to get somewhere
            session = '001'

    return {
        # TODO: request info on study from the JedCap
        'locator': locator,
        # Sessions to be deduced yet from the names etc TODO
        'session': session,
        'subject': subject,
    }


def parse_dbic_protocol_name(protocol_name):
    """Parse protocol name
    """

    # Parse the name according to our convention
    # https://docs.google.com/document/d/1R54cgOe481oygYVZxI7NHrifDyFUZAjOBwCTu7M7y48/edit?usp=sharing
    import re

    # TODO -- redo without mandating order of e.g. _run vs _task to go first,
    # since BIDS somewhat imposes the order but it doesn't matter. So better be
    # flexible -- split first on __ and then on _ within the first field and analyze
    # bids_regex = re.compile(
    #     r"""
    #     (?P<modality>[^-_]+)(-(?P<modality_label>[^-_]+))?   # modality
    #     (_ses(?P<session>([+=]|-[^-_]+)))?                 # session
    #     (_run(?P<run>([+=]|-[^-_]+)))?                     # run
    #     (_task-(?P<task>[^-_]+))?                          # task
    #     (?P<bids>(_[^_]+)+)?                               # more of _ separated items for generic BIDS
    #     (__.*?)?       # some custom suffix which will not be included anywhere
    #     """,
    #     flags=re.X
    # )

    # Remove possible suffix we don't care about after __
    protocol_name = protocol_name.split('__', 1)[0]

    bids = None  # we don't know yet for sure
    # We need to figure out if it is a valid bids
    split = protocol_name.split('_')
    prefix = split[0]
    if prefix != 'bids' and '-' in prefix:
        prefix, _ = prefix.split('-', 1)
    if prefix == 'bids':
        bids = True  # for sure
        split = split[1:]

    def split2(s):
        # split on - if present, if not -- 2nd one returned None
        if '-' in s:
            return s.split('-', 1)
        return s, None

    # Let's analyze first element which should tell us sequence type
    modality, modality_label = split2(split[0])
    if modality not in {'anat', 'func', 'dwi', 'behav', 'fmap'}:
        # It is not something we don't consume
        if bids:
            lgr.warning("It was instructed to be BIDS sequence but unknown "
                        "type %s found", modality)
        return {}

    regd = dict(modality=modality)
    if modality_label:
        regd['modality_label'] = modality_label
    # now go through each to see if one which we care
    bids_leftovers = []
    for s in split[1:]:
        key, value = split2(s)
        if value is None and key[-1] in "+=":
            value = key[-1]
            key = key[:-1]
        if key in ['ses', 'run', 'task', 'acq']:
            # those we care about explicitly
            regd[{'ses': 'session'}.get(key, key)] = value
        else:
            bids_leftovers.append(s)

    if bids_leftovers:
        regd['bids'] = '_'.join(bids_leftovers)

    # TODO: might want to check for all known "standard" BIDS suffixes here
    # among bids_leftovers, thus serve some kind of BIDS validator

    # if not regd.get('modality_label', None):
    #     # might need to assign a default label for each modality if was not
    #     # given
    #     regd['modality_label'] = {
    #         'func': 'bold'
    #     }.get(regd['modality'], None)

    return regd


def test_parse_dbic_protocol_name():
    pdpn = parse_dbic_protocol_name

    assert pdpn("nondbic_func-bold") == {}
    assert pdpn("cancelme_func-bold") == {}

    assert pdpn("bids_func-bold") == \
           pdpn("func-bold") == \
           {'modality': 'func', 'modality_label': 'bold'}

    # pdpn("bids_func_ses+_task-boo_run+") == \
    # order should not matter
    assert pdpn("bids_func_ses+_run+_task-boo") == \
           {
               'modality': 'func',
               # 'modality_label': 'bold',
               'session': '+',
               'run': '+',
               'task': 'boo',
            }
    # TODO: fix for that
    assert pdpn("bids_func-pace_ses-1_task-boo_acq-bu_bids-please_run-2__therest") == \
           pdpn("bids_func-pace_ses-1_run-2_task-boo_acq-bu_bids-please__therest") == \
           pdpn("func-pace_ses-1_task-boo_acq-bu_bids-please_run-2") == \
           {
               'modality': 'func', 'modality_label': 'pace',
               'session': '1',
               'run': '2',
               'task': 'boo',
               'acq': 'bu',
               'bids': 'bids-please'
           }

    assert pdpn("bids_anat-scout_ses+") == \
           {
               'modality': 'anat',
               'modality_label': 'scout',
               'session': '+',
           }