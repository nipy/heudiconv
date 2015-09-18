import os

def create_key(template, outtype=('nii.gz',), annotation_classes=None):
    if template is None or not template:
        raise ValueError('Template must be a valid format string')
    return (template, outtype, annotation_classes)

def filter_dicom(dcmdata):
    """Return True if a DICOM dataset should be filtered out, else False"""
    comments = getattr(dcmdata, 'ImageComments', '')
    if len(comments):
        if 'reference volume' in comments.lower():
            print("Filter out image with comment '%s'" % comments)
            return True
    return False

def infotodict(seqinfo):
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module: 

    item: index within category 
    subject: participant id 
    seqitem: run number during scanning
    subindex: sub index within group
    """

    label_map = {
        'movie': 'movielocalizer',
        'retmap': 'retmap',
        'visloc': 'objectcategories',
    }
    info = {}
    for s in seqinfo:
        if not '_bold_' in s[12]:
            continue
        resolution = s[12].split('_')[-2][:-3]
        assert(float(resolution))

        templ = 'ses-%smm/func/{subject}_ses-%smm_task-orientation_run-{item:02d}' \
                % (resolution, resolution)
        if s[13] == True:
            templ += '_bolddico'
        else:
            templ += '_bold'
        key = create_key(templ)

        if not key in info:
            info[key] = []
        info[key].append(s[2])

    return info
