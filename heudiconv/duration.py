"""Duration of an acquisition: how long its stored data took to acquire.

That is from the onset of the first stored volume, which is the `acq_time`
of `_scans.tsv`, to the end of the last one.  It leaves out the preparation,
reference and dummy scans which precede them, and which scanners count in
the durations they report.

All that HeuDiConv knows about establishing it is in this module, for it to
be replaceable as a whole should the converter (dcm2niix) come to report it:
:func:`from_dicoms` is used upon conversion, :func:`from_sidecar` for data
converted earlier, and :data:`SCANS_FIELDS` describes the result.  The rules,
what they are based on, and their limitations are in ``docs/duration.rst``.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import logging
import math
import os.path as op
from typing import Any, NamedTuple

import nibabel as nb
from nibabel.filename_parser import splitext_addext
import pydicom as dcm

from .dicoms import FileTiming, parse_private_csa_protocol

__all__ = ["Duration", "SCANS_FIELDS", "SOURCES", "from_dicoms", "from_sidecar"]

lgr = logging.getLogger(__name__)

#: What a duration could be established from, and what it then is of
SOURCES = OrderedDict(
    [
        (
            "volume-onsets",
            "From the onset of the first stored volume to the end of the last "
            "one, per the acquisition times of the volumes as numbered in the "
            "DICOMs. Does not include what precedes the first stored volume",
        ),
        (
            "ge-tag",
            "GE's private Acquisition Duration (0019,105A) of the DICOMs. "
            "Includes preparation and dummy scans",
        ),
        (
            "ge-tag-scaled",
            "As ge-tag, scaled to the share of the planned volumes which is stored",
        ),
        (
            "dicom-tag",
            "AcquisitionDuration (0018,9073) of the DICOMs. Includes "
            "preparation, reference and dummy scans, and is of what was "
            "planned should the scan have been aborted",
        ),
        (
            "siemens-protocol",
            "Scan time which the Siemens protocol of a single volume declares "
            "(lTotalScanTimeSec), in whole seconds",
        ),
        (
            "tr-x-volumes",
            "RepetitionTime times the number of volumes of the NIfTI, there "
            "being no DICOMs to tell",
        ),
        (
            "sidecar-tag",
            "AcquisitionDuration of the JSON sidecar of a single volume, as "
            "the converter recorded it, there being no DICOMs to tell",
        ),
    ]
)

#: Descriptions, for ``scans.json``, of the columns of ``_scans.tsv`` for a
#: :class:`Duration`: its seconds and its source
SCANS_FIELDS = OrderedDict(
    [
        (
            "duration",
            OrderedDict(
                [
                    ("LongName", "Scan duration"),
                    (
                        "Description",
                        "Wallclock duration of the scan, in seconds, from the "
                        "onset of the first to the end of the last stored volume "
                        "or sample, as established by HeuDiConv. What it "
                        "includes depends on duration_source. See also "
                        "https://github.com/bids-standard/bids-specification/pull/2508",
                    ),
                    ("Units", "s"),
                ]
            ),
        ),
        (
            "duration_source",
            OrderedDict(
                [
                    ("LongName", "Source of the scan duration"),
                    (
                        "Description",
                        "What HeuDiConv established duration from, which "
                        "determines what it includes",
                    ),
                    ("Levels", SOURCES),
                ]
            ),
        ),
    ]
)

# no acquisition takes that long: beyond it a tag is not in seconds
_LONGEST = 4 * 3600.0
# how far from a RepetitionTime, as a fraction of it, two volumes may be
# apart for them to be taken for consecutive ones
_CONSECUTIVE_TOLERANCE = 0.05
_SPECTROSCOPY_SOP_CLASS = "1.2.840.10008.5.1.4.1.1.4.2"
# BIDS suffixes of 4D images whose volumes are not a RepetitionTime apart
_NOT_REPETITION_PACED = {"asl", "m0scan", "svs", "mrsi", "unloc", "mrsref"}


class Duration(NamedTuple):
    seconds: float
    #: one of :data:`SOURCES`
    source: str


def from_dicoms(dicom_list: list[str], timings: list[FileTiming]) -> Duration | None:
    """Duration of the run stored in the files of `dicom_list`, None if unknown.

    `timings` are what :func:`heudiconv.dicoms.get_file_timings` returns for
    `dicom_list`.
    """
    if not dicom_list:
        return None
    dcm_data = dcm.dcmread(dicom_list[0], stop_before_pixels=True, force=True)
    return estimate(SeriesHeader.from_dicom(dcm_data), len(dicom_list), timings)


def from_sidecar(nifti_fn: str, meta: dict[str, Any]) -> Duration | None:
    """Duration of the run in `nifti_fn`, per it and its sidecar `meta`.

    For when there are no DICOMs to tell by.  Of volumes it is their number
    times ``RepetitionTime``, unless they are not that far apart: with
    ``VolumeTiming``, or for ASL and spectroscopy, which are told by the
    BIDS suffix of `nifti_fn` (or ``ArterialSpinLabelingType``).  Of a single
    volume it is the ``AcquisitionDuration`` which the converter recorded.
    None if unknown.  `nifti_fn` has to be readable, for how many it has.
    """
    shape = nb.load(nifti_fn).shape  # type: ignore[attr-defined]
    if len(shape) < 4 or shape[3] == 1:
        duration = _positive(meta.get("AcquisitionDuration"))
        if duration is None or duration > _LONGEST:
            return None
        return Duration(duration, "sidecar-tag")
    suffix = splitext_addext(op.basename(nifti_fn))[0].rpartition("_")[2]
    repetition_time = _positive(meta.get("RepetitionTime"))
    if (
        repetition_time is None
        or suffix in _NOT_REPETITION_PACED
        or {"VolumeTiming", "ArterialSpinLabelingType"} & meta.keys()
    ):
        return None
    return Duration(repetition_time * shape[3], "tr-x-volumes")


@dataclass(frozen=True)
class SeriesHeader:
    """What of the header of a DICOM of a series :func:`estimate` goes by."""

    manufacturer: str = ""
    is_spectroscopy: bool = False
    #: RepetitionTime, in seconds
    repetition_time: float | None = None
    #: AcquisitionDuration (0018,9073)
    acquisition_duration: float | None = None
    #: GE's private "Acquisition Duration" (0019,105A), in seconds
    ge_duration: float | None = None
    #: NumberOfTemporalPositions: of how many volumes `ge_duration` is
    planned_volumes: int | None = None
    #: GE's private "Locations in acquisition" (0021,104F): files per volume
    ge_locations: int | None = None
    #: lTotalScanTimeSec of a Siemens (CSA) protocol of a single volume
    siemens_duration: float | None = None

    @classmethod
    def from_dicom(cls, dcm_data: dcm.Dataset) -> SeriesHeader:
        repetition_time = _positive(_get_repetition_time(dcm_data))
        ge_duration = _positive(_get_private(dcm_data, 0x0019, 0x5A, "GEMS_ACQU_01"))
        return cls(
            manufacturer=str(dcm_data.get("Manufacturer", "")),
            is_spectroscopy=dcm_data.get("SOPClassUID") == _SPECTROSCOPY_SOP_CLASS,
            repetition_time=repetition_time and repetition_time / 1000,
            acquisition_duration=_positive(dcm_data.get("AcquisitionDuration")),
            # in microseconds: https://github.com/rordenlab/dcm2niix/issues/808
            ge_duration=ge_duration and ge_duration * 1e-6,
            planned_volumes=_whole(dcm_data.get("NumberOfTemporalPositions")),
            ge_locations=_whole(_get_private(dcm_data, 0x0021, 0x4F, "GEMS_RELA_01")),
            siemens_duration=_get_siemens_duration(dcm_data),
        )


def estimate(
    header: SeriesHeader, n_files: int, timings: list[FileTiming]
) -> Duration | None:
    """Duration of a series of `n_files` with such `header` and `timings`.

    The first of these to apply is used, see ``docs/duration.rst``:

    1. GE's private tag, scaled to the volumes stored;
    2. onsets of the numbered volumes;
    3. the ``AcquisitionDuration`` tag;
    4. the scan time which a Siemens protocol of a single volume declares.

    All but the second also count what precedes the first stored volume.
    """
    if header.is_spectroscopy:
        # AcquisitionDuration could be of each of its files
        return None
    if header.ge_duration is not None:
        return _scale_to_stored_volumes(header, n_files)
    for numbers in (
        [t.acquisition_number for t in timings],
        [t.temporal_position for t in timings],
    ):
        onsets = _get_onsets(numbers, timings)
        if onsets is not None:
            seconds = _span_volumes(onsets, header.repetition_time)
            if seconds is None:
                return None
            return Duration(seconds, "volume-onsets")
    times = [t.time for t in timings]
    span = (max(times) - min(times)).total_seconds() if times else 0.0
    tag = header.acquisition_duration
    # UIH has it in milliseconds; shorter than the span it is of a volume
    if tag and not header.manufacturer.startswith("UIH") and span <= tag <= _LONGEST:
        return Duration(tag, "dicom-tag")
    if header.siemens_duration is not None:
        return Duration(header.siemens_duration, "siemens-protocol")
    return None


def _scale_to_stored_volumes(header: SeriesHeader, n_files: int) -> Duration:
    """GE's duration, which is of all the volumes planned, for those stored."""
    assert header.ge_duration is not None
    planned, locations = header.planned_volumes, header.ge_locations
    if planned and locations and n_files // locations < planned:
        return Duration(
            header.ge_duration * max(n_files // locations, 1) / planned,
            "ge-tag-scaled",
        )
    return Duration(header.ge_duration, "ge-tag")


def _get_onsets(
    numbers: list[int | None], timings: list[FileTiming]
) -> list[tuple[int, float]] | None:
    """(number, seconds since the first) of each volume, None if not numbered.

    `numbers` are of the volumes which the files with `timings` belong to.
    They number volumes only if there are at least two of them, and their
    volumes follow in time as they do in number -- unlike on GE, where the
    times of the files do not tell their volumes apart.
    """
    earliest: dict[int, Any] = {}
    for number, timing in zip(numbers, timings, strict=True):
        if number is not None:
            earliest[number] = min(timing.time, earliest.get(number, timing.time))
    onsets = sorted(earliest.items())
    if len(onsets) < 2 or any(a[1] >= b[1] for a, b in zip(onsets, onsets[1:])):
        return None
    return [(n, (time - onsets[0][1]).total_seconds()) for n, time in onsets]


def _span_volumes(
    onsets: list[tuple[int, float]], repetition_time: float | None
) -> float | None:
    """From the first onset to the end of the last volume, None if unknown.

    A volume takes as long as their onsets are apart per their numbers.  That
    cannot be told from just two consecutive ones, where what precedes the
    second (e.g. reference scans) could be in between, unless they are a
    `repetition_time` apart.
    """
    (first, _), (last, span) = onsets[0], onsets[-1]
    if last - first > 1:
        return span + span / (last - first)
    if repetition_time and math.isclose(
        span, repetition_time, rel_tol=_CONSECUTIVE_TOLERANCE
    ):
        return 2 * repetition_time
    return None


def _get_repetition_time(dcm_data: dcm.Dataset) -> Any:
    """RepetitionTime, which enhanced DICOMs have within functional groups."""
    for groups in "SharedFunctionalGroupsSequence", "PerFrameFunctionalGroupsSequence":
        try:
            return (
                dcm_data[groups][0]
                .MRTimingAndRelatedParametersSequence[0]
                .RepetitionTime
            )
        except (KeyError, IndexError, AttributeError):
            pass
    return dcm_data.get("RepetitionTime")


def _get_siemens_duration(dcm_data: dcm.Dataset) -> float | None:
    """lTotalScanTimeSec of a Siemens (CSA) protocol, if it is of a single volume.

    For more of them (lRepetitions) it could be of an aborted run, with just
    a part of what was planned.
    """
    protocol = parse_private_csa_protocol(dcm_data)
    if protocol.get("lRepetitions"):
        return None
    return _positive(protocol.get("lTotalScanTimeSec"))


def _get_private(dcm_data: dcm.Dataset, group: int, offset: int, creator: str) -> Any:
    try:
        return dcm_data.get_private_item(group, offset, creator).value
    except KeyError:
        return None


def _positive(value: Any) -> float | None:
    """`value` as a float, None if it is not a finite positive number.

    >>> _positive("2.5")
    2.5
    >>> [_positive(v) for v in (None, "junk", "", 0, -1, "nan", "inf", 10**400)]
    [None, None, None, None, None, None, None, None]
    """
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _whole(value: Any) -> int | None:
    number = _positive(value)
    return None if number is None else int(number)
