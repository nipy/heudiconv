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
    rest_ap = create_key('func/sub-{subject}_dir-AP_task-rest_run-{item:02d}_bold')
    rest_pa = create_key('func/sub-{subject}_dir-PA_task-rest_run-{item:02d}_bold')
    face_ap = create_key('func/sub-{subject}_task-face_run-{item:02d}_acq-AP_bold')
    face_pa = create_key('func/sub-{subject}_task-face_run-{item:02d}_acq-PA_bold')
    gamble_ap = create_key('func/sub-{subject}_task-gambling_run-{item:02d}_acq-AP_bold')
    gamble_pa = create_key('func/sub-{subject}_task-gambling_run-{item:02d}_acq-PA_bold')
    conflict = create_key('func/sub-{subject}_task-conflict_run-{item:02d}_acq-{acq}_bold')
    dwi_ap = create_key('dwi/sub-{subject}_dir-AP_dwi')
    dwi_pa = create_key('dwi/sub-{subject}_dir-PA_dwi')

    info = {t1:[],t2:[],rest_ap:[],rest_pa:[],face_ap:[],face_pa:[],gamble_ap:[],gamble_pa:[],
            conflict:[], dwi_ap:[],dwi_pa:[]}

    for s in seqinfo:
        x,y,sl,nt = (s[6],s[7],s[8],s[9])
        if (sl == 208) and (nt == 1) and ('T1w' in s[12]):
            info[t1].append([s[2]])
        if (sl == 208) and ('T2w' in s[12]):
            info[t2].append([s[2]])
        if (nt == 1) and ('dMRI_dir99_AP' in s[12]):
            info[dwi_ap].append([s[2]])
        if (nt == 1) and ('dMRI_dir99_PA' in s[12]):
            info[dwi_pa].append([s[2]])
        if (nt == 420) and ('rfMRI_REST_AP' in s[12]):
            info[rest_ap].append([s[2]])
        if (nt == 420) and ('rfMRI_REST_PA' in s[12]):
            info[rest_pa].append([s[2]])
        if (nt == 346) and ('tfMRI_faceMatching_AP' in s[12]):
            info[face_ap].append([s[2]])
        if (nt == 346) and ('tfMRI_faceMatching_PA' in s[12]):
            info[face_pa].append([s[2]])
        if (nt == 288) and ('tfMRI_conflict_AP' in s[12]):
            # Add your own variables to the template using a dictionary
            info[conflict].append({'item': s[2], 'acq': 'AP'})
        if (nt == 288) and ('tfMRI_conflict_PA' in s[12]):
            info[conflict].append({'item': s[2], 'acq': 'PA'})
        if (nt == 223) and ('tfMRI_gambling_AP' in s[12]):
            info[gamble_ap].append([s[2]])
        if (nt == 223) and ('tfMRI_gambling_PA' in s[12]):
            info[gamble_pa].append([s[2]])
    return info
