"""Handle BIDS specific operations"""

from __future__ import annotations

__docformat__ = "numpy"

from collections import OrderedDict
from collections.abc import Sequence
import csv
import datetime
import errno
from glob import glob
import hashlib
import logging
import os
import os.path as op
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
from typing import Any
import warnings

import nibabel as nb
from nibabel.filename_parser import splitext_addext
import numpy as np
import pydicom as dcm

from . import __version__, dicoms
from .parser import find_files
from .utils import (
    as_finite_positive_float,
    create_file_if_missing,
    is_readonly,
    load_json,
    median_step,
    naive_if_mixed_tz,
    remove_prefix,
    remove_suffix,
    save_json,
    set_readonly,
    strptime,
    strptime_bids,
    update_json,
)

lgr = logging.getLogger(__name__)

# How far apart two acquisition times of the same run (e.g. `acq_time` and
# dcm2niix's sidecar AcquisitionTime) may be and still be considered the
# same: DICOM TM carries microseconds, but dcm2niix goes through a double
# when printing its AcquisitionTime, so allow for rounding
ACQ_TIME_TOLERANCE = datetime.timedelta(milliseconds=1)

# beyond this, an acq_time/DICOM gap looks like deliberately shifted
# (anonymized) dates rather than the interleaved-slice bias we target
ACQ_TIME_DATE_SHIFT_THRESHOLD = datetime.timedelta(hours=12)

# Fields to be populated in _scans files. Order matters
SCANS_FILE_FIELDS = OrderedDict(
    [
        ("filename", OrderedDict([("Description", "Name of the nifti file")])),
        (
            "acq_time",
            OrderedDict(
                [
                    ("LongName", "Acquisition time"),
                    ("Description", "Acquisition time of the particular scan"),
                ]
            ),
        ),
        (
            "duration",
            OrderedDict(
                [
                    ("LongName", "Scan duration"),
                    (
                        "Description",
                        "Wallclock duration of the scan, in seconds, from the "
                        "onset of the first to the end of the last acquired "
                        "volume or sample. Estimated from the DICOM headers "
                        "(see heudiconv.dicoms.get_acquisition_duration) or, "
                        "retrospectively, from the NIfTI/JSON sidecar. See also "
                        "https://github.com/bids-standard/bids-specification/pull/2508",
                    ),
                    ("Units", "s"),
                ]
            ),
        ),
        ("operator", OrderedDict([("Description", "Name of the operator")])),
        (
            "randstr",
            OrderedDict(
                [("LongName", "Random string"), ("Description", "md5 hash of UIDs")]
            ),
        ),
    ]
)

#: JSON Key where we will embed our version in the newly produced .json files
HEUDICONV_VERSION_JSON_KEY = "HeudiconvVersion"


class BIDSError(Exception):
    pass


BIDS_VERSION = "1.8.0"

# List defining allowed parameter matching for fmap assignment:
SHIM_KEY = "ShimSetting"
AllowedFmapParameterMatching = [
    "Shims",
    "ImagingVolume",
    "ModalityAcquisitionLabel",
    "CustomAcquisitionLabel",
    "PlainAcquisitionLabel",
    "Force",
]
# Key info returned by get_key_info_for_fmap_assignment when
# matching_parameter = "Force"
KeyInfoForForce = "Forced"
# List defining allowed criteria to assign a given fmap to a non-fmap run
# among the different fmaps with matching parameters:
AllowedCriteriaForFmapAssignment = [
    "First",
    "Closest",
]


def maybe_na(val: Any) -> str:
    """Return 'n/a' if non-None value represented as str is not empty

    Primarily for the consistent use of lower case 'n/a' so 'N/A' and 'NA'
    are also treated as 'n/a'
    """
    if val is not None:
        valstr = str(val).strip()
        return "n/a" if (not valstr or valstr in ("N/A", "NA")) else valstr
    else:
        return "n/a"


def treat_age(age: str | float | None) -> str | None:
    """Age might encounter 'Y' suffix or be a float"""
    if age is None:
        return None  # might be converted to N/A by maybe_na
    agestr = str(age)
    if agestr.endswith("M"):
        agestr = agestr.rstrip("M")
        ageflt = float(agestr) / 12
        agestr = ("%.2f" if ageflt != int(ageflt) else "%d") % ageflt
    else:
        agestr = agestr.rstrip("Y")
    if agestr:
        # strip all leading 0s but allow to scan a newborn (age 0Y)
        agestr = "0" if not agestr.lstrip("0") else agestr.lstrip("0")
        if agestr.startswith("."):
            # we had float point value, let's prepend 0
            agestr = "0" + agestr
    return agestr


def populate_bids_templates(path: str, defaults: dict[str, Any] | None = None) -> None:
    """Premake BIDS text files with templates"""

    lgr.info("Populating template files under %s", path)
    descriptor = op.join(path, "dataset_description.json")
    if defaults is None:
        defaults = {}
    if not op.lexists(descriptor):
        save_json(
            descriptor,
            OrderedDict(
                [
                    ("Name", "TODO: name of the dataset"),
                    ("BIDSVersion", BIDS_VERSION),
                    (
                        "License",
                        defaults.get(
                            "License",
                            "TODO: choose a license, e.g. PDDL "
                            "(http://opendatacommons.org/licenses/pddl/)",
                        ),
                    ),
                    (
                        "Authors",
                        defaults.get(
                            "Authors", ["TODO:", "First1 Last1", "First2 Last2", "..."]
                        ),
                    ),
                    (
                        "Acknowledgements",
                        defaults.get(
                            "Acknowledgements", "TODO: whom you want to acknowledge"
                        ),
                    ),
                    (
                        "HowToAcknowledge",
                        "TODO: describe how to acknowledge -- either cite a "
                        "corresponding paper, or just in acknowledgement "
                        "section",
                    ),
                    ("Funding", ["TODO", "GRANT #1", "GRANT #2"]),
                    ("ReferencesAndLinks", ["TODO", "List of papers or websites"]),
                    ("DatasetDOI", "TODO: eventually a DOI for the dataset"),
                ]
            ),
        )
    sourcedata_README = op.join(path, "sourcedata", "README")
    if op.exists(op.dirname(sourcedata_README)):
        create_file_if_missing(
            sourcedata_README,
            "TODO: Provide description about source data, e.g. \n"
            "Directory below contains DICOMS compressed into tarballs per "
            "each sequence, replicating directory hierarchy of the BIDS dataset"
            " itself.",
            # TODO: get from schema
            glob_suffixes=[".md", ".txt", ".rst", ""],
        )
    create_file_if_missing(
        op.join(path, "CHANGES"),
        "0.0.1  Initial data acquired\n"
        "TODOs:\n\t- verify and possibly extend information in participants.tsv"
        " (see for example http://datasets.datalad.org/?dir=/openfmri/ds000208)"
        "\n\t- fill out dataset_description.json, README, sourcedata/README"
        " (if present)\n\t- provide _events.tsv file for each _bold.nii.gz with"
        " onsets of events (see  '8.5 Task events'  of BIDS specification)",
    )
    create_file_if_missing(
        op.join(path, "README"),
        "TODO: Provide description for the dataset -- basic details about the "
        "study, possibly pointing to pre-registration (if public or embargoed)",
        # TODO: get from schema
        glob_suffixes=[".md", ".txt", ".rst", ""],
    )
    _ensure_scans_json(op.join(path, "scans.json"))
    create_file_if_missing(op.join(path, ".bidsignore"), ".duecredit.p")
    if op.lexists(op.join(path, ".git")):
        create_file_if_missing(op.join(path, ".gitignore"), ".duecredit.p")

    populate_aggregated_jsons(path)


