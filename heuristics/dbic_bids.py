import os

from collections import defaultdict

import logging
lgr = logging.getLogger('heudiconv')


def create_key(subdir, file_suffix, outtype=('nii.gz',),
               annotation_classes=None):
    if not subdir:
        raise ValueError('subdir must be a valid format string')
    # may be even add "performing physician" if defined??
    template = "{referring_physician_name}/{study_description}/{bids_subject_session_dir}/" \
               "%s/{bids_subject_session_prefix}_%s" % (subdir, file_suffix)
    return template, outtype, annotation_classes


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

    # decide on global prefix (TODO -- manage to do it outside of here)

    # no checks for consistency for now -- assume that those fields we rely on
    # ARE the same
    # Actually all below is taken care of outside now!
    # s = seqinfo[0]
    #
    # session_id, subject_id = get_session_subject_id(s)
    #
    # session_suffix = session_prefix = ''
    # if session_id:
    #     session_suffix = "_ses-%s" % session_id
    #     session_prefix = "ses-%s/" % session_id
    # if not subject_id:
    #     raise ValueError("Could not figure out the subject id")
    #
    # lgr.debug("Figured out subject %s. Session prefix: %s", subject_id, session_prefix)
    # del subject_id   # not to be used

    t1 = create_key('anat', 'T1w', outtype=and_dicom)
    t2 = create_key('anat', 'T2w', outtype=and_dicom)
    fm_diff = create_key('fmap', 'fieldmap-dwi')
    dwi_ap = create_key('dwi', 'dir-AP_dwi', outtype=and_dicom)
    dwi_pa = create_key('dwi', 'dir-PA_dwi', outtype=and_dicom)
    fm_rest = create_key('fmap', 'fieldmap-rest')
    rs = create_key('func', 'task-rest_run-{item:02d}_bold', outtype=and_dicom)
    boldt1 = create_key('func', 'task-bird1back_run-{item:02d}_bold', outtype=and_dicom)
    boldt2 = create_key('func', 'task-letter1back_run-{item:02d}_bold', outtype=and_dicom)
    boldt3 = create_key('func', 'task-letter2back_run-{item:02d}_bold', outtype=and_dicom)
    nofb_task = create_key('func', 'task-nofb_run-{item:02d}_bold', outtype=and_dicom)
    fb_task = create_key('func', 'task-fb_run-{item:02d}_bold', outtype=and_dicom)
    #info = {t1: [], t2: [], fm_diff:[], dwi_ap:[], dwi_pa:[], fm_rest:[], rs:[],
    #        boldt1:[], boldt2:[], boldt3:[], nofb_task:[], fb_task:[]}
    info = defaultdict(list)
    last_run = len(seqinfo)
    skipped, skipped_unknown = [], []

    for s in seqinfo:
        template = None
        suffix = ''
        seq = []

        # figure out type of image from s.image_info
        image_dir = {
            'P': 'fmap',
            'FMRI': 'func',
            'MPR': 'anat',
            'M': 'anat',
            'DIFFUSION': 'dwi',
        }.get(s.image_type[2], None)

        if image_dir is None:
            # must be exhaustive!
            raise ValueError(
                "Cannot figure out type of image with image_info %s"
                % str(s.image_type)
            )

        if s.is_derived:
            # Let's for now stash those close to original images
            image_dir += '/derivative'
            # just keep it lower case and without special characters
            seq.append(s.series_description.lower())

        # analyze s.protocol_name (series_number is based on it) for full name mapping etc
        if image_dir == 'func':
            if '_pace_' in s.protocol_name:
                suffix += '_pace'  # or should it be part of seq-
            else:
                # assume bold by default
                suffix += '_bold'

            # TODO run.  might be needed for fieldmap

        # .series_description in case of
        sdesc = s.study_description
        # temporary aliases for those phantoms which we already collected
        # so we rename them into this
        #MAPPING

        # the idea ias to have sequence names in the format like
        # bids_<subdir>_bidsrecord
        # in bids record we could have  _run[+=]
        #  which would say to either increment run number from already encountered
        #  or reuse the last one
        if seq:
            suffix += 'seq-%s' % ('+'.join(seq))

        if template:
            info[template].append(s.series_number)
        else:
            # some are ok to skip and not to whine
            if "_Scout_" in s.series_description:
                skipped.append(s.series_number)
                lgr.debug("Ignoring %s", s.series_number)
            else:
                skipped_unknown.append(s.series_number)

    info = dict(info)  # convert to dict since outside functionality depends on it being a basic dict
    if skipped:
        lgr.info("Skipped %d sequences: %s" % (len(skipped), skipped))
    if skipped_unknown:
        lgr.warning("Could not figure out where to stick %d sequences: %s" %
                    (len(skipped_unknown), skipped_unknown))
    return info


def get_session_subject_id(s):
    # decide on subjid and session based on patient_id
    pid_split = s.patient_id.split('_')
    if len(pid_split) == 1:
        # there were no explicit session
        # then it is not a multi-session study
        sid = s.patient_id
        session_id = None
    elif len(pid_split) == 2:
        sid, session_id = pid_split
    elif len(pid_split) == 3:
        _nonanon_sid, session_id, sid = pid_split
    else:
        raise ValueError(
            "No logic for more than 3 _-separated entries in patient_id. Got:"
            " %s" % s.patient_id)
    return session_id, sid
