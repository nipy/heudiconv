import os
import re
from collections import OrderedDict
import hashlib

import logging
lgr = logging.getLogger('heudiconv')

# dictionary from accession-number to runs that need to be marked as bad
# NOTE: even if filename has number that is 0-padded, internally no padding
# is done
fix_accession2run = {
    'A000005': ['^1-'],
    'A000035': ['^8-', '^9-'],
    'A000067': ['^9-'],
    'A000072': ['^5-'],
    'A000081': ['^5-'],
    'A000082': ['^5-'],
    'A000088': ['^9-'],
    'A000090': ['^5-'],
    'A000127': ['^21-'],
    'A000130': ['^15-'],
    'A000137': ['^9-', '^11-'],
    'A000297': ['^12-'],
    'A000376': ['^15-'],
    'A000384': ['^8-', '^11-'],
    'A000467': ['^15-'],
    'A000490': ['^15-'],
    'A000511': ['^15-'],
}

# dictionary containing fixes, keys are md5sum of study_description from
# dicoms, in the form of PI-Experimenter^protocolname
# values are list of tuples in the form (regex_pattern, substitution)
protocols2fix = {
    # QA
    '43b67d9139e8c7274578b7451ab21123':
        [
         #('anat-scout.*', 'anat-scout_ses-{date}'),
         ('anat-scout.*', 'anat-scout'),
         ('BOLD_p2_s4_3\.5mm', 'func_task-rest_acq-p2-s4-3.5mm'),
         ('BOLD_p2_s4',        'func_task-rest_acq-p2-s4'),
         ('BOLD_p2_noprescannormalize', 'func-bold_task-rest_acq-p2noprescannormalize'),
         ('BOLD_p2',                    'func-bold_task-rest_acq-p2'),
         ('BOLD_', 'func_task-rest'),
         ('DTI_30_p2_s4_3\.5mm', 'dwi_acq-DTI-30-p2-s4-3.5mm'),
         ('DTI_30_p2_s4',        'dwi_acq-DTI-30-p2-s4'),
         ('DTI_30_p2',           'dwi_acq-DTI-30-p2'),
         ('_p2_s4_3\.5mm', '_acq-p2-s4-3.5mm'),
         ('_p2_s4',        '_acq-p2-s4'),
         ('_p2', '_acq-p2'),
        ],
    '9d148e2a05f782273f6343507733309d':
        [('anat_', 'anat-'),
         ('run-life[0-9]', 'run+_task-life'),
         ('scout_run\+', 'scout'),
         ('T2w', 'T2w_run+'),
         # substitutions for old protocol names
         ('AAHead_Scout_32ch-head-coil', 'anat-scout'),
         ('MPRAGE', 'anat-T1w_acq-MPRAGE_run+'),
         ('gre_field_mapping_2mm', 'fmap_run+_acq-2mm'),
         ('gre_field_mapping_3mm', 'fmap_run+_acq-3mm'),
         ('epi_bold_sms_p2_s4_2mm_life1_748',
            'func_run+_task-life_acq-2mm748'),
         ('epi_bold_sms_p2_s4_2mm_life2_692',
            'func_run+_task-life_acq-2mm692'),
         ('epi_bold_sms_p2_s4_2mm_life3_754',
            'func_run+_task-life_acq-2mm754'),
         ('epi_bold_sms_p2_s4_2mm_life4_824',
            'func_run+_task-life_acq-2mm824'),
         ('epi_bold_p2_3mm_nofs_life1_374',
            'func_run+_task-life_acq-3mmnofs374'),
         ('epi_bold_p2_3mm_nofs_life2_346',
          'func_run+_task-life_acq-3mmnofs346'),
         ('epi_bold_p2_3mm_nofs_life3_377',
          'func_run+_task-life_acq-3mmnofs377'),
         ('epi_bold_p2_3mm_nofs_life4_412',
          'func_run+_task-life_acq-3mmnofs412'),
         ('t2_space_sag_p4_iso', 'anat-T2w_run+'),
         ('gre_field_mapping_2.4mm', 'fmap_run+_acq-2.4mm'),
         ('rest_p2_sms4_2.4mm_64sl_1000tr_32te_600dyn',
            'func_run+_task-rest_acq-2.4mm64sl1000tr32te600dyn'),
         ('DTI_30', 'dwi_run+_acq-30'),
         ('t1_space_sag_p2_iso', 'anat-T1w_acq-060mm_run+')],
    '76b36c80231b0afaf509e2d52046e964':
        [('fmap_run\+_2mm', 'fmap_run+_acq-2mm')],
    'c6d8fbccc72990bee61d28e73b2618a4':
        [('run=', 'run+')],
    'a751cc977f1e354fcafcb0ea2de123bd':
        [
          ('_unlabeled', '_task-unlabeled'),
          ('_mSense', '_acq-mSense'),
          ('_p1_sms4_2.5mm', '_acq-p1-sms4-2.5mm'),
          ('_p1_sms4_3mm', '_acq-p1-sms4-3mm'),
	],
    'd160113cf5ea8c5d0cbbbe14ef625e76':
        [
          ('_run0', '_run-0'),
	],
}
keys2replace = ['protocol_name', 'series_description']