def populate_aggregated_jsons(path: str) -> None:
    """Aggregate across the entire BIDS dataset ``.json``\\s into top level ``.json``\\s

    Top level .json files would contain only the fields which are
    common to all ``subject[/session]/type/*_modality.json``\\s.

    ATM aggregating only for ``*_task*_bold.json`` files. Only the task- and
    OPTIONAL _acq- field is retained within the aggregated filename.  The other
    BIDS _key-value pairs are "aggregated over".

    Parameters
    ----------
    path: str
      Path to the top of the BIDS dataset
    """
    # TODO: collect all task- .json files for func files to
    tasks = {}
    # way too many -- let's just collect all which are the same!
    # FIELDS_TO_TRACK = {'RepetitionTime', 'FlipAngle', 'EchoTime',
    #                    'Manufacturer', 'SliceTiming', ''}
    for fpath in find_files(
        r".*_task-.*\_bold\.json",
        topdir=glob(op.join(path, "sub-*")),
        exclude_vcs=True,
        exclude=r"/\.(datalad|heudiconv)/",
    ):
        #
        # According to BIDS spec I think both _task AND _acq (may be more?
        # _rec, _dir, ...?) should be retained?
        # TODO: if we are to fix it, then old ones (without _acq) should be
        # removed first
        task = re.sub(r".*_(task-[^_\.]*(_acq-[^_\.]*)?)_.*", r"\1", fpath)
        json_ = load_json(fpath, retry=100)
        if task not in tasks:
            tasks[task] = json_
        else:
            rec = tasks[task]
            # let's retain only those fields which have the same value
            for field in sorted(rec):
                if field not in json_ or json_[field] != rec[field]:
                    del rec[field]
        # create a stub onsets file for each one of those
        suf = "_bold.json"
        assert fpath.endswith(suf)

        # specify the name of the '_events.tsv' file:
        parsed_fpath = BIDSFile.parse(op.basename(fpath))
        for events_invalid_entity in ["chunk", "echo", "part"]:
            # events.tsv with these entities are not specified
            parsed_fpath.drop(events_invalid_entity, missing_ok=True)
        fpath = op.join(op.dirname(fpath), str(parsed_fpath))
        events_file = remove_suffix(fpath, suf) + "_events.tsv"
        # do not touch any existing thing, it may be precious
        if not op.lexists(events_file):
            lgr.debug("Generating %s", events_file)
            with open(events_file, "w") as fp:
                fp.write(
                    "onset\tduration\ttrial_type\tresponse_time\tstim_file"
                    "\tTODO -- fill in rows and add more tab-separated "
                    "columns if desired"
                )
    # extract tasks files stubs
    for task_acq, fields in tasks.items():
        task_file = op.join(path, task_acq + "_bold.json")
        # Since we are pulling all unique fields we have to possibly
        # rewrite this file to guarantee consistency.
        # See https://github.com/nipy/heudiconv/issues/277 for a usecase/bug
        # when we didn't touch existing one.
        # But the fields we enter (TaskName and CogAtlasID) might need need
        # to be populated from the file if it already exists
        placeholders = {
            "TaskName": (
                "TODO: full task name for %s" % task_acq.split("_")[0].split("-")[1]
            ),
            "CogAtlasID": "http://www.cognitiveatlas.org/task/id/TODO",
        }
        if op.lexists(task_file):
            j = load_json(task_file, retry=100)
            # Retain possibly modified placeholder fields
            for f in placeholders:
                if f in j:
                    placeholders[f] = j[f]
            act = "Regenerating"
        else:
            act = "Generating"
        lgr.debug("%s %s", act, task_file)
        fields.update(placeholders)
        save_json(task_file, fields, sort_keys=True, pretty=True)


def tuneup_bids_json_files(json_files: list[str]) -> None:
    """Given a list of BIDS .json files, e.g."""
    if not json_files:
        return
    # Harmonize generic .json formatting
    for jsonfile in json_files:
        json_ = load_json(jsonfile)
        # sanitize!
        for f1 in ["Acquisition", "Study", "Series"]:
            for f2 in ["DateTime", "Date"]:
                json_.pop(f1 + f2, None)
        # TODO:  should actually be placed into series file which must
        #        go under annex (not under git) and marked as sensitive
        # MG - Might want to replace with flag for data sensitivity
        # related - https://github.com/nipy/heudiconv/issues/92
        if "Date" in str(json_):
            # Let's hope no word 'Date' comes within a study name or smth like
            # that
            raise ValueError("There must be no dates in .json sidecar")
        # Those files should not have our version field already - should have been
        # freshly produced
        assert HEUDICONV_VERSION_JSON_KEY not in json_
        json_[HEUDICONV_VERSION_JSON_KEY] = str(__version__)
        save_json(jsonfile, json_, pretty=True)

    # Load the beast
    seqtype = op.basename(op.dirname(jsonfile))

    # MG - want to expand this for other _epi
    # possibly add IntendedFor automatically as well?
    if seqtype == "fmap":
        json_basename = "_".join(jsonfile.split("_")[:-1])
        # if we got by now all needed .json files -- we can fix them up
        # unfortunately order of "items" is not guaranteed atm
        json_phasediffname = json_basename + "_phasediff.json"
        json_mag = json_basename + "_magnitude*.json"
        if op.exists(json_phasediffname) and len(glob(json_mag)) >= 1:
            json_ = load_json(json_phasediffname)
            # TODO: we might want to reorder them since ATM
            # the one for shorter TE is the 2nd one!
            # For now just save truthfully by loading magnitude files
            lgr.debug("Placing EchoTime fields into phasediff file")
            for i in 1, 2:
                try:
                    json_["EchoTime%d" % i] = load_json(
                        json_basename + "_magnitude%d.json" % i
                    )["EchoTime"]
                except IOError as exc:
                    lgr.error("Failed to open magnitude file: %s", exc)
            # might have been made R/O already, but if not -- it will be set
            # only later in the pipeline, so we must not make it read-only yet
            _save_json_keeping_readonly(json_phasediffname, json_, pretty=True)


def add_participant_record(
    studydir: str, subject: str, age: str | None, sex: str | None
) -> None:
    participants_tsv = op.join(studydir, "participants.tsv")
    participant_id = "sub-%s" % subject

    if not create_file_if_missing(
        participants_tsv, "\t".join(["participant_id", "age", "sex", "group"]) + "\n"
    ):
        # check if may be subject record already exists
        with open(participants_tsv) as f:
            f.readline()
            known_subjects = {ln.split("\t")[0] for ln in f.readlines()}
        if participant_id in known_subjects:
            return
    else:
        # Populate participants.json (an optional file to describe column names in
        # participant.tsv). This auto generation will make BIDS-validator happy.
        participants_json = op.join(studydir, "participants.json")
        if not op.lexists(participants_json):
            save_json(
                participants_json,
                OrderedDict(
                    [
                        (
                            "participant_id",
                            OrderedDict([("Description", "Participant identifier")]),
                        ),
                        (
                            "age",
                            OrderedDict(
                                [
                                    (
                                        "Description",
                                        "Age in years (TODO - verify) as in the initial"
                                        " session, might not be correct for other sessions",
                                    )
                                ]
                            ),
                        ),
                        (
                            "sex",
                            OrderedDict(
                                [
                                    (
                                        "Description",
                                        "self-rated by participant, M for male/F for "
                                        "female (TODO: verify)",
                                    )
                                ]
                            ),
                        ),
                        (
                            "group",
                            OrderedDict(
                                [
                                    (
                                        "Description",
                                        "(TODO: adjust - by default everyone is in "
                                        "control group)",
                                    )
                                ]
                            ),
                        ),
                    ]
                ),
                sort_keys=False,
            )

    # Add a new participant
    with open(participants_tsv, "a") as f:
        f.write(
            "\t".join(
                map(
                    str,
                    [
                        participant_id,
                        maybe_na(treat_age(age)),
                        maybe_na(sex),
                        "control",
                    ],
                )
            )
            + "\n"
        )


def find_subj_ses(f_name: str) -> tuple[str | None, str | None]:
    """Given a path to the bids formatted filename parse out subject/session"""
    # we will allow the match at either directories or within filename
    # assuming that bids layout is "correct"
    regex = re.compile("sub-(?P<subj>[a-zA-Z0-9]*)([/_]ses-(?P<ses>[a-zA-Z0-9]*))?")
    regex_res = regex.search(f_name)
    res = regex_res.groupdict() if regex_res else {}
    return res.get("subj", None), res.get("ses", None)


