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
    """
    t1w = create_key("anat/sub-{subject}_T1w")
    t2w = create_key("anat/sub-{subject}_acq-{acq}_T2w")
    flair = create_key("anat/sub-{subject}_acq-{acq}_FLAIR")
    rest = create_key("func/sub-{subject}_task-rest_acq-{acq}_run-{item:02d}_bold")

    info: dict[tuple[str, tuple[str, ...], None], list] = {
        t1w: [],
        t2w: [],
        flair: [],
        rest: [],
    }

    for seq in seqinfo:
        x, _, z, n_vol, protocol, dcm_dir = (
            seq.dim1,
            seq.dim2,
            seq.dim3,
            seq.dim4,
            seq.protocol_name,
            seq.dcm_dir_name,
        )
        # t1_mprage --> T1w
        if (
            (z == 160)
            and (n_vol == 1)
            and ("t1_mprage" in protocol)
            and ("XX" not in dcm_dir)
        ):
            info[t1w] = [seq.series_id]
        # t2_tse --> T2w
        if (
            (z == 35)
            and (n_vol == 1)
            and ("t2_tse" in protocol)
            and ("XX" not in dcm_dir)
        ):
            info[t2w].append({"item": seq.series_id, "acq": "TSE"})
        # T2W --> T2w
        if (
            (z == 192)
            and (n_vol == 1)
            and ("T2W" in protocol)
            and ("XX" not in dcm_dir)
        ):
            info[t2w].append({"item": seq.series_id, "acq": "highres"})
        # t2_tirm --> FLAIR
        if (
            (z == 35)
            and (n_vol == 1)
            and ("t2_tirm" in protocol)
            and ("XX" not in dcm_dir)
        ):
            info[flair].append({"item": seq.series_id, "acq": "TIRM"})
        # t2_flair --> FLAIR
        if (
            (z == 160)
            and (n_vol == 1)
            and ("t2_flair" in protocol)
            and ("XX" not in dcm_dir)
        ):
            info[flair].append({"item": seq.series_id, "acq": "highres"})
        # T2FLAIR --> FLAIR
        if (
            (z == 192)
            and (n_vol == 1)
            and ("T2-FLAIR" in protocol)
            and ("XX" not in dcm_dir)
        ):
            info[flair].append({"item": seq.series_id, "acq": "highres"})
        # EPI (physio-matched) --> bold
        if (
            (x == 128)
            and (z == 28)
            and (n_vol == 300)
            and ("EPI" in protocol)
            and ("XX" not in dcm_dir)
        ):
            info[rest].append({"item": seq.series_id, "acq": "128px"})
        # EPI (physio-matched_NEW) --> bold
        if (
            (x == 64)
            and (z == 34)
            and (n_vol == 300)
            and ("EPI" in protocol)
            and ("XX" not in dcm_dir)
        ):
            info[rest].append({"item": seq.series_id, "acq": "64px"})
    return info
