import os

from collections import defaultdict

import logging
lgr = logging.getLogger('heudiconv')


def create_key(subdir, file_suffix, outtype=('nii.gz',),
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

        regd = parse_dbic_protocol_name(s.protocol_name)

        if not regd:
            skipped_unknown.append(s.series_id)
            continue

        modality = regd.pop('modality')
        modality_label = regd.pop('modality_label', None)

        if image_type_modality and modality != image_type_modality:
            import pdb; pdb.set_trace()
            lgr.warning("Deduced modality to be %s from DICOM, but got %s out of %s",
                        image_type_modality, modality, s.protocol_name)

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
            if '_pace_' in s.protocol_name:
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
            run_label,
            None if not regd.get('task') else "task-%s" % regd['task'],
            regd.get('bids'),
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

    bids_regex = re.compile(
        r"""
        bids_           # our prefix to signal BIDS layout
        (?P<modality>[^-_]+)(-(?P<modality_label>[^-_]+))?   # modality
        (_ses(?P<session>([+=]|-[^-_]+)))?                 # session
        (_run(?P<run>([+=]|-[^-_]+)))?                     # run
        (_task-(?P<task>[^-_]+))?                          # task
        (?P<bids>(_[^_]+)+)?                               # more of _ separated items for generic BIDS
        (__.*?)?       # some custom suffix which will not be included anywhere
        """,
        flags=re.X
    )

    reg = bids_regex.match(protocol_name)

    if not reg:
        lgr.debug("Did not match protocol %s as DBIC BIDS protocol",
                  protocol_name)
        return {}
    regd = reg.groupdict()

    # pop those which were not found (i.e None)
    for k in list(regd.keys()):
        if regd[k] is None:
            regd.pop(k)

    for f in 'run', 'session':
        # strip leading - in values
        if f in regd:
            regd[f] = regd[f].lstrip('-')

    # strip leading _ for consistency
    if regd.get('bids', None) is not None:
        regd['bids'] = regd['bids'].lstrip('_')

    # TODO: might want to check for all known "standard" BIDS suffixes here

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

    assert pdpn("bids_func-bold") == \
           {'modality': 'func', 'modality_label': 'bold'}

    assert pdpn("bids_func_ses+_run+_task-boo") == \
           {
               'modality': 'func', 'modality_label': 'bold',
               'session': '+',
               'run': '+',
               'task': 'boo',
            }
    assert pdpn("bids_func-pace_ses-1_run-2_task-boo_bids-please__therest") == \
           {
               'modality': 'func', 'modality_label': 'pace',
               'session': '1',
               'run': '2',
               'task': 'boo',
               'bids': 'bids-please'
           }

    assert pdpn("bids_anat-scout_ses+") == \
           {
               'modality': 'anat',
               'modality_label': 'scout',
               'session': '+',
           }