def save_scans_key(
    item: tuple[str, tuple[str, ...], list[str]], bids_files: list[str]
) -> None:
    """
    Parameters
    ----------
    item:
    bids_files: list of str

    Returns
    -------

    """
    rows = {}
    assert bids_files, "we do expect some files since it was called"
    # we will need to deduce subject and session from the bids_filename
    # and if there is a conflict, we would just blow since this function
    # should be invoked only on a result of a single item conversion as far
    # as I see it, so should have the same subject/session
    subj: str | None = None
    ses: str | None = None
    # all bids_files of this item share the same source DICOMs, hence the row
    timestamps = dicoms.get_acquisition_timestamps(item[-1])
    scan_key_row = get_formatted_scans_key_row(item[-1], timestamps)
    for bids_file in bids_files:
        # get filenames
        f_name = "/".join(bids_file.split("/")[-2:])
        f_name = f_name.replace("json", "nii.gz")
        rows[f_name] = scan_key_row
        subj_, ses_ = find_subj_ses(f_name)
        if not subj_:
            lgr.warning(
                "Failed to detect fulfilled BIDS layout.  "
                "No scans.tsv file(s) will be produced for %s",
                ", ".join(bids_files),
            )
            return
        if subj and subj_ != subj:
            raise ValueError(
                "We found before subject %s but now deduced %s from %s"
                % (subj, subj_, f_name)
            )
        subj = subj_
        if ses and ses_ != ses:
            raise ValueError(
                "We found before session %s but now deduced %s from %s"
                % (ses, ses_, f_name)
            )
        ses = ses_
    try:
        check_acq_time_congruency(
            min(timestamps, default=None),
            [f for f in bids_files if f.endswith(".json")],
            label=op.basename(item[0]),
            timestamps=timestamps,
            fix=True,
        )
    except (OSError, ValueError) as exc:
        # an unreadable sidecar is not worth aborting the conversion for
        lgr.warning("Failed to check acq_time of %s: %s", item[0], exc)
    # where should we store it?
    output_dir = op.dirname(op.dirname(bids_file))
    # save
    ses = "_ses-%s" % ses if ses else ""
    add_rows_to_scans_keys_file(
        op.join(output_dir, "sub-{0}{1}_scans.tsv".format(subj, ses)), rows
    )


def _save_json_keeping_readonly(json_file: str, data: Any, **kwargs: Any) -> None:
    """:func:`save_json`, which replaces `json_file`, keeping it read-only if it was."""
    was_readonly = op.exists(json_file) and is_readonly(json_file)
    save_json(json_file, data, **kwargs)
    if was_readonly:
        set_readonly(json_file)


def _ensure_scans_json(scans_json: str) -> None:
    """Create `scans_json`, or add the ``SCANS_FILE_FIELDS`` keys it is missing.

    Anything else in an existing one, e.g. user-defined keys, is left
    untouched, and so is one without content (e.g. annexed and not present).
    """
    if op.islink(scans_json) and not op.exists(scans_json):
        return
    meta = load_json(scans_json) if op.exists(scans_json) else {}
    if not isinstance(meta, dict):
        raise ValueError(f"{scans_json} does not contain a JSON object")
    missing = {k: v for k, v in SCANS_FILE_FIELDS.items() if k not in meta}
    if missing:
        _save_json_keeping_readonly(scans_json, {**meta, **missing}, sort_keys=False)


def _merge_scans_header(existing_header: list[str], additions: list[str]) -> list[str]:
    """Extend `existing_header` with whichever of `additions` it is missing.

    Every existing column is kept (BIDS allows custom ones), and a missing
    one goes right after the one preceding it in `additions`, so e.g. a new
    "duration" lands next to "acq_time".

    >>> _merge_scans_header(["filename", "acq_time", "custom"], ["acq_time", "duration"])
    ['filename', 'acq_time', 'duration', 'custom']
    """
    merged = list(existing_header)
    for previous, column in zip([None, *additions], additions):
        if column not in merged:
            at = merged.index(previous) + 1 if previous in merged else len(merged)
            merged.insert(at, column)
    return merged


# a row of a `_scans.tsv`: its fields by column name, a missing one being
# None, and any beyond the header listed under the key None
_ScansRow = dict[Any, Any]


