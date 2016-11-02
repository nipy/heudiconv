import os
import re
from collections import defaultdict
import hashlib

import logging
lgr = logging.getLogger('heudiconv')


def create_key(subdir, file_suffix, outtype=('nii.gz', 'dicom'),
               annotation_classes=None, prefix=''):
    if not subdir:
        raise ValueError('subdir must be a valid format string')
    # may be even add "performing physician" if defined??
    template = os.path.join(
        prefix,
        "{bids_subject_session_dir}",
        subdir,
        "{bids_subject_session_prefix}_%s" % file_suffix
    )
    return template, outtype, annotation_classes


def md5sum(string):
    """Computes md5sum of as string"""
    m = hashlib.md5(string.encode())
    return m.hexdigest()


# XXX: hackhackhack
protocols2fix = {
    '9d148e2a05f782273f6343507733309d':
        [('anat_', 'anat-'),
         ('run-life[0-9]', 'run+_task-life'),
         ('scout_run\+', 'scout')],
    '76b36c80231b0afaf509e2d52046e964':
        [('fmap_run\+_2mm', 'fmap_run+_acq-2mm')]
}
keys2replace = ['protocol_name', 'series_description']


def fix_dbic_protocol(seqinfo, keys=keys2replace, subsdict=protocols2fix):
    """Ad-hoc fixup for existing protocols"""

    # get name of the study to check if we know how to fix it up
    study_descr = get_unique(seqinfo, 'study_description')
    study_descr_hash = md5sum(study_descr)

    if study_descr_hash not in subsdict:
        raise ValueError("I don't know how to fix {0}".format(study_descr))
    # need to replace both protocol_name series_description
    substitutions = subsdict[study_descr_hash]
    for i, s in enumerate(seqinfo):
        fixed_kwargs = dict()
        for key in keys:
            value = getattr(s, key)
            # replace all I need to replace
            for substring, replacement in substitutions:
                value = re.sub(substring, replacement, value)
            fixed_kwargs[key] = value
        # namedtuples are immutable
        seqinfo[i] = s._replace(**fixed_kwargs)

    return seqinfo


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
    # XXX: ad hoc hack
    study_description = get_unique(seqinfo, 'study_description')
    if study_description in protocols2fix:
        lgr.info("Fixing up protocol for {0}".format(study_description))
        seqinfo = fix_dbic_protocol(seqinfo)

    lgr.info("Processing %d seqinfo entries", len(seqinfo))
    and_dicom = ('dicom', 'nii.gz')

    info = defaultdict(list)
    skipped, skipped_unknown = [], []
    current_run = 0
    run_label = None   # run-
    image_data_type = None
    for s in seqinfo:
        template = None
        suffix = ''
        seq = []

        # figure out type of image from s.image_info -- just for checking ATM
        # since we primarily rely on encoded in the protocol name information
        prev_image_data_type = image_data_type
        image_data_type = s.image_type[2]
        image_type_seqtype = {
            'P': 'fmap',   # phase
            'FMRI': 'func',
            'MPR': 'anat',
            # 'M': 'func',  "magnitude"  -- can be for scout, anat, bold, fmap
            'DIFFUSION': 'dwi',
            'MIP_SAG': 'anat',  # angiography
            'MIP_COR': 'anat',  # angiography
            'MIP_TRA': 'anat',  # angiography
        }.get(image_data_type, None)

        protocol_name_tuned = s.protocol_name
        # Few common replacements
        if protocol_name_tuned in {'AAHead_Scout'}:
            protocol_name_tuned = 'anat-scout'

        regd = parse_dbic_protocol_name(protocol_name_tuned)

        if image_data_type.startswith('MIP'):
            regd['acq'] = regd.get('acq', '') + image_data_type

        if not regd:
            skipped_unknown.append(s.series_id)
            continue

        seqtype = regd.pop('seqtype')
        seqtype_label = regd.pop('seqtype_label', None)

        if image_type_seqtype and seqtype != image_type_seqtype:
            lgr.warning(
                "Deduced seqtype to be %s from DICOM, but got %s out of %s",
                image_type_seqtype, seqtype, protocol_name_tuned)

        if s.is_derived:
            # Let's for now stash those close to original images
            # TODO: we might want a separate tree for all of this!?
            # so more of a parameter to the create_key
            #seqtype += '/derivative'
            # just keep it lower case and without special characters
            # XXXX what for???
            #seq.append(s.series_description.lower())
            prefix = os.path.join('derivatives', 'scanner')
        else:
            prefix = ''

        # analyze s.protocol_name (series_id is based on it) for full name mapping etc
        if seqtype == 'func' and not seqtype_label:
            if '_pace_' in protocol_name_tuned:
                seqtype_label = 'pace'  # or should it be part of seq-
            else:
                # assume bold by default
                seqtype_label = 'bold'

        if seqtype == 'fmap' and not seqtype_label:
            seqtype_label = {
                'M': 'magnitude',  # might want explicit {file_index}  ?
                'P': 'phasediff'
            }[image_data_type]

        run = regd.get('run')
        if run is not None:
            # so we have an indicator for a run
            if run == '+':
                # some sequences, e.g.  fmap, would generate two (or more?)
                # sequences -- e.g. one for magnitude(s) and other ones for
                # phases.  In those we must not increment run!
                if image_data_type == 'P':
                    if prev_image_data_type != 'M':
                        raise RuntimeError("Was expecting phase image to follow magnitude image, but previous one was %r", prev_image_data_type)
                    # else we do nothing special
                else:  # and otherwise we go to the next run
                    current_run += 1
            elif run == '=':
                if not current_run:
                    current_run = 1
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
        else:
            # if there is no _run -- no run label addded
            run_label = None

        suffix_parts = [
            None if not regd.get('task') else "task-%s" % regd['task'],
            None if not regd.get('acq') else "acq-%s" % regd['acq'],
            regd.get('bids'),
            run_label,
            seqtype_label,
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
        if "_Scout" in s.series_description or \
                (seqtype == 'anat' and seqtype_label == 'scout'):
            skipped.append(s.series_id)
            lgr.debug("Ignoring %s", s.series_id)
        else:
            template = create_key(seqtype, suffix, prefix=prefix)
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
def infotoids(seqinfos, outdir):
    # decide on subjid and session based on patient_id
    lgr.info("Processing sequence infos to deduce study/session")
    study_description = get_unique(seqinfos, 'study_description')
    subject = fixup_subjectid(get_unique(seqinfos, 'patient_id'))
    # TODO:  fix up subject id if missing some 0s
    split = study_description.split('^', 1)
    # split first one even more, since couldbe PI_Student
    split = split[0].split('_', 1) + split[1:]

    # locator = study_description.replace('^', '/')
    locator = '/'.join(split)

    # TODO: actually check if given study is study we would care about
    # and if not -- we should throw some ???? exception

    # So -- use `outdir` and locator etc to see if for a given locator/subject
    # and possible ses+ in the sequence names, so we would provide a sequence
    # So might need to go through  parse_dbic_protocol_name(s.protocol_name)
    # to figure out presence of sessions.
    ses_markers = [
        parse_dbic_protocol_name(s.protocol_name).get('session', None) for s in seqinfos
        if not s.is_derived
    ]
    ses_markers = filter(bool, ses_markers)  # only present ones
    session = None
    if ses_markers:
        # we have a session or possibly more than one even
        # let's figure out which case we have
        nonsign_vals = set(ses_markers).difference('+=')
        # although we might want an explicit '=' to note the same session as
        # mentioned before?
        if len(nonsign_vals) > 1:
            lgr.warning( #raise NotImplementedError(
                "Cannot deal with multiple sessions in the same study yet!"
                " We will process until the end of the first session"
            )
        if nonsign_vals:
            if set(ses_markers).intersection('+='):
                raise NotImplementedError(
                    "Should not mix hardcoded session markers with incremental ones (+=)"
                )
            assert len(ses_markers) == 1
            session = ses_markers[0]
        else:
            # TODO - I think we are doomed to go through the sequence and split
            # ... actually the same as with nonsign_vals, we just would need to figure
            # out initial one if sign ones, and should make use of knowing
            # outdir
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


def sanitize_str(value):
    """Remove illegal characters for BIDS from task/acq/etc.."""
    return value.translate(None, '#!@$%^&.,:;')


def parse_dbic_protocol_name(protocol_name):
    """Parse protocol name
    """

    # Parse the name according to our convention
    # https://docs.google.com/document/d/1R54cgOe481oygYVZxI7NHrifDyFUZAjOBwCTu7M7y48/edit?usp=sharing
    # Remove possible suffix we don't care about after __
    protocol_name = protocol_name.split('__', 1)[0]

    bids = None  # we don't know yet for sure
    # We need to figure out if it is a valid bids
    split = protocol_name.split('_')
    prefix = split[0]

    # Fixups
    if prefix == 'scout':
        prefix = split[0] = 'anat-scout'

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
    seqtype, seqtype_label = split2(split[0])
    if seqtype not in {'anat', 'func', 'dwi', 'behav', 'fmap'}:
        # It is not something we don't consume
        if bids:
            lgr.warning("It was instructed to be BIDS sequence but unknown "
                        "type %s found", seqtype)
        return {}

    regd = dict(seqtype=seqtype)
    if seqtype_label:
        regd['seqtype_label'] = seqtype_label
    # now go through each to see if one which we care
    bids_leftovers = []
    for s in split[1:]:
        key, value = split2(s)
        if value is None and key[-1] in "+=":
            value = key[-1]
            key = key[:-1]

        # sanitize values, which must not have _ and - is undesirable ATM as well
        # TODO: BIDSv2.0 -- allows "-" so replace with it instead
        value = str(value).replace('_', 'X').replace('-', 'X')

        if key in ['ses', 'run', 'task', 'acq']:
            # those we care about explicitly
            regd[{'ses': 'session'}.get(key, key)] = sanitize_str(value)
        else:
            bids_leftovers.append(s)

    if bids_leftovers:
        regd['bids'] = '_'.join(bids_leftovers)

    # TODO: might want to check for all known "standard" BIDS suffixes here
    # among bids_leftovers, thus serve some kind of BIDS validator

    # if not regd.get('seqtype_label', None):
    #     # might need to assign a default label for each seqtype if was not
    #     # given
    #     regd['seqtype_label'] = {
    #         'func': 'bold'
    #     }.get(regd['seqtype'], None)

    return regd


def fixup_subjectid(subjectid):
    """Just in case someone managed to miss a zero or added an extra one"""
    # make it lowercase
    subjectid = subjectid.lower()
    reg = re.match("sid0*(\d+)$", subjectid)
    if not reg:
        # some completely other pattern
        return subjectid
    return "sid%06d" % int(reg.groups()[0])


def test_md5sum():
    assert md5sum('cryptonomicon') == '1cd52edfa41af887e14ae71d1db96ad1'
    assert md5sum('mysecretmessage') == '07989808231a0c6f522f9d8e34695794'


def test_fix_dbic_protocol():
    from collections import namedtuple
    FakeSeqInfo = namedtuple('FakeSeqInfo',
                             ['study_description', 'field1', 'field2'])

    seq1 = FakeSeqInfo('mystudy',
                       '02-anat-scout_run+_MPR_sag',
                       '11-func_run-life2_acq-2mm692')
    seq2 = FakeSeqInfo('mystudy',
                       'nochangeplease',
                       'nochangeeither')


    seqinfos = [seq1, seq2]
    keys = ['field1']
    subsdict = {
        md5sum('mystudy'):
            [('scout_run\+', 'scout'),
             ('run-life[0-9]', 'run+_task-life')],
    }

    seqinfos_ = fix_dbic_protocol(seqinfos, keys=keys, subsdict=subsdict)
    assert(seqinfos[1] == seqinfos_[1])
    # field2 shouldn't have changed since I didn't pass it
    assert(seqinfos_[0] == FakeSeqInfo('mystudy',
                                       '02-anat-scout_MPR_sag',
                                       seq1.field2))

    # change also field2 please
    keys = ['field1', 'field2']
    seqinfos_ = fix_dbic_protocol(seqinfos, keys=keys, subsdict=subsdict)
    assert(seqinfos[1] == seqinfos_[1])
    # now everything should have changed
    assert(seqinfos_[0] == FakeSeqInfo('mystudy',
                                       '02-anat-scout_MPR_sag',
                                       '11-func_run+_task-life_acq-2mm692'))


def test_sanitize_str():
    assert sanitize_str('acq-super@duper.faster') == 'acq-superduperfaster'
    assert sanitize_str('acq-perfect') == 'acq-perfect'
    assert sanitize_str('acq-never:use:colon:!') == 'acq-neverusecolon'


def test_fixupsubjectid():
    assert fixup_subjectid("abra") == "abra"
    assert fixup_subjectid("sub") == "sub"
    assert fixup_subjectid("sid") == "sid"
    assert fixup_subjectid("sid000030") == "sid000030"
    assert fixup_subjectid("sid0000030") == "sid000030"
    assert fixup_subjectid("sid00030") == "sid000030"
    assert fixup_subjectid("sid30") == "sid000030"
    assert fixup_subjectid("SID30") == "sid000030"


def test_parse_dbic_protocol_name():
    pdpn = parse_dbic_protocol_name

    assert pdpn("nondbic_func-bold") == {}
    assert pdpn("cancelme_func-bold") == {}

    assert pdpn("bids_func-bold") == \
           pdpn("func-bold") == \
           {'seqtype': 'func', 'seqtype_label': 'bold'}

    # pdpn("bids_func_ses+_task-boo_run+") == \
    # order should not matter
    assert pdpn("bids_func_ses+_run+_task-boo") == \
           {
               'seqtype': 'func',
               # 'seqtype_label': 'bold',
               'session': '+',
               'run': '+',
               'task': 'boo',
            }
    # TODO: fix for that
    assert pdpn("bids_func-pace_ses-1_task-boo_acq-bu_bids-please_run-2__therest") == \
           pdpn("bids_func-pace_ses-1_run-2_task-boo_acq-bu_bids-please__therest") == \
           pdpn("func-pace_ses-1_task-boo_acq-bu_bids-please_run-2") == \
           {
               'seqtype': 'func', 'seqtype_label': 'pace',
               'session': '1',
               'run': '2',
               'task': 'boo',
               'acq': 'bu',
               'bids': 'bids-please'
           }

    assert pdpn("bids_anat-scout_ses+") == \
           {
               'seqtype': 'anat',
               'seqtype_label': 'scout',
               'session': '+',
           }