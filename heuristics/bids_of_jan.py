import os

def create_key(template, outtype=('nii.gz',), annotation_classes=None):
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
    
    rs_lr = create_key('func/sub-{subject}_task-rest_acq-LR_run-{item:01d}_bold')
    rs_lr_sbref = create_key('func/sub-{subject}_task-rest_acq-LR_run-{item:01d}_sbref')
    rs_rl = create_key('func/sub-{subject}_task-rest_acq-RL_run-{item:01d}_bold')
    rs_rl_sbref = create_key('func/sub-{subject}_task-rest_acq-RL_run-{item:01d}_sbref')
    dwi_dir90lr = create_key('dwi/sub-{subject}_acq-dir90LR_run-{item:01d}_dwi')
    dwi_dir90lr_sbref = create_key('dwi/sub-{subject}_acq-dir90LR_run-{item:01d}_sbref')
    dwi_dir90rl = create_key('dwi/sub-{subject}_acq-dir90RL_run-{item:01d}_dwi')
    dwi_dir90rl_sbref = create_key('dwi/sub-{subject}_acq-dir90RL_run-{item:01d}_sbref')
    dwi_dir91lr = create_key('dwi/sub-{subject}_acq-dir90LR_run-{item:01d}_dwi')
    dwi_dir91lr_sbref = create_key('dwi/sub-{subject}_acq-dir90LR_run-{item:01d}_sbref')
    dwi_dir91rl = create_key('dwi/sub-{subject}_acq-dir90RL_run-{item:01d}_dwi')
    dwi_dir91rl_sbref = create_key('dwi/sub-{subject}_acq-dir90RL_run-{item:01d}_sbref')
    nback = create_key('func/sub-{subject}_task-nback_run-{item:01d}_bold')
    nback_sbref = create_key('func/sub-{subject}_task-nback_run-{item:01d}_sbref')
    fmap_lr = create_key('fmap/sub-{subject}_dir-1_run-{item:01d}_epi')
    fmap_rl = create_key('fmap/sub-{subject}_dir-2_run-{item:01d}_epi')
    t1 = create_key('anat/sub-{subject}_run-{item:01d}_T1w')
    t2 = create_key('anat/sub-{subject}_run-{item:01d}_T2w')
    info = {rs_lr: [], rs_rl: [], dwi_dir90lr: [], dwi_dir90rl: [], dwi_dir91lr: [], dwi_dir91rl: [], t1: [], t2: [], nback: [],
            rs_lr_sbref: [], rs_rl_sbref: [], dwi_dir90lr_sbref: [], dwi_dir90rl_sbref: [], dwi_dir91lr_sbref: [], dwi_dir91rl_sbref: [], nback_sbref: [],
            fmap_lr: [], fmap_rl: []}
    last_run = len(seqinfo)
    for s in seqinfo:
        print s[12]
        x,y,sl,nt = (s[6], s[7], s[8], s[9])
        if (nt == 1) and (s[12] == 'T1w_MPR_BIC_v1'):
            info[t1] = [s[2]]
        elif (nt == 1) and (s[12] == 'T2w_SPC_BIC_v1'):
            info[t2] = [s[2]]
        elif (s[12] == 'rfMRI_REST_LR_BIC_v2'):
            if (nt > 60):
                info[rs_lr].append(s[2])
            else:
                info[rs_lr_sbref].append(s[2])
        elif (s[12] == 'rfMRI_REST_RL_BIC_v2'):
            if (nt > 60):
                info[rs_rl].append(s[2])
            else:
                info[rs_rl_sbref].append(s[2])
        elif (s[12] == 'DWI_dir90_RL'):
            if (nt > 60):
                info[dwi_dir90rl].append(s[2])
            else:
                info[dwi_dir90rl_sbref].append(s[2])
        elif (s[12] == 'DWI_dir90_LR'):
            if (nt > 60):
                info[dwi_dir90lr].append(s[2])
            else:
                info[dwi_dir90lr_sbref].append(s[2])
        elif (s[12] == 'DWI_dir91_RL'):
            if (nt > 60):
                info[dwi_dir91rl].append(s[2])
            else:
                info[dwi_dir91rl_sbref].append(s[2])
        elif (s[12] == 'DWI_dir91_LR'):
            if (nt > 60):
                info[dwi_dir91lr].append(s[2])
            else:
                info[dwi_dir91lr_sbref].append(s[2])
        elif (s[12] == 'HPC Nback'):
            if (nt > 60):
                info[nback].append(s[2])
            else:
                info[nback_sbref].append(s[2])
        #elif (s[12] == 'SpinEchoFieldMap_RL_BIC_v2'):
        #    info[fmap_rl].append(s[2])
        #elif (s[12] == 'SpinEchoFieldMap_LR_BIC_v2'):
        #    info[fmap_lr].append(s[2])
        else:
            pass
    return info