# list containing StudyInstanceUID to skip -- hopefully doesn't happen too often
dicoms2skip = [
    '1.3.12.2.1107.5.2.43.66112.30000016110117002435700000001',
    '1.3.12.2.1107.5.2.43.66112.30000016102813152550600000004',  # double scout
]

DEFAULT_FIELDS = {
    # Let it just be in each json file extracted
    #'Manufacturer': "Siemens",
    #'ManufacturersModelName': "Prisma",
    "Acknowledgements":
        "We thank Terry Sacket and the rest of the DBIC (Dartmouth Brain Imaging "
        "Center) personnel for assistance in data collection, and "
        "Yaroslav Halchenko and Matteo Visconti for preparing BIDS dataset. "
        "TODO: more",
}


def filter_dicom(dcmdata):
    """Return True if a DICOM dataset should be filtered out, else False"""
    return True if dcmdata.StudyInstanceUID in dicoms2skip else False


def filter_files(fn):
    """Return True if a file should be kept, else False.
    We're using it to filter out files that do not start with a number."""

    # do not check for these accession numbers because they haven't been
    # recopied with the initial number
    donotfilter = ['A000012', 'A000013', 'A000020', 'A000041']

    split = os.path.split(fn)
    split2 = os.path.split(split[0])
    sequence_dir = split2[1]
    split3 = os.path.split(split2[0])
    accession_number = split3[1]
    return True
    if accession_number == 'A000043':
        # crazy one that got copied for some runs but not for others,
        # so we are going to discard those that got copied and let heudiconv
        # figure out the rest
        return False if re.match('^[0-9]+-', sequence_dir) else True
    elif accession_number == 'unknown':
        # this one had some stuff without study description, filter stuff before
        # collecting info, so it doesn't crash completely
        return False if re.match('^[34][07-9]-sn', sequence_dir) else True
    elif accession_number in donotfilter:
        return True
    elif accession_number.startswith('phantom-'):
        # Accessions on phantoms, e.g. in dartmouth-phantoms/bids_test4-20161014
        return True
    elif accession_number.startswith('heudiconvdcm'):
        # we were given some tarball with dicoms which was extracted so we
        # better obey
        return True
    else:
        return True if re.match('^[0-9]+-', sequence_dir) else False


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
    if not string:
        return ""  # not None so None was not compared to strings
    m = hashlib.md5(string.encode())
    return m.hexdigest()


def fix_canceled_runs(seqinfo, accession2run=fix_accession2run):
    """Function that adds cancelme_ to known bad runs which were forgotten"""
    accession_number = get_unique(seqinfo, 'accession_number')
    if accession_number in accession2run:
        lgr.info("Considering some runs possibly marked to be "
                 "canceled for accession %s", accession_number)
        badruns = accession2run[accession_number]
        badruns_pattern = '|'.join(badruns)
        for i, s in enumerate(seqinfo):
            if re.match(badruns_pattern, s.series_id):
                lgr.info('Fixing bad run {0}'.format(s.series_id))
                fixedkwargs = dict()
                for key in keys2replace:
                    fixedkwargs[key] = 'cancelme_' + getattr(s, key)
                seqinfo[i] = s._replace(**fixedkwargs)
    return seqinfo


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


