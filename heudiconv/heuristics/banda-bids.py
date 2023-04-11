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


def infotodict(seqinfo: list[SeqInfo]) -> dict[tuple[str, tuple[str, ...], None], list]:
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    """
    t1 = create_key("sub-{subject}/anat/sub-{subject}_T1w")
    t2 = create_key("sub-{subject}/anat/sub-{subject}_T2w")
    rest = create_key("sub-{subject}/func/sub-{subject}_task-rest_run-{item:02d}_bold")
    rest_sbref = create_key(
        "sub-{subject}/func/sub-{subject}_task-rest_run-{item:02d}_sbref"
    )
    face = create_key("sub-{subject}/func/sub-{subject}_task-face_run-{item:02d}_bold")
    face_sbref = create_key(
        "sub-{subject}/func/sub-{subject}_task-face_run-{item:02d}_sbref"
    )
    gamble = create_key(
        "sub-{subject}/func/sub-{subject}_task-gambling_run-{item:02d}_bold"
    )
    gamble_sbref = create_key(
        "sub-{subject}/func/sub-{subject}_task-gambling_run-{item:02d}_sbref"
    )
    conflict = create_key(
        "sub-{subject}/func/sub-{subject}_task-conflict_run-{item:02d}_bold"
    )
    conflict_sbref = create_key(
        "sub-{subject}/func/sub-{subject}_task-conflict_run-{item:02d}_sbref"
    )
    dwi = create_key("sub-{subject}/dwi/sub-{subject}_run-{item:02d}_dwi")
    dwi_sbref = create_key("sub-{subject}/dwi/sub-{subject}_run-{item:02d}_sbref")
    fmap = create_key("sub-{subject}/fmap/sub-{subject}_dir-{dir}_run-{item:02d}_epi")

    info: dict[tuple[str, tuple[str, ...], None], list] = {
        t1: [],
        t2: [],
        rest: [],
        face: [],
        gamble: [],
        conflict: [],
        dwi: [],
        rest_sbref: [],
        face_sbref: [],
        gamble_sbref: [],
        conflict_sbref: [],
        dwi_sbref: [],
        fmap: [],
    }

    for s in seqinfo:
        # T1 and T2 scans
        if (s.dim3 == 208) and (s.dim4 == 1) and ("T1w" in s.protocol_name):
            info[t1] = [s.series_id]
        if (s.dim3 == 208) and ("T2w" in s.protocol_name):
            info[t2] = [s.series_id]
        # diffusion scans
        if "dMRI_dir9" in s.protocol_name:
            key = None
            if s.dim4 >= 99:
                key = dwi
            elif (s.dim4 == 1) and ("SBRef" in s.series_description):
                key = dwi_sbref
            if key:
                info[key].append({"item": s.series_id})
        # functional scans
        if "fMRI" in s.protocol_name:
            tasktype = s.protocol_name.split("fMRI")[1].split("_")[1]
            key = None
            if s.dim4 in [420, 215, 338, 280]:
                if "rest" in tasktype:
                    key = rest
                if "face" in tasktype:
                    key = face
                if "conflict" in tasktype:
                    key = conflict
                if "gambling" in tasktype:
                    key = gamble
            if (s.dim4 == 1) and ("SBRef" in s.series_description):
                if "rest" in tasktype:
                    key = rest_sbref
                if "face" in tasktype:
                    key = face_sbref
                if "conflict" in tasktype:
                    key = conflict_sbref
                if "gambling" in tasktype:
                    key = gamble_sbref
            if key:
                info[key].append({"item": s.series_id})
        if (s.dim4 == 3) and ("SpinEchoFieldMap" in s.protocol_name):
            dirtype = s.protocol_name.split("_")[-1]
            info[fmap].append({"item": s.series_id, "dir": dirtype})

    # You can even put checks in place for your protocol
    msg = []
    if len(info[t1]) != 1:
        msg.append("Missing correct number of t1 runs")
    if len(info[t2]) != 1:
        msg.append("Missing correct number of t2 runs")
    if len(info[dwi]) != 4:
        msg.append("Missing correct number of dwi runs")
    if len(info[rest]) != 4:
        msg.append("Missing correct number of resting runs")
    if len(info[face]) != 2:
        msg.append("Missing correct number of faceMatching runs")
    if len(info[conflict]) != 4:
        msg.append("Missing correct number of conflict runs")
    if len(info[gamble]) != 2:
        msg.append("Missing correct number of gamble runs")
    if msg:
        raise ValueError("\n".join(msg))
    return info
