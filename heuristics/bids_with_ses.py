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
    print seqinfo
    and_dicom = ('dicom', 'nii.gz')

    t1 = create_key('{session}/anat/sub-{subject}_T1w', outtype=and_dicom)
    t2 = create_key('{session}/anat/sub-{subject}_T2w', outtype=and_dicom)
    fm_diff = create_key('{session}/fmap/sub-{subject}_fieldmap-dwi')
    dwi_ap = create_key('{session}/dwi/sub-{subject}_dir-AP_dwi', outtype=and_dicom)
    dwi_pa = create_key('{session}/fmap/sub-{subject}_dir-PA_dwi', outtype=and_dicom)
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
        x,y,sl,nt = (s[6], s[7], s[8], s[9])
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
        else:
            pass
    return info
