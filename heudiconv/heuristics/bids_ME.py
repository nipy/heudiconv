"""Heuristic demonstrating conversion of the Multi-Echo sequences.

It only cares about converting sequences which have _ME_ in their
series_description and outputs to BIDS.
"""


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
    bold = create_key('sub-{subject}/func/sub-{subject}_task-test_run-{item}_bold')

    info = {bold: []}
    for s in seqinfo:
        if '_ME_' in s.series_description:
            info[bold].append(s.series_id)
    return info
