"""
Heuristic demonstrating extraction of physiological data from CMRR
fMRI DICOMs

We want to make sure the run number for the _sbref, _phase and 
_physio matches that of the corresponding _bold. For "normal"
scanning, you can just rely on the {item} value, but if you have a
functional run with just saving the magnitude and then one saving
both magnitude and phase, you would have _run-01_bold, _run-02_bold
and _run-01_phase, but the phase image corresponds to _run-02_bold,
so the run number in the filename will not match
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

    info = {}
    run_no = 0
    for idx, s in enumerate(seqinfo):
        # We want to make sure the _SBRef, PhysioLog and phase series
        # (if present) are labeled the same as the main (magnitude)
        # image. So we only focus on the magnitude series (to exclude
        # phase images) without _SBRef at the end of the series_
        # description and then we search if the phase and/or _SBRef
        # are present.
        if (
            'epfid2d' in s.sequence_name
            and (
                'M' in s.image_type
                or 'FMRI' in s.image_type
            )
            and not s.series_description.lower().endswith('_sbref')
            and not 'DERIVED' in s.image_type
        ):
            run_no += 1
            bold = create_key(
                'sub-{subject}/func/sub-{subject}_task-test_run-%02d_bold' % run_no
            )
            info[bold] = [{'item': s.series_id}]
            next_series = idx+1    # used for physio log below

            ###   is phase image present?   ###
            # At least for Siemens systems, if magnitude/phase was
            # selected, the phase images come as a separate series
            # immediatelly following the magnitude series.
            # (note: make sure you don't check beyond the number of
            # elements in seqinfo...)
            if (
                idx+1 < len(seqinfo)
                and 'P' in seqinfo[idx+1].image_type
            ):
                phase = create_key(
                    'sub-{subject}/func/sub-{subject}_task-test_run-%02d_phase' % run_no
                )
                info[phase] = [{'item': seqinfo[idx+1].series_id}]
                next_series = idx+2    # used for physio log below

            ###   SBREF   ###
            # here, within the functional run code, check to see if
            # the previous run's series_description ended in _sbref,
            # to assign the same run number.
            if (
                idx > 0
                and seqinfo[idx-1].series_description.lower().endswith('_sbref')
            ):
                sbref = create_key(
                    'sub-{subject}/func/sub-{subject}_task-test_run-%02d_sbref' % run_no
                )
                info[sbref] = [{'item': seqinfo[idx-1].series_id}]

            ###   PHYSIO LOG   ###
            # here, within the functional run code, check to see if
            # the next run image_type lists "PHYSIO", to assign the
            # same run number.
            if (
                next_series < len(seqinfo)
                and 'PHYSIO' in seqinfo[next_series].image_type
            ):
                physio = create_key(
                    'sub-{subject}/func/sub-{subject}_task-test_run-%02d_physio' % run_no,
                    outtype = ('physio',)
                )
                info[physio] = [{'item': seqinfo[next_series].series_id}]

    return info
