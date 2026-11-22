"""Duration of an acquisition, as established from its DICOMs.

All of it is here, behind :func:`get_acquisition_duration`, so that it could
be replaced as a whole should the converter (dcm2niix) come to report it.

The duration sought is that of the stored data: from the onset of the first
stored volume, which is the `acq_time` of `_scans.tsv`, to the end of the
last one.  It thus leaves out the preparation, reference and dummy scans
which precede them, and which scanners count in what they report.

What the rules are based on is in ``docs/duration.rst``.
"""

from __future__ import annotations

import datetime
import itertools
import logging

import pydicom as dcm

from .dicoms import get_acquisition_timestamps, parse_private_csa_header
from .utils import as_finite_positive_float, median_step

lgr = logging.getLogger(__name__)

# how far, as a fraction of RepetitionTime, an interval between two
# timestamps may be from a whole number of them for both to be of volumes
PER_VOLUME_TOLERANCE = 0.05


def get_acquisition_duration(
    dicom_list: list[str],
    timestamps: list[datetime.datetime] | None = None,
) -> float | None:
    """Duration in seconds of the run stored in the files of `dicom_list`.

    `timestamps`, if already at hand, are what
    :func:`heudiconv.dicoms.get_acquisition_timestamps` returns for them.
    Sources, in order, the first one to apply being used:

    1. GE's private tag (:func:`get_ge_acquisition_duration`), GE files
       having no times of their volumes to go by.
    2. Timestamps of the volumes (:func:`estimate_duration_from_volume_times`).
    3. The ``AcquisitionDuration`` tag, which also counts what precedes the
       first stored volume, and is of the planned duration if the run got
       aborted.  Not used if shorter than what the timestamps span, when it
       is of a single volume.
    4. The scan time declared in a Siemens protocol of a single volume
       (:func:`get_siemens_declared_duration`), which likewise counts it all.
    5. Timestamps of whatever they are of, e.g. slices
       (:func:`estimate_duration_from_times`), if they span more than a
       volume: within one they tell where in it a slice got acquired, not
       how long e.g. an anatomical took.

    None if none applies.
    """
    if not dicom_list:
        return None
    if timestamps is None:
        timestamps = get_acquisition_timestamps(dicom_list)
    dcm_data = dcm.dcmread(dicom_list[0], stop_before_pixels=True, force=True)
    repetition_time = get_repetition_time(dcm_data)
    times = sorted(set(timestamps))
    span = (times[-1] - times[0]).total_seconds() if times else 0.0

    def of_tag() -> float | None:
        duration = as_finite_positive_float(dcm_data.get("AcquisitionDuration"))
        return duration if duration is not None and duration >= span else None

    def of_times() -> float | None:
        if repetition_time is not None and span < repetition_time:
            return None
        return estimate_duration_from_times(timestamps)

    sources = {
        "GE's private tag": lambda: get_ge_acquisition_duration(dcm_data),
        "timestamps of volumes": lambda: estimate_duration_from_volume_times(
            timestamps, repetition_time
        ),
        "the AcquisitionDuration tag": of_tag,
        "the Siemens protocol": lambda: get_siemens_declared_duration(dcm_data),
        "timestamps": of_times,
    }
    for source, get in sources.items():
        duration = get()
        if duration is not None:
            lgr.debug("Duration of %s is %.3fs per %s", dicom_list[0], duration, source)
            return duration
    return None


def get_ge_acquisition_duration(dcm_data: dcm.Dataset) -> float | None:
    """Duration per GE's private "Acquisition Duration" (0019,105A), in microseconds.

    See https://github.com/rordenlab/dcm2niix/issues/808
    """
    try:
        elem = dcm_data.get_private_item(0x0019, 0x5A, "GEMS_ACQU_01")
    except KeyError:
        return None
    duration = as_finite_positive_float(elem.value)
    return duration and duration * 1e-6


def get_repetition_time(dcm_data: dcm.Dataset) -> float | None:
    """``RepetitionTime`` in seconds, None if there is none.

    In an enhanced DICOM it is within the functional groups.
    """
    candidates = [dcm_data]
    for groups in "SharedFunctionalGroupsSequence", "PerFrameFunctionalGroupsSequence":
        try:
            candidates.append(
                dcm_data[groups][0].MRTimingAndRelatedParametersSequence[0]
            )
        except (KeyError, IndexError, AttributeError):
            pass
    for candidate in candidates:
        value = as_finite_positive_float(candidate.get("RepetitionTime"))
        if value is not None:
            return value / 1000
    return None


def estimate_duration_from_volume_times(
    timestamps: list[datetime.datetime], repetition_time: float | None
) -> float | None:
    """Duration per `timestamps`, if they are of volumes `repetition_time` long.

    They are taken to be if the distinct ones are whole numbers of
    `repetition_time` apart; None otherwise.  The duration is from the
    earliest of them to the end of the volume of the latest one.  A volume
    is taken to last for the shortest of the intervals, which could be of
    several `repetition_time`, e.g. for a pair of ASL volumes.  With just
    two timestamps it is `repetition_time`, since what is between them may
    as well be all that is missing of an aborted run.
    """
    times = sorted(set(timestamps))
    if len(times) < 2 or not repetition_time:
        return None
    intervals = [(b - a).total_seconds() for a, b in itertools.pairwise(times)]
    for interval in intervals:
        volumes = interval / repetition_time
        if round(volumes) < 1 or abs(volumes - round(volumes)) > PER_VOLUME_TOLERANCE:
            return None
    volume = min(intervals) if len(intervals) > 1 else repetition_time
    return (times[-1] - times[0]).total_seconds() + volume


def estimate_duration_from_times(timestamps: list[datetime.datetime]) -> float | None:
    """Duration per `timestamps` of whatever regularly acquired, e.g. slices.

    From the earliest of them to their median interval, taken for how long
    each took, past the latest.  None if fewer than two are distinct.
    """
    times = sorted(set(timestamps))
    if len(times) < 2:
        return None
    duration: datetime.timedelta = times[-1] - times[0] + median_step(times)
    return duration.total_seconds()


def get_siemens_declared_duration(dcm_data: dcm.Dataset) -> float | None:
    """Scan time which a Siemens (CSA) protocol declares, ``lTotalScanTimeSec``.

    Only if the protocol is of a single volume (no ``lRepetitions``), since
    for more of them it could be of an aborted run, with just a part of
    what was planned.  None otherwise, or if there is no such protocol.
    """
    if parse_private_csa_header(dcm_data, "NumberOfTemporalPositions", "lRepetitions"):
        return None
    value = parse_private_csa_header(
        dcm_data, "AcquisitionDuration", "lTotalScanTimeSec"
    )
    return as_finite_positive_float(value) if value else None
