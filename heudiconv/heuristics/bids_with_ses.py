from __future__ import annotations

from typing import Optional

from heudiconv.utils import SeqInfo


def create_key(
    template: Optional[str],
    outtype: tuple[str, ...] = ("nii.gz",),
    annotation_classes: None = None,
) -> tuple[str, tuple[str, ...], None]:
    if template is None or not template:
        raise ValueError("Template must be a valid format string")
    return (template, outtype, annotation_classes)


def infotodict(
    seqinfo: list[SeqInfo],
) -> dict[tuple[str, tuple[str, ...], None], list]:
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    session: scan index for longitudinal acq
    """
    # for this example, we want to include copies of the DICOMs just for our T1
    # and functional scans
    outdicom = ("dicom", "nii.gz")

    t1 = create_key(
        "{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_T1w",
        outtype=outdicom,
    )
    t2 = create_key("{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_T2w")
    dwi_ap = create_key(
        "{bids_subject_session_dir}/dwi/{bids_subject_session_prefix}_dir-AP_dwi"
    )
    dwi_pa = create_key(
        "{bids_subject_session_dir}/dwi/{bids_subject_session_prefix}_dir-PA_dwi"
    )
    rs = create_key(
        "{bids_subject_session_dir}/func/{bids_subject_session_prefix}_task-rest_run-{item:02d}_bold",
        outtype=outdicom,
    )
    boldt1 = create_key(
        "{bids_subject_session_dir}/func/{bids_subject_session_prefix}_task-bird1back_run-{item:02d}_bold",
        outtype=outdicom,
    )
    boldt2 = create_key(
        "{bids_subject_session_dir}/func/{bids_subject_session_prefix}_task-letter1back_run-{item:02d}_bold",
        outtype=outdicom,
    )
    boldt3 = create_key(
        "{bids_subject_session_dir}/func/{bids_subject_session_prefix}_task-letter2back_run-{item:02d}_bold",
        outtype=outdicom,
    )

    info: dict[tuple[str, tuple[str, ...], None], list] = {
        t1: [],
        t2: [],
        dwi_ap: [],
        dwi_pa: [],
        rs: [],
        boldt1: [],
        boldt2: [],
        boldt3: [],
    }
    for s in seqinfo:
        if (
            (s.dim3 == 176 or s.dim3 == 352)
            and (s.dim4 == 1)
            and ("MEMPRAGE" in s.protocol_name)
        ):
            info[t1] = [s.series_id]
        elif (s.dim4 == 1) and ("MEMPRAGE" in s.protocol_name):
            info[t1] = [s.series_id]
        elif (
            (s.dim3 == 176 or s.dim3 == 352)
            and (s.dim4 == 1)
            and ("T2_SPACE" in s.protocol_name)
        ):
            info[t2] = [s.series_id]
        elif (s.dim4 >= 70) and ("DIFFUSION_HighRes_AP" in s.protocol_name):
            info[dwi_ap].append([s.series_id])
        elif "DIFFUSION_HighRes_PA" in s.protocol_name:
            info[dwi_pa].append([s.series_id])
        elif (s.dim4 == 144) and ("resting" in s.protocol_name):
            if not s.is_motion_corrected:
                info[rs].append([(s.series_id)])
        elif (s.dim4 == 183 or s.dim4 == 366) and ("localizer" in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt1].append([s.series_id])
        elif (s.dim4 == 227 or s.dim4 == 454) and ("transfer1" in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt2].append([s.series_id])
        elif (s.dim4 == 227 or s.dim4 == 454) and ("transfer2" in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt3].append([s.series_id])
    return info
