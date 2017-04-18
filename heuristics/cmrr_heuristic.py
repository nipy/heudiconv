import os

def create_key(template, outtype=('nii.gz','dicom'), annotation_classes=None):
    if template is None or not template:
        raise ValueError('Template must be a valid format string')
    return (template, outtype, annotation_classes)


def infotodict(seqinfo):
    """Heuristic evaluator for determining which runs belong where
    
    allowed template fields - follow python string module: 
    
    item: index within category 
    subject: participant id 
    seqitem: run number during scanning
    subindex: sub index within group
    """
    t1 = create_key('anat/sub-{subject}_T1w')
    t2 = create_key('anat/sub-{subject}_T2w')
    rest = create_key('func/sub-{subject}_dir-{acq}_task-rest_run-{item:02d}_bold')
    face = create_key('func/sub-{subject}_task-face_run-{item:02d}_acq-{acq}_bold')
    gamble = create_key('func/sub-{subject}_task-gambling_run-{item:02d}_acq-{acq}_bold')
    conflict = create_key('func/sub-{subject}_task-conflict_run-{item:02d}_acq-{acq}_bold')
    dwi = create_key('dwi/sub-{subject}_dir-{acq}_run-{item:02d}_dwi')

    fmap_rest = create_key('fmap/sub-{subject}_acq-func{acq}_dir-{dir}_run-{item:02d}_epi')
    fmap_dwi = create_key('fmap/sub-{subject}_acq-dwi{acq}_dir-{dir}_run-{item:02d}_epi')

    info = {t1:[], t2:[], rest:[], face:[], gamble:[], conflict:[], dwi:[], fmap_rest:[], fmap_dwi:[]}

    for idx, s in enumerate(seqinfo):
        x,y,sl,nt = (s[6],s[7],s[8],s[9])
        if (sl == 208) and (nt == 1) and ('T1w' in s[12]):
            info[t1] = [s[2]]
        if (sl == 208) and ('T2w' in s[12]):
            info[t2] = [s[2]]
        if (nt >= 99) and (('dMRI_dir98_AP' in s[12]) or ('dMRI_dir99_AP' in s[12])):
            acq = s[12].split('dMRI_')[1].split('_')[0] + 'AP'
            info[dwi].append({'item': s[2], 'acq': acq})
        if (nt >= 99) and (('dMRI_dir98_PA' in s[12]) or ('dMRI_dir99_PA' in s[12])):
            acq = s[12].split('dMRI_')[1].split('_')[0] + 'PA'
            info[dwi].append({'item': s[2], 'acq': acq})
        if (nt == 1) and (('dMRI_dir98_AP' in s[12]) or ('dMRI_dir99_AP' in s[12])):
            acq = s[12].split('dMRI_')[1].split('_')[0]
            info[fmap_dwi].append({'item': s[2], 'dir': 'AP', 'acq': acq})
        if (nt == 1) and (('dMRI_dir98_PA' in s[12]) or ('dMRI_dir99_PA' in s[12])):
            acq = s[12].split('dMRI_')[1].split('_')[0]
            info[fmap_dwi].append({'item': s[2], 'dir': 'PA', 'acq': acq})
        if (nt == 420) and ('rfMRI_REST_AP' in s[12]):
            info[rest].append({'item': s[2], 'acq': 'AP'})
        if (nt == 420) and ('rfMRI_REST_PA' in s[12]):
            info[rest].append({'item': s[2], 'acq': 'PA'})
        if (nt == 1) and ('rfMRI_REST_AP' in s[12]):
            if seqinfo[idx + 1][9] != 420:
                continue
            info[fmap_rest].append({'item': s[2], 'dir': 'AP', 'acq': ''})
        if (nt == 1) and ('rfMRI_REST_PA' in s[12]):
            info[fmap_rest].append({'item': s[2], 'dir': 'PA', 'acq': ''})
        if (nt == 346) and ('tfMRI_faceMatching_AP' in s[12]):
            info[face].append({'item': s[2], 'acq': 'AP'})
        if (nt == 346) and ('tfMRI_faceMatching_PA' in s[12]):
            info[face].append({'item': s[2], 'acq': 'PA'})
        if (nt == 288) and ('tfMRI_conflict_AP' in s[12]):
            info[conflict].append({'item': s[2], 'acq': 'AP'})
        if (nt == 288) and ('tfMRI_conflict_PA' in s[12]):
            info[conflict].append({'item': s[2], 'acq': 'PA'})
        if (nt == 223) and ('tfMRI_gambling_AP' in s[12]):
            info[gamble].append({'item': s[2], 'acq': 'AP'})
        if (nt == 223) and ('tfMRI_gambling_PA' in s[12]):
            info[gamble].append({'item': s[2], 'acq': 'PA'})
    return info