def _read_scans_tsv(scans_tsv: str) -> tuple[list[str], list[_ScansRow]]:
    """Read a `_scans.tsv` file into (fieldnames, rows)."""
    with open(scans_tsv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def _write_scans_tsv(
    scans_tsv: str, fieldnames: list[str], rows: list[_ScansRow]
) -> None:
    """(Re)write `scans_tsv` atomically, keeping the permissions of an existing one.

    Replacing the directory entry also works for a read-only file or a
    symlink into git-annex, and leaves the original intact on failure.
    """
    tmp = f"{scans_tsv}.{os.getpid()}.tmp"
    # not mkstemp(), which would not give a new file its umask-default mode
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(fieldnames)
            writer.writerows(
                ["n/a" if row.get(k) is None else row[k] for k in fieldnames]
                + row.get(None, [])
                for row in rows
            )
        if op.exists(scans_tsv):
            shutil.copymode(scans_tsv, tmp)
        os.replace(tmp, scans_tsv)
    finally:
        Path(tmp).unlink(missing_ok=True)


def add_rows_to_scans_keys_file(fn: str, newrows: dict[str, list[str]]) -> None:
    """Add or refresh rows in the _scans file.

    Parameters
    ----------
    fn: str
      filename
    newrows: dict
      rows to add or, for a file already in `fn` (e.g. re-converted with
      `--overwrite`), update (acquisition time, duration, referring
      physician, random string), in the order of ``SCANS_FILE_FIELDS``
      (excluding "filename")
    """
    canonical = list(SCANS_FILE_FIELDS.keys())
    header, rows = _read_scans_tsv(fn) if op.lexists(fn) else ([], [])
    # values are matched to columns by name, so that a file written by an
    # older heudiconv (e.g. without "duration") or with extra (e.g.
    # user-added) columns keeps every value under its own column
    header = _merge_scans_header(header or canonical, canonical)
    fnames2info = {row["filename"]: row for row in rows if row.get("filename")}
    for filename, values in newrows.items():
        fnames2info.setdefault(filename, {"filename": filename}).update(
            zip(canonical[1:], values, strict=True)
        )
    # sort by the date/filename
    _write_scans_tsv(
        fn,
        header,
        sorted(
            fnames2info.values(),
            key=lambda row: (row.get("acq_time") or "n/a", row["filename"]),
        ),
    )


def get_formatted_scans_key_row(
    dcm_fns: str | Path | Sequence[str | Path],
    timestamps: list[datetime.datetime] | None = None,
) -> list[str]:
    """Build a `_scans.tsv` data row for one converted item.

    Parameters
    ----------
    dcm_fns: str or Path, or sequence of str or Path
        A single representative DICOM, or -- preferably -- every DICOM of
        the run, letting `duration` be estimated from timestamps when no
        `AcquisitionDuration` tag is available, and `acq_time` be the
        earliest of them rather than whichever sorts first
        (https://github.com/nipy/heudiconv/issues/876).
    timestamps: list of datetime, optional
        What :func:`heudiconv.dicoms.get_acquisition_timestamps` returns for
        `dcm_fns`, if already at hand.

    Returns
    -------
    row: list
        [ISO acquisition time, duration in seconds (or 'n/a'), performing
        physician name, random string]
    """
    if isinstance(dcm_fns, (str, Path)):
        dcm_fns = [dcm_fns]
    dcm_fn_strs: list[str] = [str(f) for f in dcm_fns]
    if timestamps is None:
        timestamps = dicoms.get_acquisition_timestamps(dcm_fn_strs)
    dcm_data = dcm.dcmread(dcm_fn_strs[0], stop_before_pixels=True, force=True)
    acq_datetime = min(timestamps, default=None)
    acq_duration = dicoms.get_acquisition_duration(dcm_fn_strs, timestamps)
    # add random string
    # But let's make it reproducible by using all UIDs
    # (might change across versions?)
    randcontent = "".join(
        [getattr(dcm_data, f) or "" for f in sorted(dir(dcm_data)) if f.endswith("UID")]
    )
    randstr = hashlib.md5(randcontent.encode()).hexdigest()[:8]
    try:
        perfphys = dcm_data.PerformingPhysicianName
    except AttributeError:
        perfphys = ""
    row = [
        acq_datetime.isoformat() if acq_datetime else "",
        _format_duration(acq_duration),
        perfphys,
        randstr,
    ]
    # empty entries should be 'n/a'
    # https://github.com/dartmouth-pbs/heudiconv/issues/32
    return ["n/a" if not str(e) else e for e in row]


def _get_sidecar_acquisition_datetime(
    json_file: str, near: datetime.datetime
) -> datetime.datetime | None:
    """Return the time-of-day `AcquisitionTime` of a JSON sidecar as a datetime.

    On whichever day puts it closest to `near`, so a run straddling midnight
    is handled.  None if the sidecar has no `AcquisitionTime`.
    """
    acq_time = load_json(json_file).get("AcquisitionTime")
    if not acq_time:
        return None
    time_ = strptime(str(acq_time), ["%H:%M:%S.%f", "%H:%M:%S"]).time()
    candidates = [
        # the sidecar carries the same local wall time as a timezone-aware
        # `near` (from DICOM TimezoneOffsetFromUTC), so take its tzinfo
        datetime.datetime.combine(
            near.date() + datetime.timedelta(days=d), time_, tzinfo=near.tzinfo
        )
        for d in (-1, 0, 1)
    ]
    return min(candidates, key=lambda c: abs(c - near))


def check_acq_time_congruency(
    acq_datetime: datetime.datetime | None,
    json_files: Sequence[str],
    label: str,
    timestamps: Sequence[datetime.datetime] = (),
    fix: bool = False,
) -> None:
    """Check `acq_time` against dcm2niix's sidecar `AcquisitionTime`, fixing it if `fix`.

    `acq_time` is the earliest acquisition timestamp across the run's DICOMs
    (`timestamps`, see :func:`get_formatted_scans_key_row`), whereas dcm2niix
    records that of the first DICOM in its own order, which can be later
    (https://github.com/nipy/heudiconv/issues/876,
    https://github.com/rordenlab/dcm2niix/issues/1039).  When that is
    unambiguously what happened -- `acq_time` is the earliest of
    `timestamps`, and all `json_files` record the same `AcquisitionTime`,
    one of the later `timestamps` -- the sidecars are corrected in place if
    `fix`.  Any other disagreement is only warned about.

    Parameters
    ----------
    acq_datetime: datetime or None
        The datetime reported as `acq_time` for the run. Nothing is checked
        if None.
    json_files: sequence of str
        JSON sidecars produced for the run.
    label: str
        What to refer to the run as in the log, e.g. its file name.
    timestamps: sequence of datetime, optional
        Acquisition timestamps of all DICOMs of the run.  Without them,
        nothing is considered unambiguous enough to fix.
    fix: bool, optional
        Whether to correct the sidecars when unambiguous.
    """
    if acq_datetime is None:
        return

    def close(dt1: datetime.datetime, dt2: datetime.datetime) -> bool:
        # e.g. a historical, naive acq_time vs timezone-aware DICOM timestamps
        dt1, dt2 = naive_if_mixed_tz([dt1, dt2])
        return abs(dt1 - dt2) <= ACQ_TIME_TOLERANCE

    sidecar_times = {
        json_file: dt
        for json_file in json_files
        if (dt := _get_sidecar_acquisition_datetime(json_file, acq_datetime))
        is not None
    }
    if not sidecar_times:
        return
    # dcm2niix may split a series into several outputs (e.g. echoes, or
    # localizer planes) with legitimately different AcquisitionTimes -- the
    # earliest of them is what corresponds to acq_time
    json_file, sidecar_datetime = min(sidecar_times.items(), key=lambda i: i[1])
    if close(sidecar_datetime, acq_datetime):
        return
    fixable = (
        bool(timestamps)
        and close(acq_datetime, min(timestamps))
        and len(sidecar_times) == len(json_files)
        and all(close(dt, sidecar_datetime) for dt in sidecar_times.values())
        and any(close(sidecar_datetime, t) for t in timestamps)
    )
    if fixable and fix:
        acq_time_str = acq_datetime.strftime("%H:%M:%S.%f")
        for f in sidecar_times:
            _save_json_keeping_readonly(
                f, {**load_json(f), "AcquisitionTime": acq_time_str}, pretty=True
            )
        lgr.info(
            "%s: corrected AcquisitionTime recorded by dcm2niix from %s to "
            "%s, the earliest of its DICOMs, in %s -- see "
            "https://github.com/rordenlab/dcm2niix/issues/1039",
            label,
            sidecar_datetime.time().isoformat(),
            acq_time_str,
            ", ".join(op.basename(f) for f in sidecar_times),
        )
        return
    lgr.warning(
        "%s: acq_time %s disagrees with AcquisitionTime %s (%+.6f "
        "seconds) recorded by dcm2niix in %s%s",
        label,
        acq_datetime.time().isoformat(),
        sidecar_datetime.time().isoformat(),
        (sidecar_datetime - acq_datetime).total_seconds(),
        op.basename(json_file),
        (
            " -- `heudiconv --command populate-scans-duration --overwrite "
            "--fix-acq-time` would fix it"
            if fixable
            else ""
        ),
    )


def _find_bids_dataset_root(path: str) -> str | None:
    """Closest ancestor of `path` (or itself) with a ``dataset_description.json``."""
    for candidate in [Path(op.abspath(path)), *Path(op.abspath(path)).parents]:
        if (candidate / "dataset_description.json").exists():
            return str(candidate)
    return None


def _is_within(path: str, directory: str) -> bool:
    """Whether `path`, with symlinks resolved, is at or under `directory`."""
    return Path(op.realpath(path)).is_relative_to(op.realpath(directory))


def _extract_dicom_tarball(tarball: str, dest: str) -> list[str]:
    """Extract the regular files of `tarball` into `dest`, sorted by member name.

    They are stored under names of our own, so nothing depends on -- or
    needs vetting of -- the paths recorded in the archive.
    """
    extracted = []
    with tarfile.open(tarball) as tar:
        for i, member in enumerate(m for m in tar if m.isfile()):
            fn = op.join(dest, f"{i:06d}.dcm")
            src = tar.extractfile(member)
            assert src is not None  # it is a regular file
            with src, open(fn, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append((member.name, fn))
    return [fn for _, fn in sorted(extracted)]


def _duration_and_timestamps_from_dicom_tarball(
    tarball: str,
) -> tuple[float | None, list[datetime.datetime]]:
    """Acquisition duration and timestamps from a sourcedata DICOM tarball.

    See :func:`heudiconv.dicoms.compress_dicoms` for how it's produced.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        dicom_files = _extract_dicom_tarball(tarball, tmpdir)
        timestamps = dicoms.get_acquisition_timestamps(dicom_files)
        return dicoms.get_acquisition_duration(dicom_files, timestamps), timestamps


def _format_duration(duration: float | None) -> str:
    """Format a duration in seconds as a `_scans.tsv` cell (``'n/a'`` if None)."""
    return "%.3f" % duration if duration is not None else "n/a"


def _parse_bids_name(path: str) -> BIDSFile:
    """:meth:`BIDSFile.parse` also accepting a name with no entities, e.g. ``T1w.json``."""
    try:
        return BIDSFile.parse(op.basename(path))
    except ValueError:
        suffix, _, extension = op.basename(path).partition(".")
        return BIDSFile({}, suffix, extension or None)


def _find_json_sidecar(nifti_fn: str, bids_root: str) -> str | None:
    """Find the JSON sidecar applicable to `nifti_fn`.

    A same-named one right next to it if present, else -- per the `BIDS
    Inheritance Principle
    <https://bids-specification.readthedocs.io/en/stable/common-principles.html#the-inheritance-principle>`_
    -- the most-specific same-suffix ``.json`` (matching entities) found in
    an ancestor directory up to `bids_root`. None if neither exists.
    """
    exact = splitext_addext(nifti_fn)[0] + ".json"
    if op.exists(exact):
        return exact

    target = _parse_bids_name(nifti_fn)
    root = Path(op.realpath(bids_root))
    directory = Path(op.realpath(op.dirname(nifti_fn)))
    for current in [directory, *directory.parents]:
        if not current.is_relative_to(root):
            break
        candidates = [
            (len(candidate.entities), json_fn)
            for json_fn in sorted(glob(str(current / "*.json")))
            if (candidate := _parse_bids_name(json_fn)).suffix == target.suffix
            and all(target[k] == v for k, v in candidate.entities.items())
        ]
        if candidates:
            # most specific (most shared entities) match wins
            return max(candidates, key=lambda c: c[0])[1]
    return None


def _duration_from_volume_timing(meta: dict[str, Any], json_fn: str) -> float | None:
    """Duration per a sidecar's ``VolumeTiming``: its last onset plus one frame."""
    volume_timing = meta["VolumeTiming"]
    if not isinstance(volume_timing, list):
        return None
    try:
        onsets = sorted(float(t) for t in volume_timing)
    except (TypeError, ValueError):
        return None
    if not onsets:
        return None
    frame_duration = as_finite_positive_float(
        meta.get("FrameAcquisitionDuration")
    ) or as_finite_positive_float(meta.get("AcquisitionDuration"))
    if frame_duration is None:
        if as_finite_positive_float(meta.get("RepetitionTime")) is not None:
            lgr.warning(
                "%s has both RepetitionTime and VolumeTiming, which BIDS "
                "treats as mutually exclusive; not guessing a duration from "
                "this inconsistent metadata",
                json_fn,
            )
            return None
        if len(onsets) < 2:
            return None
        frame_duration = median_step(onsets)
    return onsets[-1] + frame_duration


def _duration_from_nifti_sidecar(nifti_fn: str, bids_root: str) -> float | None:
    """Estimate a run's duration from its NIfTI + JSON sidecar.

    The sidecar (see :func:`_find_json_sidecar`) gives it via
    ``VolumeTiming`` or ``AcquisitionDuration``, or else it is TR x volumes.
    Unlike with DICOMs (:func:`heudiconv.dicoms.get_acquisition_duration`)
    there are no timestamps to tell by whether ``AcquisitionDuration`` is of
    a truncated run, TR x volumes being no measure for many a sequence.
    """
    json_fn = _find_json_sidecar(nifti_fn, bids_root)
    if json_fn is None:
        return None
    try:
        meta = load_json(json_fn)
        if not isinstance(meta, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError) as exc:
        lgr.warning("Failed to load %s to get acquisition duration: %s", json_fn, exc)
        return None
    if "VolumeTiming" in meta:
        return _duration_from_volume_timing(meta, json_fn)

    duration = as_finite_positive_float(meta.get("AcquisitionDuration"))
    tr = as_finite_positive_float(meta.get("RepetitionTime"))
    if duration is not None or tr is None:
        return duration
    try:
        shape = nb.load(nifti_fn).shape  # type: ignore[attr-defined]
    except Exception as exc:
        # arbitrary, possibly corrupted or truncated, user data
        lgr.warning("Failed to load %s to get the number of volumes: %s", nifti_fn, exc)
        return None
    # TR x 1 vastly underestimates e.g. an anatomical, so we do not guess
    return tr * shape[3] if len(shape) > 3 and shape[3] > 1 else None


def _find_sourcedata_tarball(nifti_fn: str, bids_root: str) -> tuple[str | None, bool]:
    """Find the heudiconv-produced sourcedata DICOM tarball for `nifti_fn`.

    Returns it (None if not found), and whether it is shared by all outputs
    of a multi-output item (e.g. ``echo-``, ``magnitude1``/``2``), i.e.
    named after the item rather than after `nifti_fn` itself.
    """
    rel = op.relpath(nifti_fn, bids_root)
    sourcedata_dir = op.join(bids_root, "sourcedata", op.dirname(rel))
    stem = splitext_addext(op.basename(rel))[0]
    exact = op.join(sourcedata_dir, stem + ".dicom.tgz")
    if op.exists(exact):
        return exact, False
    # the longest prefix of `stem` without the entities heudiconv inserts to
    # tell apart the outputs of an item
    item_stem = re.sub(r"_(echo|part|ch|chunk)-[a-zA-Z0-9]+", "", stem)
    candidates = [
        p
        for p in glob(op.join(sourcedata_dir, "*.dicom.tgz"))
        if item_stem.startswith(op.basename(p)[: -len(".dicom.tgz")])
    ]
    return (max(candidates, key=len), True) if candidates else (None, False)


_TarballCache = dict[str, tuple[float | None, list[datetime.datetime]]]


def _get_retrospective_duration(
    nifti_fn: str, bids_root: str, tarballs: _TarballCache
) -> tuple[float | None, list[datetime.datetime], bool]:
    """Best-effort duration of an already-converted scan, and its DICOM timestamps.

    From the sourcedata DICOM tarball (see :func:`_find_sourcedata_tarball`,
    which also gives the returned "shared" flag) or, without timestamps
    then, from the NIfTI + JSON sidecar.  `tarballs` caches what was read
    from each tarball, which the outputs of a multi-output item share.
    """
    tarball, shared = _find_sourcedata_tarball(nifti_fn, bids_root)
    if tarball is not None:
        if tarball not in tarballs:
            try:
                tarballs[tarball] = _duration_and_timestamps_from_dicom_tarball(tarball)
            except Exception as exc:
                # a corrupt archive or DICOM within -- resort to the sidecar
                lgr.warning("Failed to read source DICOMs from %s: %s", tarball, exc)
                tarballs[tarball] = None, []
        duration, timestamps = tarballs[tarball]
        if duration is not None:
            return duration, timestamps, shared
        lgr.debug("No duration from source DICOMs %s for %s", tarball, nifti_fn)
    return _duration_from_nifti_sidecar(nifti_fn, bids_root), [], False


def populate_scans_duration(
    path: str, overwrite: bool = False, fix_acq_time: bool = False
) -> None:
    """Retrospectively populate the 'duration' column of `_scans.tsv` file(s).

    For datasets converted before conversion started to populate it (see
    :func:`get_formatted_scans_key_row`).

    Parameters
    ----------
    path: str
        A ``*_scans.tsv`` file, or a directory to look for them under.
    overwrite: bool, optional
        Also recompute `duration` of rows which already have one.  A value
        which cannot be re-established is kept.
    fix_acq_time: bool, optional
        Whether to replace `acq_time` of the rows (re)computed with the
        earliest acquisition timestamp of the source DICOMs where they
        disagree (https://github.com/nipy/heudiconv/issues/876), and
        likewise `AcquisitionTime` of the scan's own JSON sidecar where
        unambiguous (see :func:`check_acq_time_congruency`).  A disagreement
        is warned about regardless.
    """
    if op.isfile(path):
        scans_tsvs = [path] if path.endswith("_scans.tsv") else []
    else:
        scans_tsvs = sorted(
            find_files(r".*_scans\.tsv$", topdir=path, exclude_vcs=True)
        )
    if not scans_tsvs:
        lgr.warning("No '*_scans.tsv' files found under %s", path)
        return
    for scans_tsv in scans_tsvs:
        try:
            _populate_scans_duration_file(scans_tsv, overwrite, fix_acq_time)
        except Exception as exc:
            # one malformed file must not abort the rest of the dataset
            lgr.error("Failed to populate 'duration' in %s: %s", scans_tsv, exc)


def _populate_scans_duration_file(
    scans_tsv: str, overwrite: bool, fix_acq_time: bool = False
) -> None:
    """Backfill the 'duration' column of a single ``_scans.tsv`` file, in place."""
    session_dir = op.dirname(scans_tsv)
    bids_root = _find_bids_dataset_root(session_dir)
    if bids_root is None:
        raise ValueError(
            "it is not within a BIDS dataset (no dataset_description.json)"
        )
    fieldnames, rows = _read_scans_tsv(scans_tsv)
    if "filename" not in fieldnames:
        raise ValueError("it has no 'filename' column")

    # a legacy file gains the column (and scans.json its description below)
    # even if there is nothing to compute, e.g. no rows
    changed = "duration" not in fieldnames
    if changed:
        fieldnames = _merge_scans_header(
            fieldnames, ["filename", "acq_time", "duration"]
        )
    tarballs: _TarballCache = {}
    for row in rows:
        filename = row["filename"]
        if not filename:
            lgr.warning("%s has a row with no filename, skipping it", scans_tsv)
        elif maybe_na(row.get("duration")) != "n/a" and not overwrite:
            pass
        elif not _is_within(op.join(session_dir, filename), bids_root):
            lgr.warning(
                "Refusing %r in %s: resolves outside of the dataset (%s)",
                filename,
                scans_tsv,
                bids_root,
            )
        else:
            before = dict(row)
            try:
                _populate_scans_duration_row(
                    row,
                    op.join(session_dir, filename),
                    bids_root,
                    fix_acq_time,
                    tarballs,
                )
            except Exception as exc:
                # e.g. a malformed sidecar must not get in the way of the
                # other rows, nor of recording what was done to this one
                lgr.warning("Failed to process %s: %s", filename, exc)
            changed |= row != before

    if changed:
        _write_scans_tsv(scans_tsv, fieldnames, rows)
        lgr.info("Updated 'duration' column in %s", scans_tsv)
    else:
        lgr.info("No new 'duration' values could be established for %s", scans_tsv)
    _ensure_scans_json(op.join(bids_root, "scans.json"))


def _populate_scans_duration_row(
    row: _ScansRow,
    nifti_fn: str,
    bids_root: str,
    fix_acq_time: bool,
    tarballs: _TarballCache,
) -> None:
    """Update `duration` of `row`, and check (or fix) the acquisition times."""
    duration, timestamps, shared_tarball = _get_retrospective_duration(
        nifti_fn, bids_root, tarballs
    )
    # keep a value which we could not re-establish
    row["duration"] = (
        maybe_na(row.get("duration"))
        if duration is None
        else _format_duration(duration)
    )
    acq_datetime = _reconcile_acq_time(row, min(timestamps, default=None), fix_acq_time)
    json_fn = _find_json_sidecar(nifti_fn, bids_root)
    # never touch (or suggest fixing) an inherited sidecar, which is shared
    # with other scans, nor one of an output of a multi-output item, whose
    # sidecars may legitimately differ (e.g. localizer planes) -- only
    # conversion sees all of them together
    own_sidecar = (
        json_fn == splitext_addext(nifti_fn)[0] + ".json" and not shared_tarball
    )
    check_acq_time_congruency(
        acq_datetime,
        [json_fn] if json_fn else [],
        label=str(row["filename"]),
        timestamps=timestamps if own_sidecar else (),
        fix=fix_acq_time and own_sidecar,
    )


def _reconcile_acq_time(
    row: _ScansRow, earliest: datetime.datetime | None, fix: bool
) -> datetime.datetime | None:
    """Warn if `acq_time` of `row` is not `earliest`, replacing it if `fix`.

    Returns the resulting `acq_time`, None if `row` has no parseable one.
    A gap suggesting deliberately shifted dates (anonymization), which
    fixing would undo, is left alone.
    """
    try:
        stored = strptime_bids(row.get("acq_time") or "")
    except ValueError:
        return None
    if earliest is None:
        return stored
    # keep the stored value's timezone style (naive/aware)
    earliest, comparable = naive_if_mixed_tz([earliest, stored])
    gap = earliest - comparable
    if abs(gap) <= ACQ_TIME_TOLERANCE:
        return stored
    if abs(gap) > ACQ_TIME_DATE_SHIFT_THRESHOLD:
        fix = False
        status = "looks anonymized/date-shifted, not fixing"
    else:
        status = "fixing" if fix else "not fixed -- pass --fix-acq-time to"
    lgr.warning(
        "%s: stored acq_time %s differs from the earliest acquisition "
        "timestamp re-derived from its source DICOMs (%+.6f seconds; %s). "
        "See https://github.com/nipy/heudiconv/issues/876",
        row["filename"],
        stored.isoformat(),
        gap.total_seconds(),
        status,
    )
    if not fix:
        return stored
    row["acq_time"] = earliest.isoformat()
    return earliest


def convert_sid_bids(subject_id: str) -> str:
    """Shim for stripping any non-BIDS compliant characters within subject_id

    Parameters
    ----------
    subject_id : string

    Returns
    -------
    sid : string
        New subject ID
    """
    warnings.warn(
        "convert_sid_bids() is deprecated, please use sanitize_label() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return sanitize_label(subject_id)


def get_shim_setting(json_file: str) -> Any:
    """
    Gets the "ShimSetting" field from a json_file.
    If no "ShimSetting" present, return error

    Parameters
    ----------
    json_file : str

    Returns
    -------
    str with "ShimSetting" value
    """
    data = load_json(json_file)
    try:
        shims = data[SHIM_KEY]
    except KeyError:
        lgr.error(
            'File %s does not have "%s". '
            'Please use a different "matching_parameters" in your heuristic file',
            json_file,
            SHIM_KEY,
        )
        raise
    return shims


def find_fmap_groups(fmap_dir: str) -> dict[str, list[str]]:
    """
    Finds the different fmap groups in a fmap directory.
    By groups here we mean fmaps that are intended to go together
    (with reversed PE polarity, magnitude/phase, etc.)

    Parameters
    ----------
    fmap_dir : str
        path to the session folder (or to the subject folder, if there are no
        sessions).

    Returns
    -------
    fmap_groups : dict
        key: prefix common to the group (e.g. no "dir" entity, "_phase"/"_magnitude", ...)
        value: list of all fmap paths in the group
    """
    if op.basename(fmap_dir) != "fmap":
        lgr.error("%s is not a fieldmap folder", fmap_dir)

    # Get a list of all fmap json files in the session:
    fmap_jsons = sorted(glob(op.join(fmap_dir, "*.json")))

    # RegEx to remove fmap-specific substrings from fmap file names
    # "_phase[1,2]", "_magnitude[1,2]", "_phasediff", "_dir-<label>", ...
    fmap_regex = re.compile(
        "(_dir-[0-9,a-z,A-Z]*)*"  # for pepolar case
        "(_phase[12])*"  # for phase images
        "(_phasediff)*"  # for phasediff images
        "(_magnitude[12])*"  # for magnitude images
        "(_fieldmap)*"  # for actual fieldmap images
    )

    # Find the unique prefixes ('splitext' removes the extension):
    prefixes = sorted(
        set(
            fmap_regex.sub("", remove_suffix(op.basename(fm), ".json"))
            for fm in fmap_jsons
        )
    )
    return {
        k: [
            fm
            for fm in fmap_jsons
            if fmap_regex.sub("", remove_suffix(op.basename(fm), ".json")) == k
        ]
        for k in prefixes
    }


def get_key_info_for_fmap_assignment(
    json_file: str, matching_parameter: str
) -> list[Any]:
    """
    Gets key information needed to assign fmaps to other modalities.
    (Note: It is the responsibility of the calling function to make sure
    the arguments are OK)

    Parameters
    ----------
    json_file : str
        path to the json file
    matching_parameter : str in AllowedFmapParameterMatching
        matching_parameter that will be used to match runs

    Returns
    -------
    key_info : list
        part of the json file that will need to match between the fmap and
        the other image
    """
    if not op.exists(json_file):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), json_file)

    # loop through the possible criteria and extract the info needed
    if matching_parameter == "Shims":
        key_info = [get_shim_setting(json_file)]
    elif matching_parameter == "ImagingVolume":
        from nibabel import load as nb_load
        from nibabel.nifti1 import Nifti1Header

        nifti_files = glob(remove_suffix(json_file, ".json") + ".nii*")
        assert len(nifti_files) == 1
        nifti_file = nifti_files[0]
        nifti_header = nb_load(nifti_file).header
        assert isinstance(nifti_header, Nifti1Header)
        key_info = [nifti_header.get_best_affine(), nifti_header.get_data_shape()[:3]]
    elif matching_parameter == "ModalityAcquisitionLabel":
        # Check the acq label for the fmap and the modality for others:
        modality = op.basename(op.dirname(json_file))
        if modality == "fmap":
            # extract the <acq> entity:
            acq_label = BIDSFile.parse(op.basename(json_file))["acq"]
            assert acq_label is not None
            if any(s in acq_label.lower() for s in ["fmri", "bold", "func"]):
                key_info = ["func"]
            elif any(s in acq_label.lower() for s in ["diff", "dwi"]):
                key_info = ["dwi"]
            elif any(s in acq_label.lower() for s in ["anat", "struct"]):
                key_info = ["anat"]
        else:
            key_info = [modality]
    elif matching_parameter == "CustomAcquisitionLabel":
        modality = op.basename(op.dirname(json_file))
        if modality == "func":
            # extract the <task> entity:
            custom_label = BIDSFile.parse(op.basename(json_file))["task"]
        else:
            # extract the <acq> entity:
            custom_label = BIDSFile.parse(op.basename(json_file))["acq"]
        # Get the custom acquisition label, acq_label is None if no custom field found
        key_info = [custom_label]
    elif matching_parameter == "PlainAcquisitionLabel":
        # always base the decision on <acq> label
        plain_label = BIDSFile.parse(op.basename(json_file))["acq"]
        key_info = [plain_label]
    elif matching_parameter == "Force":
        # We want to force the matching, so just return some string
        # regardless of the image
        key_info = [KeyInfoForForce]
    else:
        # fallback:
        key_info = []

    return key_info


def find_compatible_fmaps_for_run(
    json_file: str, fmap_groups: dict[str, list[str]], matching_parameters: list[str]
) -> dict[str, list[str]]:
    """
    Finds compatible fmaps for a given run, for populate_intended_for.
    (Note: It is the responsibility of the calling function to make sure
    the arguments are OK)

    Parameters
    ----------
    json_file : str
        path to the json file
    fmap_groups : dict
        key: prefix common to the group
        value: list of all fmap paths in the group
    matching_parameters : list of str from AllowedFmapParameterMatching
        matching_parameters that will be used to match runs

    Returns
    -------
    compatible_fmap_groups : dict
        Subset of the fmap_groups which match json_file, according
        to the matching_parameters.
        key: prefix common to the group
        value: list of all fmap paths in the group
    """
    lgr.debug("Looking for fmaps for %s", json_file)
    json_info = {}
    for param in matching_parameters:
        json_info[param] = get_key_info_for_fmap_assignment(json_file, param)

    compatible_fmap_groups = {}
    for fm_key, fm_group in fmap_groups.items():
        # check the key_info (for all parameters) for one (the first) of
        # the fmaps in the group:
        compatible = False
        for param in matching_parameters:
            json_info_1st_item = json_info[param][0]
            fm_info = get_key_info_for_fmap_assignment(fm_group[0], param)
            # for the case in which key_info is a list of strings:
            if isinstance(json_info_1st_item, str):
                compatible = json_info[param] == fm_info
            # for the case when no key info was found (e.g. "acq" field does not exist)
            elif json_info_1st_item is None:
                compatible = False
            else:
                # allow for tiny differences between the affines etc
                compatible = all(
                    # allow for small up to 5% difference
                    np.allclose(x, y, rtol=0.05)
                    for x, y in zip(json_info[param], fm_info)
                )
            if not compatible:
                break  # don't bother checking more params
        if compatible:
            compatible_fmap_groups[fm_key] = fm_group

    return compatible_fmap_groups


def find_compatible_fmaps_for_session(
    path_to_bids_session: str, matching_parameters: list[str]
) -> dict[str, dict[str, list[str]]] | None:
    """
    Finds compatible fmaps for all non-fmap runs in a session.
    (Note: It is the responsibility of the calling function to make sure
    the arguments are OK)

    Parameters
    ----------
    path_to_bids_session : str
        path to the session folder (or to the subject folder, if there are no
        sessions).
    matching_parameters : list of str from AllowedFmapParameterMatching
        matching_parameters that will be used to match runs

    Returns
    -------
    compatible_fmap : dict
        Dict of compatible_fmaps_groups (values) for each non-fmap run (keys)
    """
    lgr.debug("Looking for fmaps for session: %s", path_to_bids_session)

    # Resolve path (eliminate '..')
    path_to_bids_session = op.abspath(path_to_bids_session)

    # find the different groups of fmaps:
    fmap_dir = op.join(path_to_bids_session, "fmap")
    if not op.exists(fmap_dir):
        lgr.warning(
            "We cannot add the IntendedFor field: no fmap/ in %s", path_to_bids_session
        )
        return None
    fmap_groups = find_fmap_groups(fmap_dir)

    # Get a set with all non-fmap json files in the session (exclude SBRef files).
    session_jsons = [
        j
        for j in glob(op.join(path_to_bids_session, "*/*.json"))
        if not (
            op.basename(op.dirname(j)) == "fmap"
            or remove_suffix(j, ".json").endswith("_sbref")
        )
    ]

    # Loop through session_jsons and find the compatible fmap_groups for each
    compatible_fmaps = {
        j: find_compatible_fmaps_for_run(j, fmap_groups, matching_parameters)
        for j in session_jsons
    }
    return compatible_fmaps


def select_fmap_from_compatible_groups(
    json_file: str, compatible_fmap_groups: dict[str, list[str]], criterion: str
) -> str | None:
    """
    Selects the fmap that will be used to correct for distortions in json_file
    from the compatible fmap_groups list, based on the given criterion
    (Note: It is the responsibility of the calling function to make sure
    the arguments are OK)

    Parameters
    ----------
    json_file : str
        path to the json file
    compatible_fmap_groups : dict
        fmap_groups that are compatible with the specific json_file
    criterion : str in ['First', 'Closest']
        matching_parameters that will be used to decide which fmap to use

    Returns
    -------
    selected_fmap_key : str
        key from the compatible_fmap_groups for the selected fmap group
    """
    if len(compatible_fmap_groups) == 0:
        return None
    # if compatible_fmap_groups has only one entry, that's it:
    elif len(compatible_fmap_groups) == 1:
        return list(compatible_fmap_groups.keys())[0]

    # get the modality folders, then session folder:
    modality_folders = set(
        op.dirname(fmap) for v in compatible_fmap_groups.values() for fmap in v
    )  # there should be only one value, ending in 'fmap'
    sess_folders = set(op.dirname(k) for k in modality_folders)
    if len(sess_folders) > 1:
        # for now, we only deal with single sessions:
        raise RuntimeError
    # if we made it here, we have only one session:
    sess_folder = list(sess_folders)[0]

    # get acquisition times from '_scans.tsv':
    try:
        scans_tsv = glob(op.join(sess_folder, "*_scans.tsv"))[0]
    except IndexError:
        raise FileNotFoundError("No '*_scans' file found for session %s" % sess_folder)
    _, scans_rows = _read_scans_tsv(scans_tsv)
    acq_times = {row.get("filename"): row.get("acq_time") or "" for row in scans_rows}
    # acq_times for the compatible fmaps:
    acq_times_fmaps = {
        k: acq_times[
            # remove session folder and '.json', add '.nii.gz':
            remove_suffix(remove_prefix(v[0], sess_folder + op.sep), ".json")
            + ".nii.gz"
        ]
        for k, v in compatible_fmap_groups.items()
    }

    if criterion == "First":
        # find the first acquired fmap_group from the compatible_fmap_groups:
        first_acq_time = sorted(acq_times_fmaps.values())[0]
        selected_fmap_key = [
            k for k, v in acq_times_fmaps.items() if v == first_acq_time
        ][0]
    elif criterion == "Closest":
        json_acq_time = strptime_bids(
            acq_times[
                # remove session folder and '.json', add '.nii.gz':
                remove_suffix(remove_prefix(json_file, sess_folder + op.sep), ".json")
                + ".nii.gz"
            ]
        )
        # differences in acquisition time (abs value):
        diff_fmaps_acq_times = {
            k: abs(strptime_bids(v) - json_acq_time) for k, v in acq_times_fmaps.items()
        }
        min_diff_acq_times = sorted(diff_fmaps_acq_times.values())[0]
        selected_fmap_key = [
            k for k, v in diff_fmaps_acq_times.items() if v == min_diff_acq_times
        ][0]
    else:
        raise ValueError(f"Invalid 'criterion' value: {criterion!r}")

    return selected_fmap_key


def populate_intended_for(
    path_to_bids_session: str, matching_parameters: str | list[str], criterion: str
) -> None:
    """
    Adds the 'IntendedFor' field to the fmap .json files in a session folder.
    It goes through the session folders and for every json file, it finds
    compatible_fmaps: fmaps that have the same matching_parameters as the json
    file (e.g., same 'Shims').

    If there are more than one compatible_fmaps, it will use the criterion
    specified by the user (default: 'Closest' in time).

    Because fmaps come in groups (with reversed PE polarity, or magnitude/
    phase), we work with fmap_groups.

    Parameters
    ----------
    path_to_bids_session : str
        path to the session folder (or to the subject folder, if there are no
        sessions).
    matching_parameters : list of str from AllowedFmapParameterMatching
        matching_parameters that will be used to match runs
    criterion : str in ['First', 'Closest']
        matching_parameters that will be used to decide which of the matching
        fmaps to use
    """

    if not isinstance(matching_parameters, list):
        assert isinstance(matching_parameters, str), (
            "matching_parameters must be a str or a list, got %s" % matching_parameters
        )
        matching_parameters = [matching_parameters]
    for param in matching_parameters:
        if param not in AllowedFmapParameterMatching:
            raise ValueError("Fmap matching_parameter %s not allowed." % param)
    if criterion not in AllowedCriteriaForFmapAssignment:
        raise ValueError("Fmap assignment criterion '%s' not allowed." % criterion)

    lgr.info('Adding "IntendedFor" to the fieldmaps in %s.', path_to_bids_session)

    # Resolve path (eliminate '..')
    path_to_bids_session = op.abspath(path_to_bids_session)

    # Get the subject folder (if "path_to_bids_session" includes the session,
    # remove it). "IntendedFor" paths will be relative to it.
    if op.basename(path_to_bids_session).startswith("ses-"):
        subj_folder = op.dirname(path_to_bids_session)
    else:
        subj_folder = path_to_bids_session

    fmap_dir = op.join(path_to_bids_session, "fmap")
    if not op.exists(fmap_dir):
        lgr.warning(
            "We cannot add the IntendedFor field: no fmap/ in %s", path_to_bids_session
        )
        return

    compatible_fmaps = find_compatible_fmaps_for_session(
        path_to_bids_session, matching_parameters=matching_parameters
    )
    assert compatible_fmaps is not None
    selected_fmaps = {}
    for json_file, fmap_groups in compatible_fmaps.items():
        if not op.dirname(json_file).endswith("fmap"):
            selected_fmaps[json_file] = select_fmap_from_compatible_groups(
                json_file, fmap_groups, criterion=criterion
            )

    # Loop through all the unique fmap_groups in compatible_fmaps:
    unique_fmap_groups = {}
    for cf in compatible_fmaps.values():
        for key, values in cf.items():
            if key not in unique_fmap_groups:
                unique_fmap_groups[key] = values

    for fmap_group in unique_fmap_groups:
        intended_for = []
        for json_file, selected_fmap_group in selected_fmaps.items():
            if selected_fmap_group and (fmap_group in selected_fmap_group):
                intended_for.append(
                    op.relpath(
                        remove_suffix(json_file, ".json") + ".nii.gz", start=subj_folder
                    )
                )
        if intended_for:
            intended_for = sorted(str(f) for f in intended_for)
            # Add this intended_for to all fmap files in the fmap_group:
            for fm_json in unique_fmap_groups[fmap_group]:
                update_json(fm_json, {"IntendedFor": intended_for}, pretty=True)


class BIDSFile:
    """as defined in https://bids-specification.readthedocs.io/en/stable/99-appendices/04-entity-table.html
    which might soon become machine readable
    order matters
    """

    # The full list of entities, in the order mandated by the BIDS entity table
    # (``rules/entities.yaml`` of the BIDS schema).  Entities we do not produce
    # ourselves are listed as well, so that a filename which carries them (e.g.
    # coming from a heuristic) survives a parse/serialize round-trip in the
    # right order.
    _known_entities = [
        "sub",
        "tpl",
        "ses",
        "cohort",
        "sample",
        "task",
        "tracksys",
        "acq",
        "nuc",
        "voi",
        "ce",
        "trc",
        "stain",
        "rec",
        "dir",
        "run",
        "mod",
        "echo",
        "flip",
        "inv",
        "mt",
        "part",
        # not a BIDS entity: heudiconv's own, for uncombined multi-channel data.
        # Kept at the position update_uncombined_name() places it at.
        "ch",
        "proc",
        "hemi",
        "space",
        "split",
        "recording",
        "chunk",
        "atlas",
        "seg",
        "scale",
        "res",
        "den",
        "label",
        "desc",
    ]

    def __init__(
        self, entities: dict[str, str], suffix: str, extension: str | None
    ) -> None:
        self._entities = entities
        self._suffix = suffix
        self._extension = extension

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        if (
            all([other[k] == v for k, v in self._entities.items()])
            and self.extension == other.extension
            and self.suffix == other.suffix
        ):
            return True
        else:
            return False

    @classmethod
    def parse(cls, filename: str) -> BIDSFile:
        """Parse the filename for BIDS entities, suffix and extension

        Raises
        ------
        ValueError
            If no ``key-value`` pair could be found at all, i.e. the name is
            not a BIDS one.
        """
        # Entities are the leading run of '_'-separated lower-case-letters + '-' +
        # value pairs; everything after it is the suffix (+ extension).  Matching
        # the run as a whole, rather than every such pair anywhere in the name,
        # keeps us from mistaking a part of the suffix for an entity: reproin
        # marks duplicate series with a trailing '__dup-01', and a 'T1w-mod'
        # suffix contains a 'w-mod' pair.  Values are not restricted to
        # alphanumerics, so that a non-compliant label coming from a heuristic
        # (e.g. 'task-rest-state') does not hide all the entities after it.
        match = re.match(r"((?:[a-z]+-[^_.]+_)*[a-z]+-[^_.]+)(?=_|\.|$)", filename)
        if not match:
            raise ValueError(f"No BIDS entities found in {filename!r}")
        # keep all of them: dropping the ones we do not know about would silently
        # lose information from the filename (see __str__, which puts the unknown
        # ones back at the end).
        entities = {
            k: v for k, v in (e.split("-", 1) for e in match.group(1).split("_"))
        }
        # get whatever comes after the entities, and remove any '_' that
        # might come in front:
        ending = remove_prefix(filename[match.end() :], "_")
        # the first dot ('.') separates the suffix from the extension:
        if "." in ending:
            suffix, extension = ending.split(".", 1)
        else:
            suffix, extension = ending, None
        return BIDSFile(entities, suffix, extension)

    def __str__(self) -> str:
        """reconstitute in a legit BIDS filename using the order from entity table"""
        if "sub" not in self._entities:
            raise ValueError("The 'sub-' entity is mandatory")
        # reconstitute the ending for the filename:
        suffix = "_" + self.suffix if self.suffix else ""
        extension = "." + self.extension if self.extension else ""
        ordered = [e for e in self._known_entities if e in self._entities]
        # entities we do not know about cannot be placed within the entity table
        # order, so keep them (in the order they were given) right before the
        # suffix rather than dropping them on the floor
        unknown = [e for e in self._entities if e not in self._known_entities]
        out = (
            "_".join(["-".join([e, self._entities[e]]) for e in ordered + unknown])
            + suffix
            + extension
        )
        if unknown:
            lgr.warning(
                "Unknown BIDS entities (%s) in %s: keeping them, but their "
                "placement within the filename might not be BIDS-compliant.",
                ", ".join(unknown),
                out,
            )
        return out

    def __getitem__(self, entity: str) -> str | None:
        return self._entities[entity] if entity in self._entities else None

    def __setitem__(
        self, entity: str, value: str
    ) -> None:  # would puke with some exception if already known
        return self.set(entity, value, overwrite=False)

    def __contains__(self, entity: object) -> bool:
        return entity in self._entities

    def drop(self, entity: str, missing_ok: bool = False) -> None:
        if entity not in self._entities:
            if not missing_ok:
                raise ValueError(f"{self} does not contain entity {entity!r}")
            return
        self._entities.pop(entity)

    def set(self, entity: str, value: str, overwrite: bool = True) -> None:
        if entity not in self._entities:
            # just set it; no complains here
            self._entities[entity] = value
        elif overwrite:
            lgr.warning(
                "Overwriting the entity %s from %s to %s for file %s",
                str(entity),
                str(self[entity]),
                str(value),
                self.__str__(),
            )
            self._entities[entity] = value
        else:
            # if it already exists, and overwrite is false:
            lgr.warning(
                "Setting the entity %s to %s for file %s failed",
                str(entity),
                str(value),
                self.__str__(),
            )

    @property  # as needed make them RW
    def suffix(self) -> str:
        return self._suffix

    @property
    def extension(self) -> str | None:
        return self._extension

    @property
    def entities(self) -> dict[str, str]:
        return dict(self._entities)


def sanitize_label(label: str) -> str:
    """Strips any non-BIDS compliant characters within label

    Parameters
    ----------
    label : string

    Returns
    -------
    clean_label : string
        New, sanitized label
    """
    clean_label = "".join(x for x in label if x.isalnum())
    if not clean_label:
        raise ValueError(
            "Label became empty after cleanup.  Please manually provide "
            "a suitable alphanumeric label."
        )
    if clean_label != label:
        lgr.warning(
            "%r label contained non-alphanumeric character(s), it "
            "was cleaned to be %r",
            label,
            clean_label,
        )
    return clean_label
