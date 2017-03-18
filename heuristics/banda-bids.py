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
    rest = create_key('func/sub-{subject}_task-rest_run-{item:02d}_{runtype}')
    face = create_key('func/sub-{subject}_task-face_run-{item:02d}_{runtype}')
    gamble = create_key('func/sub-{subject}_task-gambling_run-{item:02d}_{runtype}')
    conflict = create_key('func/sub-{subject}_task-conflict_run-{item:02d}_{runtype}')
    dwi = create_key('dwi/sub-{subject}_run-{item:02d}_{runtype}')
    fmap = create_key('fmap/sub-{subject}_dir-{dir}_run-{item:02d}_epi')

    info = {t1:[], t2:[], rest:[], face:[], gamble:[], conflict:[], dwi:[], 
            fmap:[]}

    for idx, s in enumerate(seqinfo):
        x, y, sl, nt = (s[6], s[7], s[8], s[9])
        # T1 and T2 scans
        if (sl == 208) and (nt == 1) and ('T1w' in s[12]):
            info[t1] = [s[2]]
        if (sl == 208) and ('T2w' in s[12]):
            info[t2] = [s[2]]
        # diffusion scans
        if ('dMRI_dir9' in s[12]):
            runtype = None
            if (nt >= 99):
                runtype = 'dwi'
            elif (nt == 1) and ('SBRef' in s[12]):
                runtype = 'sbref'
            if runtype:
                info[dwi].append({'item': s[2], 'runtype': runtype})
        # functional scans
        if ('fMRI' in s[12]):
            tasktype = s[12].split('fMRI')[1].split('_')[1]
            runtype = None
            if (nt in [420, 346, 288, 223]):
                runtype = 'bold'
            elif (nt == 1) and ('SBRef' in s[12]):
                runtype = 'sbref'
            if runtype:
                if 'rest' in tasktype: key = rest
                if 'face' in tasktype: key = face
                if 'conflict' in tasktype: key = conflict
                if 'gambling' in tasktype: key = gambling
                info[key].append({'item': s[2], 'runtype': runtype})
        if (nt == 3) and ('SpinEchoFieldMap' in s[12]):
            dirtype = s[12].split('_')[-1]
            info[fmap].append({'item': s[2], 'dir': dirtype})
    return info
