from __future__ import annotations

import datetime
from glob import glob
import os.path as op
from pathlib import Path
from typing import Any

import pydicom as dcm
from pydicom.dataset import Dataset
import pytest

from heudiconv.duration import (
    estimate_duration_from_times,
    estimate_duration_from_volume_times,
    get_acquisition_duration,
    get_ge_acquisition_duration,
    get_repetition_time,
    get_siemens_declared_duration,
)

from .utils import TESTS_DATA_PATH, make_timed_dicoms


def _timestamps(offsets: list[float]) -> list[datetime.datetime]:
    start = datetime.datetime(2020, 1, 1, 12)
    return [start + datetime.timedelta(seconds=offset) for offset in offsets]


def _test_dicom(name: str) -> dcm.Dataset:
    return dcm.dcmread(op.join(TESTS_DATA_PATH, name), stop_before_pixels=True)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "creator,value,expected",
    [
        ("GEMS_ACQU_01", 3.0118515e08, pytest.approx(301.185)),
        # other vendors use that private group for something else
        ("SOME_OTHER_VENDOR_01", 3.0118515e08, None),
        ("GEMS_ACQU_01", 0.0, None),
        (None, None, None),
    ],
)
def test_get_ge_acquisition_duration(
    creator: str | None, value: float | None, expected: float | None
) -> None:
    dcm_data = _test_dicom("phantom.dcm")
    if creator:
        dcm_data.add_new((0x0019, 0x0010), "LO", creator)
        dcm_data.add_new((0x0019, 0x105A), "FL", value)
    assert get_ge_acquisition_duration(dcm_data) == expected


def _with_repetition_time(groups: str | None, value: Any) -> Dataset:
    timing = Dataset()
    timing.RepetitionTime = value
    if groups is None:
        return timing
    group = Dataset()
    group.MRTimingAndRelatedParametersSequence = [timing]
    dcm_data = Dataset()
    setattr(dcm_data, groups, [group])
    return dcm_data


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "dcm_data,expected",
    [
        (_with_repetition_time(None, 1810), 1.81),
        # where enhanced DICOMs have it
        (_with_repetition_time("SharedFunctionalGroupsSequence", 1810), 1.81),
        (_with_repetition_time("PerFrameFunctionalGroupsSequence", 1810), 1.81),
        (_with_repetition_time(None, 0), None),
        (_with_repetition_time(None, None), None),
        (Dataset(), None),
    ],
)
def test_get_repetition_time(dcm_data: Dataset, expected: float | None) -> None:
    assert get_repetition_time(dcm_data) == expected


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "name,expected",
    [
        ("phantom.dcm", 14.0),
        # of 2 volumes (lRepetitions = 1), so its 17s could be of more
        # than there is of an aborted run
        ("axasc35.dcm", None),
    ],
)
def test_get_siemens_declared_duration(name: str, expected: float | None) -> None:
    assert get_siemens_declared_duration(_test_dicom(name)) == expected


@pytest.mark.ai_generated
def test_get_siemens_declared_duration_without_protocol() -> None:
    dcm_data = _test_dicom("phantom.dcm")
    del dcm_data[(0x0029, 0x1020)]
    assert get_siemens_declared_duration(dcm_data) is None


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "offsets,repetition_time,expected",
    [
        ([2, 0, 1, 3], 1.0, 4.0),
        # within the tolerance of whole numbers of repetitions apart
        ([0, 1.23, 2.4575, 3.69], 1.23, pytest.approx(4.9175)),
        # some are missing: still up to a repetition past the last one
        ([0, 1, 5, 6], 1.0, 7.0),
        # each takes several repetitions, e.g. a pair of ASL volumes
        ([0, 9.1, 18.2], 4.55, pytest.approx(27.3)),
        # with just two it may as well be all there is of an aborted run
        ([0, 36.2], 1.81, pytest.approx(38.01)),
        # not of volumes: echoes, slices, or seconds on GE
        ([0, 0.022], 2.01, None),
        ([0, 0.5, 1, 1.5], 1.0, None),
        ([0, 1, 2.5], 1.0, None),
        # nothing to tell by
        ([0, 1, 2], None, None),
        ([3, 3], 1.0, None),
        ([], 1.0, None),
    ],
)
def test_estimate_duration_from_volume_times(
    offsets: list[float], repetition_time: float | None, expected: float | None
) -> None:
    timestamps = _timestamps(offsets)
    assert estimate_duration_from_volume_times(timestamps, repetition_time) == expected


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "offsets,expected",
    [
        # span plus the median interval, which for an even number of
        # intervals (1, 2, 4, 1) is the mean of the two middle ones
        ([0, 1, 3, 7, 8], 9.5),
        ([2, 0, 4, 7], 9.0),
        ([3, 3], None),  # need two distinct ones
        ([3], None),
        ([], None),
    ],
)
def test_estimate_duration_from_times(
    offsets: list[float], expected: float | None
) -> None:
    assert estimate_duration_from_times(_timestamps(offsets)) == expected


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "dicoms,expected",
    [
        ("", None),
        # 3 volumes 4.15s (their TR) apart, not the 591s which their
        # protocol declares
        ("b0dwiForFmap/*.dcm", 12.45),
        # a single volume: what its protocol declares
        ("phantom.dcm", 14.0),
        # nothing to go by: its protocol is of more than a volume
        ("axasc35.dcm", None),
        # 2 volumes, 20 of their 1.81s TR apart, of an aborted run, whose
        # AcquisitionDuration of 602.735s is of what was planned
        ("xa_4d_interrupted/*", 38.01),
    ],
)
def test_get_acquisition_duration_of_test_data(
    dicoms: str, expected: float | None
) -> None:
    dicom_list = sorted(glob(op.join(TESTS_DATA_PATH, dicoms))) if dicoms else []
    assert get_acquisition_duration(dicom_list) == (
        expected and pytest.approx(expected)
    )


