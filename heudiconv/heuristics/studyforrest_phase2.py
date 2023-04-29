from __future__ import annotations

from typing import Optional

from heudiconv.utils import SeqInfo

scaninfo_suffix = ".json"


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
) -> dict[tuple[str, tuple[str, ...], None], list[str]]:
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    """

    label_map = {
        "movie": "movielocalizer",
        "retmap": "retmap",
        "visloc": "objectcategories",
    }
    info: dict[tuple[str, tuple[str, ...], None], list[str]] = {}
    for s in seqinfo:
        if "EPI_3mm" not in s.protocol_name:
            continue
        label = s.protocol_name.split("_")[2].split()[0].strip("1234567890").lower()
        if label in ("movie", "retmap", "visloc"):
            key = create_key(
                "ses-localizer/func/{subject}_ses-localizer_task-%s_run-{item:01d}_bold"
                % label_map[label]
            )
        elif label == "sense":
            # pilot retmap had different description
            key = create_key(
                "ses-localizer/func/{subject}_ses-localizer_task-retmap_run-{item:01d}_bold"
            )
        elif label == "r":
            key = create_key(
                "ses-movie/func/{subject}_ses-movie_task-movie_run-%i_bold"
                % int(s.protocol_name.split("_")[2].split()[0][-1])
            )
        else:
            raise RuntimeError("YOU SHALL NOT PASS!")

        if key not in info:
            info[key] = []

        info[key].append(s.series_id)

    return info
