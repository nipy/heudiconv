from __future__ import annotations

from typing import Optional

from heudiconv.utils import SeqInfo


def create_key(
    template: Optional[str],
    outtype: tuple[str, ...] = ("nii.gz", "dicom"),
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
    """
    t1 = create_key("anat/sub-{subject}_T1w")
    t2 = create_key("anat/sub-{subject}_T2w")
    rest = create_key("func/sub-{subject}_dir-{acq}_task-rest_run-{item:02d}_bold")
    face = create_key("func/sub-{subject}_task-face_run-{item:02d}_acq-{acq}_bold")
    gamble = create_key(
        "func/sub-{subject}_task-gambling_run-{item:02d}_acq-{acq}_bold"
    )
    conflict = create_key(
        "func/sub-{subject}_task-conflict_run-{item:02d}_acq-{acq}_bold"
    )
    dwi = create_key("dwi/sub-{subject}_dir-{acq}_run-{item:02d}_dwi")

    fmap_rest = create_key(
        "fmap/sub-{subject}_acq-func{acq}_dir-{dir}_run-{item:02d}_epi"
    )
    fmap_dwi = create_key(
        "fmap/sub-{subject}_acq-dwi{acq}_dir-{dir}_run-{item:02d}_epi"
    )

    info: dict[tuple[str, tuple[str, ...], None], list] = {
        t1: [],
        t2: [],
        rest: [],
        face: [],
        gamble: [],
        conflict: [],
        dwi: [],
        fmap_rest: [],
        fmap_dwi: [],
    }

    for idx, s in enumerate(seqinfo):
        if (s.dim3 == 208) and (s.dim4 == 1) and ("T1w" in s.protocol_name):
            info[t1] = [s.series_id]
        if (s.dim3 == 208) and ("T2w" in s.protocol_name):
            info[t2] = [s.series_id]
        if (s.dim4 >= 99) and (
            ("dMRI_dir98_AP" in s.protocol_name) or ("dMRI_dir99_AP" in s.protocol_name)
        ):
            acq = s.protocol_name.split("dMRI_")[1].split("_")[0] + "AP"
            info[dwi].append({"item": s.series_id, "acq": acq})
        if (s.dim4 >= 99) and (
            ("dMRI_dir98_PA" in s.protocol_name) or ("dMRI_dir99_PA" in s.protocol_name)
        ):
            acq = s.protocol_name.split("dMRI_")[1].split("_")[0] + "PA"
            info[dwi].append({"item": s.series_id, "acq": acq})
        if (s.dim4 == 1) and (
            ("dMRI_dir98_AP" in s.protocol_name) or ("dMRI_dir99_AP" in s.protocol_name)
        ):
            acq = s.protocol_name.split("dMRI_")[1].split("_")[0]
            info[fmap_dwi].append({"item": s.series_id, "dir": "AP", "acq": acq})
        if (s.dim4 == 1) and (
            ("dMRI_dir98_PA" in s.protocol_name) or ("dMRI_dir99_PA" in s.protocol_name)
        ):
            acq = s.protocol_name.split("dMRI_")[1].split("_")[0]
            info[fmap_dwi].append({"item": s.series_id, "dir": "PA", "acq": acq})
        if (s.dim4 == 420) and ("rfMRI_REST_AP" in s.protocol_name):
            info[rest].append({"item": s.series_id, "acq": "AP"})
        if (s.dim4 == 420) and ("rfMRI_REST_PA" in s.protocol_name):
            info[rest].append({"item": s.series_id, "acq": "PA"})
        if (s.dim4 == 1) and ("rfMRI_REST_AP" in s.protocol_name):
            if seqinfo[idx + 1][9] != 420:
                continue
            info[fmap_rest].append({"item": s.series_id, "dir": "AP", "acq": ""})
        if (s.dim4 == 1) and ("rfMRI_REST_PA" in s.protocol_name):
            info[fmap_rest].append({"item": s.series_id, "dir": "PA", "acq": ""})
        if (s.dim4 == 346) and ("tfMRI_faceMatching_AP" in s.protocol_name):
            info[face].append({"item": s.series_id, "acq": "AP"})
        if (s.dim4 == 346) and ("tfMRI_faceMatching_PA" in s.protocol_name):
            info[face].append({"item": s.series_id, "acq": "PA"})
        if (s.dim4 == 288) and ("tfMRI_conflict_AP" in s.protocol_name):
            info[conflict].append({"item": s.series_id, "acq": "AP"})
        if (s.dim4 == 288) and ("tfMRI_conflict_PA" in s.protocol_name):
            info[conflict].append({"item": s.series_id, "acq": "PA"})
        if (s.dim4 == 223) and ("tfMRI_gambling_AP" in (s.protocol_name)):
            info[gamble].append({"item": s.series_id, "acq": "AP"})
        if (s.dim4 == 223) and ("tfMRI_gambling_PA" in s.protocol_name):
            info[gamble].append({"item": s.series_id, "acq": "PA"})
    return info
