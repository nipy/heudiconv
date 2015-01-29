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
    
    rs = create_key('functional/{subject}_task010_run{item:03d}_rest')
    boldt1 = create_key('functional/{subject}_task001_run{item:03d}_bold')
    boldt2 = create_key('functional/{subject:03d}_task002_run{item:03d}_bold')
    boldt3 = create_key('functional/{subject:03d}_task003_run{item:03d}_bold')
    boldt4 = create_key('functional/{subject:03d}_task004_run{item:03d}_bold')
    boldt5 = create_key('functional/{subject:03d}_task005_run{item:03d}_bold')
    boldt6 = create_key('functional/{subject:03d}_task006_run{item:03d}_bold')
    boldt7 = create_key('functional/{subject:03d}_task007_run{item:03d}_bold')
    boldt8 = create_key('functional/{subject:03d}_task008_run{item:03d}_bold')
    fm1 = create_key('fieldmap/{subject:03d}_fieldmap_{item:03d}')
    dwi = create_key('diffusion/{subject:03d}_fieldmap_dwi_{item:03d}', outtype=('dicom', 'nii.gz'))
    t1 = create_key('anatomy/{subject:03d}_fieldmap_T1w_{item:03d}')
    asl = create_key('functional/{subject:03d}_task009_run{item:03d}_asl')
    aslcal = create_key('functional/{subject:03d}_task009_run{item:03d}_aslcal_{subindex:03d}')
    info = {rs: [], boldt1: [], boldt2: [], boldt3: [], boldt4: [], 
            boldt5: [], boldt6: [], boldt7: [], boldt8: [],
            fm1: [],  dwi: [], t1: [], 
            asl: [], aslcal: [[]]}
    last_run = len(seqinfo)
    for s in seqinfo:
        x,y,sl,nt = (s[6], s[7], s[8], s[9])
        if (sl == 176) and (nt == 1) and ('MPRAGE' in s[12]):
            info[t1] = [s[2]]
        elif (nt > 60) and ('ge_func_2x2x2_Resting' in s[12]):
            if not s[13]:
                info[rs].append(int(s[2]))
        elif (nt == 156) and ('ge_functionals_128_PACE_ACPC-30' in s[12]) and s[2] < last_run:
            if not s[13]:
                info[boldt1].append(s[2])
                last_run = s[2]
        elif (nt == 155) and ('ge_functionals_128_PACE_ACPC-30' in s[12]):
            if not s[13]:
                info[boldt2].append(s[2])
        elif (nt == 222) and ('ge_functionals_128_PACE_ACPC-30' in s[12]):
            if not s[13]:
                info[boldt3].append(s[2])
        elif (nt == 114) and ('ge_functionals_128_PACE_ACPC-30' in s[12]):
            if not s[13]:
                info[boldt4].append(s[2])
        elif (nt == 156) and ('ge_functionals_128_PACE_ACPC-30' in s[12]):
            if not s[13] and (s[2] > last_run):
                info[boldt5].append(s[2])
        elif (nt == 324) and ('ge_func_3.1x3.1x4_PACE' in s[12]):
            if not s[13]:
                info[boldt6].append(s[2])
        elif (nt == 250) and ('ge_func_3.1x3.1x4_PACE' in s[12]):
            if not s[13]:
                info[boldt7].append(s[2])
        elif (nt == 136) and ('ge_func_3.1x3.1x4_PACE' in s[12]):
            if not s[13]:
                info[boldt8].append(s[2])
        elif (nt == 101) and ('ep2d_pasl_FairQuipssII' in s[12]):
            if not s[13]:
                info[asl].append(s[2])
        elif (nt == 1) and ('ep2d_pasl_FairQuipssII' in s[12]):
            info[aslcal][0].append(s[2])
        elif (sl > 1) and (nt == 70) and ('DIFFUSION' in s[12]):
            info[dwi].append(s[2])
        elif ('field_mapping_128' in s[12]):
            info[fm].append(s[2])
        elif ('field_mapping_3.1' in s[12]):
            info[fm].append(s[2])
        elif ('field_mapping_Resting' in s[12]):
            info[fm].append(s[2])
        else:
            pass
    return info