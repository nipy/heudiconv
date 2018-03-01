import os

scaninfo_suffix = '.json'


def create_key(template, outtype=('nii.gz',), annotation_classes=None):
    if template is None or not template:
        raise ValueError('Template must be a valid format string')
    return template, outtype, annotation_classes


def filter_dicom(dcmdata):
    """Return True if a DICOM dataset should be filtered out, else False"""
    comments = getattr(dcmdata, 'ImageComments', '')
    if len(comments):
        if 'reference volume' in comments.lower():
            print("Filter out image with comment '%s'" % comments)
            return True
    return False


def extract_moco_params(basename, outypes, dicoms):
    if '_rec-dico' not in basename:
        return
    from dicom import read_file as dcm_read
    # get acquisition time for all dicoms
    dcm_times = [(d,
                  float(dcm_read(d, stop_before_pixels=True).AcquisitionTime))
                    for d in dicoms]
    # store MoCo info from image comments sorted by acqusition time
    moco = ['\t'.join(
        [str(float(i)) for i in dcm_read(fn, stop_before_pixels=True).ImageComments.split()[1].split(',')])
                for fn, t in sorted(dcm_times, key=lambda x: x[1])]
    outname = basename[:-4] + 'recording-motion_physio.tsv'
    with open(outname, 'wt') as fp:
        for m in moco:
            fp.write('%s\n' % (m,))

custom_callable = extract_moco_params


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
        if '_bold_' not in s[12]:
            continue
        if not '_coverage'in s[12]:
            label = 'orientation%s_run-{item:02d}'
        else:
            label = 'coverage%s'
        resolution = s[12].split('_')[5][:-3]
        assert(float(resolution))
        if s[13] == True:
            label = label % ('_rec-dico',)
        else:
            label = label % ('',)

        templ = 'ses-%smm/func/{subject}_ses-%smm_task-%s_bold' \
                % (resolution, resolution, label)

        key = create_key(templ)

        if key not in info:
            info[key] = []
        info[key].append(s[2])

    return info
