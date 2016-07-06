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
    
    data = create_key('run{item:03d}', outtype=('nii.gz',))
    info = {data: []}
    last_run = len(seqinfo)
    for s in seqinfo:
        # TODO: clean it up -- unused stuff laying around
        x, y, sl, nt = (s[6], s[7], s[8], s[9])
        info[data].append(s[2])
    return info