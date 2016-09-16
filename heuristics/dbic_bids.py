import os

from collections import defaultdict

import logging
lgr = logging.getLogger('heudiconv')


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

    def create_key(subdir, file_suffix, outtype=('nii.gz',), annotation_classes=None):
        if not subdir:
            raise ValueError('subdir must be a valid format string')
        template = "%s/{bids_subject_session}_%s" % (subdir, file_suffix)
        return template, outtype, annotation_classes

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
        sdesc = s.study_description
        # temporary aliases for those phantoms which we already collected
        # so we rename them into this
        #MAPPING

        # the idea ias to have sequence names in the format like
        # bids_<subdir>_bidsrecord
        # in bids record we could have  _run[+=]
        #  which would say to either increment run number from already encountered
        #  or reuse the last one

        x, y, sl, nt = (s[6], s[7], s[8], s[9])
        if (sl == 176 or sl == 352) and (nt == 1) and ('MEMPRAGE' in s[12]):
            info[t1] = [s[2]]
        elif (nt == 1) and ('MEMPRAGE' in s[12]):
            info[t1] = [s[2]]
        elif (sl == 176 or sl == 352) and (nt == 1) and ('T2_SPACE' in s[12]):
            info[t2] = [s[2]]
        elif ('field_mapping_diffusion' in s[12]):
            info[fm_diff].append([s[2]])
        elif (nt >= 70) and ('DIFFUSION_HighRes_AP' in s[12]):
            info[dwi_ap].append([s[2]])
        elif ('DIFFUSION_HighRes_PA' in s[12]):
            info[dwi_pa].append([s[2]])
        elif ('field_mapping_resting' in s[12]):
            info[fm_rest].append([s[2]])
        elif (nt == 144) and ('resting' in s[12]):
            if not s[13]:
                info[rs].append([(s[2])])
        elif (nt == 183 or nt == 366) and ('localizer' in s[12]):
            if not s[13]:
                info[boldt1].append([s[2]])
        elif (nt == 227 or nt == 454) and ('transfer1' in s[12]):
            if not s[13]:
                info[boldt2].append([s[2]])
        elif (nt == 227 or nt == 454) and ('transfer2' in s[12]):
            if not s[13]:
                info[boldt3].append([s[2]])
        elif (('run1' in s[12]) or ('run6' in s[12])) and (nt == 159):
            if not s[13]:
               info[nofb_task].append([s[2]])
        elif (('run2' in s[12]) or ('run3' in s[12]) or ('run4' in s[12])
                or ('run5' in s[12])) and (nt == 159):
            if not s[13]:
                info[fb_task].append([s[2]])
        elif "_Scout_" in s.series_description:
            skipped.append(s.series_number)
            lgr.debug("Ignoring %s", sdesc)
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