# AcquisitionDuration, when not of a volume, also counts the preparation,
# reference and dummy scans which precede what gets stored.  The cases with
# a collection named are of series in https://github.com/neurolabusc/<it>
@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "offsets,tags,expected",
    [
        pytest.param(
            range(20),
            dict(RepetitionTime=1000, AcquisitionDuration=27.89),
            20.0,
            id="dcm_qa_xa30 BOLD: volumes, not the tag which counts 8 more TRs",
        ),
        pytest.param(
            [0, 1.23, 2.46],
            dict(RepetitionTime=1230, AcquisitionDuration=44.605),
            pytest.approx(3.69),
            id="dcm_qa_xa60 multiband BOLD: 33 TRs of reference scans",
        ),
        pytest.param(
            [0, 8, 16, 24],
            dict(RepetitionTime=250, AcquisitionDuration=40.0),
            32.0,
            id="dcm_qa_philips_asl: volumes which take many TRs",
        ),
        pytest.param(
            [0, 0.022],
            dict(RepetitionTime=2010, AcquisitionDuration=33.912),
            33.912,
            id="dcm_qa_physio dual echo: tag, timestamps being of echoes",
        ),
        pytest.param(
            [0],
            dict(AcquisitionDuration=349.76),
            349.76,
            id="tag of a single volume",
        ),
        pytest.param(
            [0, 0.1, 0.2, 0.3],
            dict(RepetitionTime=400),
            14.0,
            id="dcm_qa_fmap: protocol, timestamps being of slices within a TR",
        ),
        pytest.param(
            [0, 0.1, 4.0, 4.1],
            dict(RepetitionTime=400),
            14.0,
            id="protocol rather than timestamps of slices",
        ),
        pytest.param(
            [2, 0, 4, 7],
            dict(RepetitionTime=None),
            14.0,
            id="protocol rather than timestamps of unknown",
        ),
    ],
)
def test_get_acquisition_duration(
    tmp_path: Path, offsets: list[float], tags: dict[str, Any], expected: float
) -> None:
    dicom_list = make_timed_dicoms(tmp_path, offsets, **tags)
    assert get_acquisition_duration(dicom_list) == expected


def _without_protocol(dicom_list: list[str], private: dict[int, Any]) -> None:
    """Remove the Siemens (CSA) protocol of the files, and add `private` tags."""
    for fn in dicom_list:
        dcm_data = dcm.dcmread(fn)
        del dcm_data[(0x0029, 0x1020)]
        for tag, value in private.items():
            dcm_data.add_new(tag, "LO" if isinstance(value, str) else "FL", value)
        dcm.dcmwrite(fn, dcm_data)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "offsets,tags,private,expected",
    [
        pytest.param(
            [0, 1.0, 2.03, 3.045],
            dict(RepetitionTime=46.1, AcquisitionDuration=0.997),
            {},
            pytest.approx(4.06),
            id="dcm_qa_ep3d: timestamps, tag being of a volume and TR of a shot",
        ),
        pytest.param(
            [0, 0.018, 2.0, 2.018, 4.0, 4.018],
            dict(RepetitionTime=2000),
            {},
            pytest.approx(4.036),
            id="dcm_qa_me: timestamps of echoes of a few volumes",
        ),
        pytest.param(
            [0, 0.1, 0.2, 0.3],
            dict(RepetitionTime=400),
            {},
            None,
            id="none: timestamps of slices tell nothing of how long a volume took",
        ),
        pytest.param(
            [2, 0, 4, 7],
            dict(RepetitionTime=None),
            {},
            9.0,
            id="timestamps of unknown",
        ),
        pytest.param([0], {}, {}, None, id="none: a single timestamp"),
        pytest.param(
            [0, 1],
            dict(RepetitionTime=1000),
            {0x00190010: "GEMS_ACQU_01", 0x0019105A: 60.00006e6},
            pytest.approx(60.0),
            id="dcm_qa_ge: private tag, timestamps being just of seconds",
        ),
    ],
)
def test_get_acquisition_duration_without_protocol(
    tmp_path: Path,
    offsets: list[float],
    tags: dict[str, Any],
    private: dict[int, Any],
    expected: float | None,
) -> None:
    dicom_list = make_timed_dicoms(tmp_path, offsets, **tags)
    _without_protocol(dicom_list, private)
    assert get_acquisition_duration(dicom_list) == expected


@pytest.mark.ai_generated
def test_get_acquisition_duration_of_given_timestamps(tmp_path: Path) -> None:
    dicom_list = make_timed_dicoms(tmp_path, [2, 0, 4, 7])
    assert get_acquisition_duration(dicom_list, _timestamps([0, 1, 2])) == 3.0
