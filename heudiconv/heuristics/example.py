from __future__ import annotations

from typing import Optional

from heudiconv.utils import SeqInfo

# Dictionary to specify options for the `populate_intended_for`.
# Valid options are defined in 'bids.py' (for 'matching_parameters':
# ['Shims', 'ImagingVolume',]; for 'criterion': ['First', 'Closest']
POPULATE_INTENDED_FOR_OPTS = {
    "matching_parameters": "ImagingVolume",
    "criterion": "Closest",
}


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

    rs = create_key("rsfmri/rest_run{item:03d}/rest", outtype=("dicom", "nii.gz"))
    boldt1 = create_key("BOLD/task001_run{item:03d}/bold")
    boldt2 = create_key("BOLD/task002_run{item:03d}/bold")
    boldt3 = create_key("BOLD/task003_run{item:03d}/bold")
    boldt4 = create_key("BOLD/task004_run{item:03d}/bold")
    boldt5 = create_key("BOLD/task005_run{item:03d}/bold")
    boldt6 = create_key("BOLD/task006_run{item:03d}/bold")
    boldt7 = create_key("BOLD/task007_run{item:03d}/bold")
    boldt8 = create_key("BOLD/task008_run{item:03d}/bold")
    fm1 = create_key("fieldmap/fm1_{item:03d}")
    fm2 = create_key("fieldmap/fm2_{item:03d}")
    fmrest = create_key("fieldmap/fmrest_{item:03d}")
    dwi = create_key("dmri/dwi_{item:03d}", outtype=("dicom", "nii.gz"))
    t1 = create_key("anatomy/T1_{item:03d}")
    asl = create_key("rsfmri/asl_run{item:03d}/asl")
    aslcal = create_key("rsfmri/asl_run{item:03d}/cal_{subindex:03d}")
    info: dict[tuple[str, tuple[str, ...], None], list] = {
        rs: [],
        boldt1: [],
        boldt2: [],
        boldt3: [],
        boldt4: [],
        boldt5: [],
        boldt6: [],
        boldt7: [],
        boldt8: [],
        fm1: [],
        fm2: [],
        fmrest: [],
        dwi: [],
        t1: [],
        asl: [],
        aslcal: [[]],
    }
    last_run = len(seqinfo)
    for s in seqinfo:
        series_num_str = s.series_id.split("-", 1)[0]
        if not series_num_str.isdecimal():
            raise ValueError(
                f"This heuristic can operate only on data when series_id has form <series-number>-<something else>, "
                f"and <series-number> is a numeric number. Got series_id={s.series_id}"
            )
        series_num: int = int(series_num_str)
        sl, nt = (s.dim3, s.dim4)
        if (sl == 176) and (nt == 1) and ("MPRAGE" in s.protocol_name):
            info[t1] = [s.series_id]
        elif (nt > 60) and ("ge_func_2x2x2_Resting" in s.protocol_name):
            if not s.is_motion_corrected:
                info[rs].append(s.series_id)
        elif (
            (nt == 156)
            and ("ge_functionals_128_PACE_ACPC-30" in s.protocol_name)
            and series_num < last_run
        ):
            if not s.is_motion_corrected:
                info[boldt1].append(s.series_id)
                last_run = series_num
        elif (nt == 155) and ("ge_functionals_128_PACE_ACPC-30" in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt2].append(s.series_id)
        elif (nt == 222) and ("ge_functionals_128_PACE_ACPC-30" in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt3].append(s.series_id)
        elif (nt == 114) and ("ge_functionals_128_PACE_ACPC-30" in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt4].append(s.series_id)
        elif (nt == 156) and ("ge_functionals_128_PACE_ACPC-30" in s.protocol_name):
            if not s.is_motion_corrected and (series_num > last_run):
                info[boldt5].append(s.series_id)
        elif (nt == 324) and ("ge_func_3.1x3.1x4_PACE" in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt6].append(s.series_id)
        elif (nt == 250) and ("ge_func_3.1x3.1x4_PACE" in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt7].append(s.series_id)
        elif (nt == 136) and ("ge_func_3.1x3.1x4_PACE" in s.protocol_name):
            if not s.is_motion_corrected:
                info[boldt8].append(s.series_id)
        elif (nt == 101) and ("ep2d_pasl_FairQuipssII" in s.protocol_name):
            if not s.is_motion_corrected:
                info[asl].append(s.series_id)
        elif (nt == 1) and ("ep2d_pasl_FairQuipssII" in s.protocol_name):
            info[aslcal][0].append(s.series_id)
        elif (sl > 1) and (nt == 70) and ("DIFFUSION" in s.protocol_name):
            info[dwi].append(s.series_id)
        elif "field_mapping_128" in s.protocol_name:
            info[fm1].append(s.series_id)
        elif "field_mapping_3.1" in s.protocol_name:
            info[fm2].append(s.series_id)
        elif "field_mapping_Resting" in s.protocol_name:
            info[fmrest].append(s.series_id)
        else:
            pass
    return info
