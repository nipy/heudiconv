from __future__ import annotations

from typing import Optional

import pydicom as dcm

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


def filter_dicom(dcmdata: dcm.dataset.Dataset) -> bool:
    """Return True if a DICOM dataset should be filtered out, else False"""
    comments = getattr(dcmdata, "ImageComments", "")
    if len(comments):
        if "reference volume" in comments.lower():
            print("Filter out image with comment '%s'" % comments)
            return True
    return False


def extract_moco_params(
    basename: str, _outypes: tuple[str, ...], dicoms: list[str]
) -> None:
    if "_rec-dico" not in basename:
        return
    from pydicom import dcmread

    # get acquisition time for all dicoms
    dcm_times = [
        (d, float(dcmread(d, stop_before_pixels=True).AcquisitionTime)) for d in dicoms
    ]
    # store MoCo info from image comments sorted by acquisition time
    moco = [
        "\t".join(
            [
                str(float(i))
                for i in dcmread(fn, stop_before_pixels=True)
                .ImageComments.split()[1]
                .split(",")
            ]
        )
        for fn, t in sorted(dcm_times, key=lambda x: x[1])
    ]
    outname = basename[:-4] + "recording-motion_physio.tsv"
    with open(outname, "wt") as fp:
        for m in moco:
            fp.write("%s\n" % (m,))


custom_callable = extract_moco_params


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

    info: dict[tuple[str, tuple[str, ...], None], list[str]] = {}
    for s in seqinfo:
        if "_bold_" not in s.protocol_name:
            continue
        if "_coverage" not in s.protocol_name:
            label = "orientation%s_run-{item:02d}"
        else:
            label = "coverage%s"
        resolution = s.protocol_name.split("_")[5][:-3]
        assert float(resolution)
        if s.is_motion_corrected:
            label = label % ("_rec-dico",)
        else:
            label = label % ("",)

        templ = "ses-%smm/func/{subject}_ses-%smm_task-%s_bold" % (
            resolution,
            resolution,
            label,
        )

        key = create_key(templ)

        if key not in info:
            info[key] = []
        info[key].append(s.series_id)

    return info
