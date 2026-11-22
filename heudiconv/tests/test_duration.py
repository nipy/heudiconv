from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import datetime
from glob import glob
import json
import os
import os.path as op
from pathlib import Path
from typing import Any
from unittest.mock import patch

import nibabel as nb
import numpy as np
import pydicom as dcm
from pydicom.dataset import Dataset
import pytest

from heudiconv.dicoms import FileTiming, get_file_timings
from heudiconv.duration import (
    Duration,
    SeriesHeader,
    estimate,
    from_dicoms,
    from_sidecar,
)

from .utils import TESTS_DATA_PATH, make_timed_dicoms

# What estimate() goes by, and what it gives, for each series of the
# dcm_qa* collections of DICOMs of https://github.com/neurolabusc.  Those
# durations are a record of what the code gave, to notice them change, and
# not a truth of their own.  What is independent of the code is "dcm2niix":
# the number of volumes and their RepetitionTime which dcm2niix made of a
# series, where it made a single 4D image of it.
# To check the record against, or regenerate it from, clones of those
# collections, set these variables to the directory with them, resp. to
# anything; a regenerated record is to be reviewed as any other change.
DCM_QA_TABLE = Path(TESTS_DATA_PATH) / "dcm_qa_durations.json"
DCM_QA_PATH = os.environ.get("HEUDICONV_TEST_DCM_QA")
DCM_QA_REGENERATE = os.environ.get("HEUDICONV_TEST_DCM_QA_REGENERATE")

START = datetime.datetime(2020, 1, 1, 12)


def _timings(*volumes: tuple[float, int | None, int | None]) -> list[FileTiming]:
    """Timings of files acquired (seconds from START, as numbered by either tag)."""
    return [
        FileTiming(START + datetime.timedelta(seconds=offset), number, position)
        for offset, number, position in volumes
    ]


def _numbered(*offsets: float, first: int = 1) -> list[FileTiming]:
    """Timings of volumes with consecutive AcquisitionNumbers at `offsets`."""
    return _timings(*((offset, first + i, None) for i, offset in enumerate(offsets)))


def _load_table() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(DCM_QA_TABLE.read_text())
    return rows


def _estimate_row(row: dict[str, Any]) -> Duration | None:
    timings = [
        timing
        for *volume, count in row["timings"]
        for timing in _timings(tuple(volume)) * count
    ]
    return estimate(SeriesHeader(**row["header"]), row["n_files"], timings)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "row", _load_table(), ids=lambda row: f"{row['first']} {row['description']}"
)
def test_estimate_of_dcm_qa(row: dict[str, Any]) -> None:
    found = _estimate_row(row)
    assert (found and [round(found.seconds, 4), found.source]) == row["duration"]
    # from the onsets of volumes it is that of as many RepetitionTime, unless
    # that is not how long a volume takes, as for ASL
    if (
        found
        and found.source.startswith("volumes numbered")
        and "dcm2niix" in row
        and "asl" not in row["description"].lower()
    ):
        volumes, repetition_time = row["dcm2niix"]
        assert found.seconds == pytest.approx(volumes * repetition_time, rel=0.02)


def _read_dcm_qa(path: str) -> list[dict[str, Any]]:  # pragma: no cover
    """Table rows for the series of the collections under `path`."""
    dcm2niix = {row["first"]: row.get("dcm2niix") for row in _load_table()}
    series = defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for filename in sorted(filenames):
            fn = op.join(dirpath, filename)
            with open(fn, "rb") as f:
                if f.read(132)[128:] != b"DICM":
                    continue
            uid = dcm.dcmread(fn, specific_tags=["SeriesInstanceUID"]).get(
                "SeriesInstanceUID"
            )
            if uid:
                series[op.relpath(fn, path).split(op.sep)[0], uid].append(fn)
    rows = []
    for fns in series.values():
        timings = get_file_timings(fns)
        dcm_data = dcm.dcmread(fns[0], stop_before_pixels=True, force=True)
        start = min((t.time for t in timings), default=START)
        volumes = Counter(
            (round((t.time - start).total_seconds(), 4), *t[1:]) for t in timings
        )
        found = from_dicoms(fns, timings)
        rows.append(
            {
                "first": op.relpath(fns[0], path),
                "description": str(dcm_data.get("SeriesDescription", "")),
                "header": {
                    k: v
                    for k, v in asdict(SeriesHeader.from_dicom(dcm_data)).items()
                    if v not in (None, False)
                },
                "n_files": len(fns),
                "timings": sorted(
                    ([*volume, count] for volume, count in volumes.items()), key=str
                ),
                "duration": found and [round(found.seconds, 4), found.source],
            }
        )
        if dcm2niix.get(rows[-1]["first"]):
            rows[-1]["dcm2niix"] = dcm2niix[rows[-1]["first"]]
    return sorted(rows, key=lambda row: row["first"])


