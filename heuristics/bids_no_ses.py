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
    """

    rs = create_key('func/sub-{subject}_task-rest_bold', outtype=('dicom', 'nii.gz'))
    spin_AP = create_key('fmap/sub-{subject}_dir-AP_epi', outtype=('dicom', 'nii.gz'))
    spin_PA = create_key('fmap/sub-{subject}_dir-PA_epi', outtype=('dicom', 'nii.gz'))
    dwi_PA = create_key('fmap/sub-{subject}_dir-PA_epi-{item:02d}', outtype=('dicom', 'nii.gz'))
    dwi_AP = create_key('fmap/sub-{subject}_dir-AP_epi-{item:02d}', outtype=('dicom', 'nii.gz'))
    t1 = create_key('anat/sub-{subject}_T1w', outtype=('dicom', 'nii.gz'))   
    t2 = create_key('anat/sub-{subject}_T2w', outtype=('dicom', 'nii.gz'))
    morphing = create_key('func/sub-{subject}_task-morph_run-{item:02d}_bold', outtype=('dicom', 'nii.gz'))
    sholo=create_key('func/sub-{subject}_task-sholo_run-{item:02d}_bold', outtype=('dicom', 'nii.gz'))

    info={rs:[], spin_AP:[], spin_PA:[], dwi_PA:[], dwi_AP:[], t1:[], t2:[], morphing:[], sholo:[]}

    for s in seqinfo:
        x, y, sl, nt = (s[6], s[7], s[8], s[9])
        if (nt == 300) and ('SMS5_rsfMRI' in s[12]):
            info[rs] = [s[2]]
        elif (sl > 1) and ('Spin_Echo_EPI_AP' in s[12]):
            info[spin_AP].append(s[2])
        elif (sl > 1)  and ('Spin_Echo_EPI_PA' in s[12]):
            info[spin_PA].append(s[2])
        elif (sl > 1) and (nt == 72) and ('SMS2-diff_b1000' in s[12]):
            info[dwi_PA].append(s[2])
        elif (sl > 1) and (nt == 7 ) and ('SMS2-diff_b1000_free' in s[12]):
            info[dwi_AP].append(s[2]) 
        elif (sl == 176) and (nt ==1) and ('T1_MPRAGE' in s[12]):
            info[t1].append(s[2])
        elif (sl == 176) and (nt == 1 ) and ('T2_SPACE' in s[12]):
            info[t2] = [s[2]]
        elif (nt == 153) and ('morphing' in s[12]) and not s[13]:
            info[morphing].append([s[2]])
        elif (nt == 76) and ('ShoLo' in s[12]):
            info[sholo].append([s[2]])
        else:
            pass
    return info
