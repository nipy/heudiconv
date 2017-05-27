import os


def create_key(template, outtype=('nii.gz',), annotation_classes=None):
    if template is None or not template:
        raise ValueError('Template must be a valid format string')
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
    and_dicom = ('dicom', 'nii.gz')

    t1 = create_key('{session}/anat/sub-{subject}_T1w', outtype=and_dicom)
    t2 = create_key('{session}/anat/sub-{subject}_T2w', outtype=and_dicom)
    fm_diff = create_key('{session}/fmap/sub-{subject}_fieldmap-dwi')
    dwi_ap = create_key('{session}/dwi/sub-{subject}_dir-AP_dwi', outtype=and_dicom)
    dwi_pa = create_key('{session}/dwi/sub-{subject}_dir-PA_dwi', outtype=and_dicom)
    fm_rest= create_key('{session}/fmap/sub-{subject}_fieldmap-rest')
    rs = create_key('{session}/func/sub-{subject}_task-rest_run-{item:02d}_bold', outtype=and_dicom)
    boldt1 = create_key('{session}/func/sub-{subject}_task-bird1back_run-{item:02d}_bold', outtype=and_dicom)
    boldt2 = create_key('{session}/func/sub-{subject}_task-letter1back_run-{item:02d}_bold', outtype=and_dicom)
    boldt3 = create_key('{session}/func/sub-{subject}_task-letter2back_run-{item:02d}_bold', outtype=and_dicom)
    nofb_task=create_key('{session}/func/sub-{subject}_task-nofb_run-{item:02d}_bold', outtype=and_dicom)
    fb_task=create_key('{session}/func/sub-{subject}_task-fb_run-{item:02d}_bold', outtype=and_dicom)
    info = {t1: [], t2:[], fm_diff:[], dwi_ap:[], dwi_pa:[], fm_rest:[], rs:[],
            boldt1:[], boldt2:[], boldt3:[], nofb_task:[], fb_task:[]}
    last_run = len(seqinfo)
    for s in seqinfo:
        if (s.dim3 == 176 or s.dim3 == 352) and (s.dim4 == 1) and ('MEMPRAGE' in s.protocol_name):
            info[t1] = [s.series_id]
        elif (s.dim4 == 1) and ('MEMPRAGE' in s.protocol_name):
            info[t1] = [s.series_id]
        elif (s.dim3 == 176 or s.dim3 == 352) and (s.dim4 == 1) and ('T2_SPACE' in s.protocol_name):
            info[t2] = [s.series_id]
        elif ('field_mapping_diffusion' in s.protocol_name):
            info[fm_diff].append([s.series_id])
        elif (s.dim4 >= 70) and ('DIFFUSION_HighRes_AP' in s.protocol_name):
            info[dwi_ap].append([s.series_id])
        elif ('DIFFUSION_HighRes_PA' in s.protocol_name):
            info[dwi_pa].append([s.series_id])
        elif ('field_mapping_resting' in s.protocol_name):
            info[fm_rest].append([s.series_id])
        elif (s.dim4 == 144) and ('resting' in s.protocol_name):
            if not s.is_motion_corrected:
                info[rs].append([(s.series_id)])
        elif (s.dim4 == 183 or s.dim4 == 366) and ('localizer' in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt1].append([s.series_id])
        elif (s.dim4 == 227 or s.dim4 == 454) and ('transfer1' in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt2].append([s.series_id])
        elif (s.dim4 == 227 or s.dim4 == 454) and ('transfer2' in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt3].append([s.series_id])
        elif (('run1' in s.protocol_name) or ('run6' in s.protocol_name)) and (s.dim4 == 159):
            if not s.is_motion_corrected:
               info[nofb_task].append([s.series_id])
        elif (('run2' in s.protocol_name) or ('run3' in s.protocol_name) or ('run4' in s.protocol_name)
                or ('run5' in s.protocol_name)) and (s.dim4 == 159):
            if not s.is_motion_corrected:
                info[fb_task].append([s.series_id])
        else:
            pass
    return info