@pytest.mark.ai_generated
@pytest.mark.skipif(not DCM_QA_PATH, reason="needs HEUDICONV_TEST_DCM_QA")
def test_dcm_qa_table_is_current() -> None:  # pragma: no cover
    assert DCM_QA_PATH
    rows = _read_dcm_qa(DCM_QA_PATH)
    if DCM_QA_REGENERATE:
        DCM_QA_TABLE.write_text(
            "[\n" + ",\n".join(json.dumps(row) for row in rows) + "\n]\n"
        )
    assert rows == _load_table()


# The rules of estimate(), the cases with a collection named being of what
# its series have, see docs/duration.rst
@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "header,n_files,timings,expected",
    [
        pytest.param(
            dict(repetition_time=1.0, acquisition_duration=27.89),
            20,
            _numbered(*range(20)),
            (20.0, "volumes numbered by AcquisitionNumber"),
            id="dcm_qa_xa30 BOLD: volumes, the tag counting 8 more TRs",
        ),
        pytest.param(
            dict(repetition_time=2.0),
            6,
            _timings(
                *((t + e, n, None) for n, t in enumerate([0, 2, 4]) for e in (0, 0.018))
            ),
            (6.0, "volumes numbered by AcquisitionNumber"),
            id="dcm_qa_me: a file per echo",
        ),
        pytest.param(
            {},
            4,
            _timings((0, 1, None), (0.5, 1, None), (2, 2, None), (4, 3, None)),
            (6.0, "volumes numbered by AcquisitionNumber"),
            id="onset of a volume is the earliest time of its files",
        ),
        pytest.param(
            {},
            4,
            _timings((0, 1, 1), (1, 2, 1), (2, 3, 2), (3, 4, 2)),
            (4.0, "volumes numbered by AcquisitionNumber"),
            id="AcquisitionNumber rather than TemporalPositionIdentifier",
        ),
        pytest.param(
            dict(repetition_time=1.81, acquisition_duration=602.735),
            2,
            _timings((0, 1, None), (36.2, 21, None)),
            (pytest.approx(38.01), "volumes numbered by AcquisitionNumber"),
            id="xa_4d_interrupted: volumes 1 and 21 of an aborted run",
        ),
        pytest.param(
            dict(repetition_time=0.25, acquisition_duration=248.0),
            8,
            _timings(*((8.0 * (i // 2), None, 1 + i // 2) for i in range(8))),
            (32.0, "volumes numbered by TemporalPositionIdentifier"),
            id="dcm_qa_philips_asl: volumes which take many TRs",
        ),
        pytest.param(
            dict(repetition_time=0.6, acquisition_duration=76.182),
            2,
            _timings((0, 1, None), (0.6025, 1, None)),
            (76.182, "AcquisitionDuration tag"),
            id="dcm_qa_xa30 field map: echoes a TR apart are of one volume",
        ),
        pytest.param(
            dict(repetition_time=3.0),
            2,
            _numbered(0, 3.0125),
            (6.0, "volumes numbered by AcquisitionNumber"),
            id="two volumes a TR apart",
        ),
        pytest.param(
            dict(repetition_time=3.0, siemens_duration=19.0),
            2,
            _numbered(0, 12.05),
            None,
            id="dcm_qa fMRI_MB: two volumes with reference scans in between",
        ),
        *(
            pytest.param(
                dict(repetition_time=3.0),
                2,
                _numbered(0, 3.0 * apart),
                expected and (6.0, "volumes numbered by AcquisitionNumber"),
                id=f"two volumes {apart} TR apart",
            )
            for apart, expected in [(0.94, None), (0.96, 1), (1.04, 1), (1.06, None)]
        ),
        pytest.param(
            {},
            4,
            _timings((0, 1, None), (9, None, None), (2, 2, None), (4, 3, None)),
            (6.0, "volumes numbered by AcquisitionNumber"),
            id="a file without a number among numbered volumes",
        ),
        pytest.param(
            dict(acquisition_duration=40.0),
            2,
            _numbered(0, 3.0),
            None,
            id="two volumes of unknown TR",
        ),
        pytest.param(
            dict(repetition_time=2.0, acquisition_duration=40.0),
            20,
            _timings(*((i // 10, None, 1 + i % 10) for i in range(20))),
            (40.0, "AcquisitionDuration tag"),
            id="dcm_qa_trt, were it not GE: times do not follow the numbers",
        ),
        pytest.param(
            dict(acquisition_duration=0.997),
            3,
            _timings((0, None, None), (1.0, None, None), (2.0, None, None)),
            None,
            id="dcm_qa_ep3d, were it not numbered: tag is of a volume",
        ),
        pytest.param(
            dict(acquisition_duration=2.0),
            2,
            _timings((0, None, None), (2.0, None, None)),
            (2.0, "AcquisitionDuration tag"),
            id="tag as long as the timestamps span",
        ),
        pytest.param(
            dict(acquisition_duration=349.76, siemens_duration=14.0),
            1,
            _timings((0, 1, None)),
            (349.76, "AcquisitionDuration tag"),
            id="tag of a single volume",
        ),
        pytest.param(
            dict(acquisition_duration=349.76),
            1,
            [],
            (349.76, "AcquisitionDuration tag"),
            id="tag of a file without a time",
        ),
        pytest.param(
            dict(manufacturer="UIH", acquisition_duration=190713.0),
            160,
            [],
            None,
            id="dcm_qa_uih: tag in milliseconds",
        ),
        pytest.param(
            dict(manufacturer="UIH", acquisition_duration=5000.0),
            1,
            [],
            None,
            id="UIH: tag which could be taken for seconds",
        ),
        pytest.param(
            dict(manufacturer="UIH Healthcare", acquisition_duration=5000.0),
            1,
            [],
            None,
            id="UIH, however spelled out",
        ),
        pytest.param(
            dict(acquisition_duration=14400.0),
            1,
            [],
            (14400.0, "AcquisitionDuration tag"),
            id="4 hours",
        ),
        pytest.param(
            dict(acquisition_duration=14400.1), 1, [], None, id="over 4 hours"
        ),
        pytest.param(
            dict(is_spectroscopy=True, acquisition_duration=4.0),
            64,
            [],
            None,
            id="dcm_qa_spec: tag is of each of the files",
        ),
        pytest.param(
            dict(siemens_duration=54.0, repetition_time=0.4),
            36,
            _timings(*((i / 100, 1, None) for i in range(36))),
            (54.0, "Siemens protocol"),
            id="dcm_qa_fmap: protocol, timestamps being of slices",
        ),
        pytest.param(
            dict(ge_duration=60.0, planned_volumes=60, ge_locations=77),
            240,
            _timings((0, 1, 1), (1, 1, 2)),
            (3.0, "GE's private tag, scaled to the stored volumes"),
            id="dcm_qa_ge: 3 of 60 volumes, and a part of one",
        ),
        pytest.param(
            dict(ge_duration=60.0, planned_volumes=60, ge_locations=77),
            4620,
            _timings((0, 1, 1)),
            (60.0, "GE's private tag"),
            id="GE: all the files, whichever have a time",
        ),
        pytest.param(
            dict(ge_duration=60.0, planned_volumes=60, ge_locations=1),
            59,
            [],
            (59.0, "GE's private tag, scaled to the stored volumes"),
            id="GE: all the volumes but one",
        ),
        pytest.param(
            dict(ge_duration=40.0, planned_volumes=10, ge_locations=54),
            540,
            [],
            (40.0, "GE's private tag"),
            id="dcm_qa_trt: all the volumes",
        ),
        pytest.param(
            dict(ge_duration=60.0, planned_volumes=60, ge_locations=77),
            70,
            [],
            (1.0, "GE's private tag, scaled to the stored volumes"),
            id="GE: not all of a volume",
        ),
        pytest.param(
            dict(ge_duration=327.0),
            196,
            _numbered(*range(20)),
            (327.0, "GE's private tag"),
            id="GE: not telling how many volumes",
        ),
        pytest.param(dict(repetition_time=2.0), 1, _numbered(0), None, id="nothing"),
    ],
)
def test_estimate(
    header: dict[str, Any],
    n_files: int,
    timings: list[FileTiming],
    expected: tuple[float, str] | None,
) -> None:
    assert estimate(SeriesHeader(**header), n_files, timings) == expected


def _in_groups(groups: str, **tags: Any) -> Dataset:
    group = Dataset()
    group.MRTimingAndRelatedParametersSequence = [Dataset()]
    for tag, value in tags.items():
        setattr(group.MRTimingAndRelatedParametersSequence[0], tag, value)
    dcm_data = Dataset()
    setattr(dcm_data, groups, [group])
    return dcm_data


def _with_top_level(dcm_data: Dataset, **tags: Any) -> Dataset:
    for tag, value in tags.items():
        setattr(dcm_data, tag, value)
    return dcm_data


def _dataset(**tags: Any) -> Dataset:
    dcm_data = Dataset()
    for tag, value in tags.items():
        setattr(dcm_data, tag, value)
    return dcm_data


def _with_private(tag: int, creator: str, vr: str, value: Any) -> Dataset:
    dcm_data = Dataset()
    dcm_data.add_new(tag & 0xFFFF0000 | 0x10, "LO", creator)
    dcm_data.add_new(tag, vr, value)
    return dcm_data


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "dcm_data,expected",
    [
        (Dataset(), {}),
        (_dataset(Manufacturer="UIH"), dict(manufacturer="UIH")),
        (
            _dataset(SOPClassUID="1.2.840.10008.5.1.4.1.1.4.2"),
            dict(is_spectroscopy=True),
        ),
        (_dataset(SOPClassUID="1.2.840.10008.5.1.4.1.1.4"), {}),
        (_dataset(RepetitionTime=1810), dict(repetition_time=1.81)),
        (_dataset(RepetitionTime=0), {}),
        # where enhanced DICOMs have it
        (
            _in_groups("SharedFunctionalGroupsSequence", RepetitionTime=1810),
            dict(repetition_time=1.81),
        ),
        (
            _in_groups("PerFrameFunctionalGroupsSequence", RepetitionTime=1810),
            dict(repetition_time=1.81),
        ),
        (_in_groups("SharedFunctionalGroupsSequence"), {}),
        # rather than one beside them
        (
            _with_top_level(
                _in_groups("SharedFunctionalGroupsSequence", RepetitionTime=1810),
                RepetitionTime=5,
            ),
            dict(repetition_time=1.81),
        ),
        (
            _dataset(SharedFunctionalGroupsSequence=[], RepetitionTime=1810),
            dict(repetition_time=1.81),
        ),
        (_dataset(AcquisitionDuration=12.5), dict(acquisition_duration=12.5)),
        (_dataset(AcquisitionDuration=-5.0), {}),
        (_dataset(NumberOfTemporalPositions=60), dict(planned_volumes=60)),
        (
            _with_private(0x0019105A, "GEMS_ACQU_01", "FL", 3.0118515e08),
            dict(ge_duration=pytest.approx(301.185)),
        ),
        # other vendors use that private group for something else
        (_with_private(0x0019105A, "SOME_OTHER_VENDOR_01", "FL", 3.0118515e08), {}),
        (_with_private(0x0021104F, "GEMS_RELA_01", "SS", 77), dict(ge_locations=77)),
    ],
)
def test_series_header(dcm_data: Dataset, expected: dict[str, Any]) -> None:
    assert SeriesHeader.from_dicom(dcm_data) == SeriesHeader(**expected)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "name,expected",
    [
        ("phantom.dcm", 14.0),
        # of 2 volumes (lRepetitions = 1), so its 17s could be of more than
        # there is of an aborted run
        ("axasc35.dcm", None),
    ],
)
def test_series_header_siemens_duration(name: str, expected: float | None) -> None:
    dcm_data = dcm.dcmread(op.join(TESTS_DATA_PATH, name), stop_before_pixels=True)
    assert SeriesHeader.from_dicom(dcm_data).siemens_duration == expected


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "dicoms,expected",
    [
        ("", None),
        # 3 volumes 4.15s (their TR) apart, not the 591s which their protocol
        # declares
        ("b0dwiForFmap/*.dcm", (12.45, "volumes numbered by AcquisitionNumber")),
        # a single volume: what its protocol declares
        ("phantom.dcm", (14.0, "Siemens protocol")),
        # nothing to go by: its protocol is of more than a volume
        ("axasc35.dcm", None),
        # volumes 1 and 21, 20 of their 1.81s TR apart, of an aborted run,
        # whose AcquisitionDuration of 602.735s is of what was planned
        ("xa_4d_interrupted/*", (38.01, "volumes numbered by AcquisitionNumber")),
    ],
)
def test_from_dicoms(dicoms: str, expected: tuple[float, str] | None) -> None:
    dicom_list = sorted(glob(op.join(TESTS_DATA_PATH, dicoms))) if dicoms else []
    found: Any = from_dicoms(dicom_list, get_file_timings(dicom_list))
    assert found == (expected and (pytest.approx(expected[0]), expected[1]))


@pytest.mark.ai_generated
def test_from_dicoms_goes_by_the_files_and_timings_given(tmp_path: Path) -> None:
    dicom_list = make_timed_dicoms(
        tmp_path, [2, 0, 4, 7], numbers=[2, 1, 3, 4], AcquisitionDuration=30.0
    )
    found: Any = from_dicoms(dicom_list, get_file_timings(dicom_list))
    assert found == (pytest.approx(7 + 7 / 3), "volumes numbered by AcquisitionNumber")
    # with the header of the first of them
    dcm_data = dcm.dcmread(dicom_list[-1])
    dcm_data.AcquisitionDuration = 99.0
    dcm.dcmwrite(dicom_list[-1], dcm_data)
    assert from_dicoms(dicom_list, []) == (30.0, "AcquisitionDuration tag")
    # and their number, whichever of them have timings
    with patch("heudiconv.duration.estimate") as estimate_:
        from_dicoms(dicom_list, [])
    assert estimate_.call_args.args[1:] == (4, [])


def _nifti(tmp_path: Path, name: str, shape: tuple[int, ...] | None) -> str:
    fn = tmp_path / name
    if shape is None:
        fn.write_bytes(b"")
    else:
        nb.Nifti1Image(np.zeros(shape), np.eye(4)).to_filename(fn)
    return str(fn)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "name,shape,meta,expected",
    [
        (
            "sub-1_task-rest_bold.nii.gz",
            (2, 2, 2, 10),
            # not AcquisitionDuration, which also counts what precedes them
            {"RepetitionTime": 2.0, "AcquisitionDuration": 27.89},
            (20.0, "RepetitionTime x volumes"),
        ),
        (
            "sub-1_dwi.nii.gz",
            (2, 2, 2, 7),
            {"RepetitionTime": 3.0},
            (21.0, "RepetitionTime x volumes"),
        ),
        *(
            ("sub-1_task-rest_bold.nii.gz", (2, 2, 2, 10), {"RepetitionTime": tr}, None)
            for tr in (None, 0, -1.0, float("nan"), float("inf"), "abc")
        ),
        # volumes which are not a RepetitionTime apart
        *(
            (
                f"sub-1_acq-x_{suffix}.nii.gz",
                (2, 2, 2, 10),
                {"RepetitionTime": 4.0},
                None,
            )
            for suffix in ("asl", "m0scan", "svs", "mrsi", "unloc", "mrsref")
        ),
        # two volumes are no single one
        (
            "sub-1_task-rest_bold.nii.gz",
            (2, 2, 2, 2),
            {"RepetitionTime": 2.0, "AcquisitionDuration": 27.89},
            (4.0, "RepetitionTime x volumes"),
        ),
        (
            "sub-1_task-rest_bold.nii.gz",
            (2, 2, 2, 10),
            {"RepetitionTime": 4.0, "ArterialSpinLabelingType": "PCASL"},
            None,
        ),
        (
            "sub-1_task-rest_bold.nii.gz",
            (2, 2, 2, 3),
            {"RepetitionTime": 2.0, "VolumeTiming": [0, 10, 20]},
            None,
        ),
        # a single volume: what the converter recorded, if anything
        (
            "sub-1_T1w.nii.gz",
            (2, 2, 2),
            {"RepetitionTime": 2.3, "AcquisitionDuration": 312.0},
            (312.0, "AcquisitionDuration of the sidecar"),
        ),
        (
            "sub-1_T1w.nii.gz",
            (2, 2, 2, 1),
            {"AcquisitionDuration": 312.0},
            (312.0, "AcquisitionDuration of the sidecar"),
        ),
        ("sub-1_T1w.nii.gz", (2, 2, 2), {"RepetitionTime": 2.3}, None),
        ("sub-1_T1w.nii.gz", (2, 2, 2), {"AcquisitionDuration": "junk"}, None),
        # not in seconds
        ("sub-1_T1w.nii.gz", (2, 2, 2), {"AcquisitionDuration": 190713.0}, None),
        # cannot tell how many volumes
        ("sub-1_T1w.nii.gz", None, {"AcquisitionDuration": 312.0}, None),
    ],
)
def test_from_sidecar(
    tmp_path: Path,
    name: str,
    shape: tuple[int, ...] | None,
    meta: dict[str, Any],
    expected: tuple[float, str] | None,
) -> None:
    assert from_sidecar(_nifti(tmp_path, name, shape), meta) == expected