def ls(study_session, seqinfo):
    """Additional ls output for a seqinfo"""
    #assert len(sequences) <= 1  # expecting only a single study here
    #seqinfo = sequences.keys()[0]
    study_descr = get_unique(seqinfo, 'study_description')
    study_descr_hash = md5sum(study_descr)
    return ' study hash: %s' % study_descr_hash

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

    # add cancelme to known bad runs
    seqinfo = fix_canceled_runs(seqinfo)

    if md5sum(study_description) in protocols2fix:
        lgr.info("Fixing up protocol for {0}".format(study_description))
        seqinfo = fix_dbic_protocol(seqinfo)

    lgr.info("Processing %d seqinfo entries", len(seqinfo))
    and_dicom = ('dicom', 'nii.gz')

    info = OrderedDict()
    skipped, skipped_unknown = [], []
    current_run = 0
    run_label = None   # run-
    image_data_type = None
    for s in seqinfo:
        # XXX: skip derived sequences, we don't store them to avoid polluting
        # the directory
        if s.is_derived:
            skipped.append(s.series_id)
            lgr.debug("Ignoring derived data %s", s.series_id)
            continue

        # possibly apply present formatting in the series_description or protocol name
        for f in 'series_description', 'protocol_name':
            s = s._replace(**{f: getattr(s, f).format(**s._asdict())})

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
            regd['acq'] = regd.get('acq', '') + sanitize_str(image_data_type)

        if not regd:
            skipped_unknown.append(s.series_id)
            continue

        seqtype = regd.pop('seqtype')
        seqtype_label = regd.pop('seqtype_label', None)

        if image_type_seqtype and seqtype != image_type_seqtype:
            lgr.warning(
                "Deduced seqtype to be %s from DICOM, but got %s out of %s",
                image_type_seqtype, seqtype, protocol_name_tuned)

        # if s.is_derived:
        #     # Let's for now stash those close to original images
        #     # TODO: we might want a separate tree for all of this!?
        #     # so more of a parameter to the create_key
        #     #seqtype += '/derivative'
        #     # just keep it lower case and without special characters
        #     # XXXX what for???
        #     #seq.append(s.series_description.lower())
        #     prefix = os.path.join('derivatives', 'scanner')
        # else:
        #     prefix = ''
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

        # label for dwi as well
        if seqtype == 'dwi' and not seqtype_label:
            seqtype_label = 'dwi'

        run = regd.get('run')
        if run is not None:
            # so we have an indicator for a run
            if run == '+':
                # some sequences, e.g.  fmap, would generate two (or more?)
                # sequences -- e.g. one for magnitude(s) and other ones for
                # phases.  In those we must not increment run!
                if image_data_type == 'P':
                    if prev_image_data_type != 'M':
                        # XXX if we have a known earlier study, we need to always
                        # increase the run counter for phasediff because magnitudes
                        # were not acquired
                        if md5sum(s.study_description) == '9d148e2a05f782273f6343507733309d':
                            current_run += 1
                        else:
                            raise RuntimeError(
                                "Was expecting phase image to follow magnitude "
                                "image, but previous one was %r", prev_image_data_type)
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

        if s.is_motion_corrected and 'rec-' in regd.get('bids', ''):
            raise NotImplementedError("want to add _acq-moco but there is _acq- already")

        suffix_parts = [
            None if not regd.get('task') else "task-%s" % regd['task'],
            None if not regd.get('acq') else "acq-%s" % regd['acq'],
            # But we want to add an indicator in case it was motion corrected
            # in the magnet. ref sample  /2017/01/03/qa
            None if not s.is_motion_corrected else 'rec-moco',
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
                (seqtype == 'anat' and seqtype_label and seqtype_label.startswith('scout')):
            skipped.append(s.series_id)
            lgr.debug("Ignoring %s", s.series_id)
        else:
            template = create_key(seqtype, suffix, prefix=prefix)
            # we wanted ordered dict for consistent demarcation of dups
            if template not in info:
                info[template] = []
            info[template].append(s.series_id)

    if skipped:
        lgr.info("Skipped %d sequences: %s" % (len(skipped), skipped))
    if skipped_unknown:
        lgr.warning("Could not figure out where to stick %d sequences: %s" %
                    (len(skipped_unknown), skipped_unknown))

    info = get_dups_marked(info)  # mark duplicate ones with __dup-0x suffix

    info = dict(info)  # convert to dict since outside functionality depends on it being a basic dict
    return info


def get_dups_marked(info):
    # analyze for "cancelled" runs, if run number was explicitly specified and
    # thus we ended up with multiple entries which would mean that older ones
    #  were "cancelled"
    info = info.copy()
    dup_id = 0
    for template in info:
        series_ids = info[template]
        if len(series_ids) > 1:
            lgr.warning("Detected %d duplicated run(s) for template %s: %s",
                        len(series_ids) - 1, template[0], series_ids[:-1])
            # copy the duplicate ones into separate ones
            for dup_series_id in series_ids[:-1]:
                dup_id += 1
                dup_template = (
                    '%s__dup-%02d' % (template[0], dup_id),
                    ) + template[1:]
                # There must have not been such a beast before!
                assert dup_template not in info
                info[dup_template] = [dup_series_id]
            info[template] = series_ids[-1:]
        assert len(info[template]) == 1
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
    study_description_hash = md5sum(study_description)
    subject = fixup_subjectid(get_unique(seqinfos, 'patient_id'))
    # TODO:  fix up subject id if missing some 0s
    if study_description:
        split = study_description.split('^', 1)
        # split first one even more, since couldbe PI_Student or PI-Student
        split = re.split('-|_', split[0], 1) + split[1:]

        # locator = study_description.replace('^', '/')
        locator = '/'.join(split)
    else:
        locator = 'unknown'

    # TODO: actually check if given study is study we would care about
    # and if not -- we should throw some ???? exception

    # So -- use `outdir` and locator etc to see if for a given locator/subject
    # and possible ses+ in the sequence names, so we would provide a sequence
    # So might need to go through  parse_dbic_protocol_name(s.protocol_name)
    # to figure out presence of sessions.
    ses_markers = []
    for s in seqinfos:
        if s.is_derived:
            continue
        session_ = parse_dbic_protocol_name(s.protocol_name).get('session', None)
        if session_ and '{' in session_:
            # there was a marker for something we could provide from our seqinfo
            # e.g. {date}
            session_ = session_.format(**s._asdict())
        ses_markers.append(session_)

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
            # get only unique values
            ses_markers = list(set(ses_markers))
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

    if study_description_hash == '9d148e2a05f782273f6343507733309d':
        session = 'siemens1'
        lgr.info('Imposing session {0}'.format(session))

    return {
        # TODO: request info on study from the JedCap
        'locator': locator,
        # Sessions to be deduced yet from the names etc TODO
        'session': session,
        'subject': subject,
    }


def sanitize_str(value):
    """Remove illegal characters for BIDS from task/acq/etc.."""
    return value.translate(None, '#!@$%^&.,:;_-')


def parse_dbic_protocol_name(protocol_name):
    """Parse protocol name according to our convention with minimal set of fixups
    """

    # Since Yarik didn't know better place to put it in, but could migrate outside
    # at some point
    protocol_name = protocol_name.replace("anat_T1w", "anat-T1w")
    protocol_name = protocol_name.replace("hardi_64", "dwi_acq-hardi64")

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
        # just filter out possible _- in it
        return re.sub('[-_]', '', subjectid)
    return "sid%06d" % int(reg.groups()[0])


def test_filter_files():
    assert(filter_files('/home/mvdoc/dbic/09-run_func_meh/0123432432.dcm'))
    assert(not filter_files('/home/mvdoc/dbic/run_func_meh/012343143.dcm'))


def test_md5sum():
    assert md5sum('cryptonomicon') == '1cd52edfa41af887e14ae71d1db96ad1'
    assert md5sum('mysecretmessage') == '07989808231a0c6f522f9d8e34695794'


def test_fix_canceled_runs():
    from collections import namedtuple
    FakeSeqInfo = namedtuple('FakeSeqInfo',
                             ['accession_number', 'series_id',
                              'protocol_name', 'series_description'])

    seqinfo = []
    runname = 'func_run+'
    for i in range(1, 6):
        seqinfo.append(
            FakeSeqInfo('accession1',
                        '{0:02d}-'.format(i) + runname,
                        runname, runname)
        )

    fake_accession2run = {
        'accession1': ['^01-', '^03-']
    }

    seqinfo_ = fix_canceled_runs(seqinfo, fake_accession2run)

    for i, s in enumerate(seqinfo_, 1):
        output = runname
        if i == 1 or i == 3:
            output = 'cancelme_' + output
        for key in ['series_description', 'protocol_name']:
            value = getattr(s, key)
            assert(value == output)
        # check we didn't touch series_id
        assert(s.series_id == '{0:02d}-'.format(i) + runname)


def test_fix_dbic_protocol():
    from collections import namedtuple
    FakeSeqInfo = namedtuple('FakeSeqInfo',
                             ['accession_number', 'study_description',
                              'field1', 'field2'])
    accession_number = 'A003'
    seq1 = FakeSeqInfo(accession_number,
                       'mystudy',
                       '02-anat-scout_run+_MPR_sag',
                       '11-func_run-life2_acq-2mm692')
    seq2 = FakeSeqInfo(accession_number,
                       'mystudy',
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
    assert(seqinfos_[0] == FakeSeqInfo(accession_number,
                                       'mystudy',
                                       '02-anat-scout_MPR_sag',
                                       seq1.field2))

    # change also field2 please
    keys = ['field1', 'field2']
    seqinfos_ = fix_dbic_protocol(seqinfos, keys=keys, subsdict=subsdict)
    assert(seqinfos[1] == seqinfos_[1])
    # now everything should have changed
    assert(seqinfos_[0] == FakeSeqInfo(accession_number,
                                       'mystudy',
                                       '02-anat-scout_MPR_sag',
                                       '11-func_run+_task-life_acq-2mm692'))


def test_sanitize_str():
    assert sanitize_str('super@duper.faster') == 'superduperfaster'
    assert sanitize_str('perfect') == 'perfect'
    assert sanitize_str('never:use:colon:!') == 'neverusecolon'


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

    assert pdpn("anat_T1w_acq-MPRAGE_run+") == \
           {
                'seqtype': 'anat',
                'run': '+',
                'acq': 'MPRAGE',
                'seqtype_label': 'T1w'
           }
