"""Handle BIDS specific operations"""

from __future__ import annotations

__docformat__ = "numpy"

from collections import OrderedDict
from collections.abc import Sequence
import csv
import errno
from glob import glob
import hashlib
import logging
import os
import os.path as op
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Optional
import warnings

import numpy as np
import pydicom as dcm

from . import __version__, dicoms
from .parser import find_files
from .utils import (
    as_finite_positive_float,
    create_file_if_missing,
    is_readonly,
    json_dumps,
    load_json,
    remove_prefix,
    remove_suffix,
    safe_extract_tar,
    save_json,
    set_readonly,
    strptime_bids,
    update_json,
)

lgr = logging.getLogger(__name__)

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


def populate_bids_templates(
    path: str, defaults: Optional[dict[str, Any]] = None
) -> None:
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
    scans_json = op.join(path, "scans.json")
    create_file_if_missing(scans_json, json_dumps(SCANS_FILE_FIELDS, sort_keys=False))
    # an existing scans.json (e.g. from before "duration" was introduced)
    # is left alone by create_file_if_missing above -- bring it up to date
    # with any SCANS_FILE_FIELDS key it is missing, without touching
    # anything else (including a user's own additions)
    _sync_scans_json_fields(scans_json)
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
        if "_echo-" in fpath:
            # multi-echo sequence: bids (1.1.0) specifies just one '_events.tsv'
            #   file, common for all echoes.  The name will not include _echo-.
            # TODO: RF to use re.match for better readability/robustness
            # So, find out the echo number:
            fpath_split = fpath.split("_echo-", 1)  # split fpath using '_echo-'
            fpath_split_2 = fpath_split[1].split(
                "_", 1
            )  # split the second part of fpath_split using '_'
            echoNo = fpath_split_2[0]  # get echo number
            if echoNo == "1":
                if len(fpath_split_2) != 2:
                    raise ValueError("Found no trailer after _echo-")
                # we modify fpath to exclude '_echo-' + echoNo:
                fpath = fpath_split[0] + "_" + fpath_split_2[1]
            else:
                # for echoNo greater than 1, don't create the events file, so go to
                #   the next for loop iteration:
                continue

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
        save_json(jsonfile, json_)

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
            was_readonly = is_readonly(json_phasediffname)
            if was_readonly:
                set_readonly(json_phasediffname, False)
            save_json(json_phasediffname, json_)
            if was_readonly:
                set_readonly(json_phasediffname)


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


def find_subj_ses(f_name: str) -> tuple[Optional[str], Optional[str]]:
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
    subj: Optional[str] = None
    ses: Optional[str] = None
    # all bids_files of this item share the same source DICOMs, so the row
    # (including the possibly-expensive `duration` estimation) is the same
    # for every one of them -- compute it once rather than per file
    scan_key_row = get_formatted_scans_key_row(item[-1])
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
    # where should we store it?
    output_dir = op.dirname(op.dirname(bids_file))
    # save
    ses = "_ses-%s" % ses if ses else ""
    add_rows_to_scans_keys_file(
        op.join(output_dir, "sub-{0}{1}_scans.tsv".format(subj, ses)), rows
    )


def _sync_scans_json_fields(scans_json: str) -> None:
    """Ensure an existing ``scans.json`` documents every ``SCANS_FILE_FIELDS`` key.

    Adds whichever of ``SCANS_FILE_FIELDS`` (e.g. "duration", for a
    ``scans.json`` predating this feature) are missing from `scans_json`,
    leaving every other key -- including any dataset-specific ones a user
    added -- untouched. A no-op if `scans_json` does not exist; creating
    it from scratch is :func:`populate_bids_templates`'s job.

    Parameters
    ----------
    scans_json : str
        Path to the dataset's ``scans.json`` data dictionary.
    """
    if not op.lexists(scans_json):
        return
    meta = load_json(scans_json)
    missing = {k: v for k, v in SCANS_FILE_FIELDS.items() if k not in meta}
    if missing:
        meta.update(missing)
        save_json(scans_json, meta, sort_keys=False)


def _merge_scans_header(existing_header: list[str], additions: list[str]) -> list[str]:
    """Extend `existing_header` with whichever of `additions` it is missing.

    Every column already in `existing_header` is preserved, in its
    existing order and position -- including any dataset-specific columns
    beyond those heudiconv itself defines, since BIDS explicitly allows
    additional ``_scans.tsv`` columns. Each missing column from
    `additions` is inserted right after the nearest earlier column (within
    `additions`, in its given order) that is already present, so that
    e.g. a newly introduced "duration" lands next to "acq_time" rather
    than at a random position.

    Parameters
    ----------
    existing_header : list of str
        Header row of an existing ``_scans.tsv`` (or a header to start
        fresh from, e.g. ``list(SCANS_FILE_FIELDS.keys())``).
    additions : list of str
        Canonical columns to ensure are present, in their intended
        relative order -- e.g. ``list(SCANS_FILE_FIELDS.keys())``, or a
        smaller ordered subset such as ``["filename", "acq_time",
        "duration"]`` to place just "duration".

    Returns
    -------
    list of str
        `existing_header` with any missing `additions` columns inserted.
    """
    merged = list(existing_header)
    for i, column in enumerate(additions):
        if column in merged:
            continue
        insert_at = len(merged)
        for prev in reversed(additions[:i]):
            if prev in merged:
                insert_at = merged.index(prev) + 1
                break
        merged.insert(insert_at, column)
    return merged


def add_rows_to_scans_keys_file(fn: str, newrows: dict[str, list[str]]) -> None:
    """Add new rows to the _scans file.

    Parameters
    ----------
    fn: str
      filename
    newrows: dict
      extra rows to add (acquisition time, duration, referring physician,
      random string), in the order of ``SCANS_FILE_FIELDS`` (excluding
      "filename")
    """
    canonical = list(SCANS_FILE_FIELDS.keys())
    header = canonical
    if op.lexists(fn):
        with open(fn, "r") as csvfile:
            reader = csv.reader(csvfile, delimiter="\t")
            existing_rows = [row for row in reader]
        # Key each row's values by their *own* column name, not by
        # position: a file written by an older heudiconv version may have
        # fewer/differently-ordered columns (e.g. no "duration"), and
        # zipping those positionally against the current, wider header
        # would silently misassign values (e.g. "operator" ending up under
        # "duration").
        existing_header = existing_rows[0] if existing_rows else canonical
        # BIDS allows additional scan columns beyond the ones we define, so
        # keep any that are already there (e.g. user-added), only adding
        # whichever canonical ones (e.g. a newly introduced "duration")
        # the existing file lacks -- rather than rebuilding the header from
        # SCANS_FILE_FIELDS alone and silently dropping the rest.
        header = _merge_scans_header(existing_header, canonical)
        fnames2info = {
            row[0]: dict(zip(existing_header[1:], row[1:])) for row in existing_rows[1:]
        }

        newrows_key = newrows.keys()
        newrows_toadd = list(set(newrows_key) - set(fnames2info.keys()))
        for key_toadd in newrows_toadd:
            fnames2info[key_toadd] = dict(zip(canonical[1:], newrows[key_toadd]))
        # remove
        os.unlink(fn)
    else:
        fnames2info = {k: dict(zip(canonical[1:], v)) for k, v in newrows.items()}

    # prepare all the data rows, filling any column missing from a given
    # row (e.g. "duration" for a row carried over from an older file, or a
    # custom column only some rows had) with 'n/a' rather than shifting
    # the remaining columns into its place
    data_rows = [
        [filename] + [info.get(col, "n/a") for col in header[1:]]
        for filename, info in fnames2info.items()
    ]
    # sort by the date/filename
    try:
        data_rows_sorted = sorted(data_rows, key=lambda x: (x[1], x[0]))
    except TypeError as exc:
        lgr.warning("Sorting scans by date failed: %s", str(exc))
        data_rows_sorted = sorted(data_rows)
    # save
    with open(fn, "a") as csvfile:
        writer = csv.writer(csvfile, delimiter="\t")
        writer.writerows([header] + data_rows_sorted)


def get_formatted_scans_key_row(
    dcm_fns: str | Path | Sequence[str | Path],
) -> list[str]:
    """
    Parameters
    ----------
    dcm_fns: str or Path, or sequence of str or Path
        A single DICOM file representative of the run, or -- preferably --
        every DICOM file belonging to it.  Providing the full list allows
        `duration` to be estimated from per-file acquisition timestamps when
        no `AcquisitionDuration` tag is directly available; see
        :func:`heudiconv.dicoms.get_acquisition_duration`.

    Returns
    -------
    row: list
        [ISO acquisition time, duration in seconds (or 'n/a'), performing
        physician name, random string]

    """
    if isinstance(dcm_fns, (str, Path)):
        dcm_fns = [dcm_fns]
    dcm_fn_strs: list[str] = [str(f) for f in dcm_fns]
    dcm_data = dcm.dcmread(dcm_fn_strs[0], stop_before_pixels=True, force=True)
    # we need to store filenames and acquisition datetimes
    acq_datetime = dicoms.get_datetime_from_dcm(dcm_data=dcm_data)
    duration = dicoms.get_acquisition_duration(dcm_fn_strs)
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
        _format_duration(duration),
        perfphys,
        randstr,
    ]
    # empty entries should be 'n/a'
    # https://github.com/dartmouth-pbs/heudiconv/issues/32
    row = ["n/a" if not str(e) else e for e in row]
    return row


def _find_bids_dataset_root(path: str) -> str:
    """Find the BIDS dataset root, walking upward from `path`.

    Parameters
    ----------
    path : str
        Directory to start the search from (e.g., a subject or session
        folder).

    Returns
    -------
    str
        The closest ancestor of `path` (inclusive) containing a
        ``dataset_description.json``, or `path` itself (absolute) if no such
        ancestor could be found.
    """
    current = op.abspath(path)
    while True:
        if op.exists(op.join(current, "dataset_description.json")):
            return current
        parent = op.dirname(current)
        if parent == current:
            return op.abspath(path)
        current = parent


def _duration_from_dicom_tarball(tarball: str) -> Optional[float]:
    """Compute acquisition duration from a heudiconv-produced DICOM tarball.

    Parameters
    ----------
    tarball : str
        Path to a ``*.dicom.tgz`` file, as produced under ``sourcedata/`` by
        heudiconv's ``-c dicom`` conversion (see
        :func:`heudiconv.dicoms.compress_dicoms`).

    Returns
    -------
    Optional[float]
        Duration in seconds, or None if it could not be determined.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        safe_extract_tar(tarball, tmpdir)
        dicom_files = sorted(str(p) for p in Path(tmpdir).rglob("*") if p.is_file())
        if not dicom_files:
            lgr.warning("No files found within %s", tarball)
            return None
        return dicoms.get_acquisition_duration(dicom_files)


def _nifti_stem(nifti_fn: str) -> str:
    """Strip a NIfTI extension (``.nii`` or ``.nii.gz``) off `nifti_fn`."""
    return remove_suffix(remove_suffix(nifti_fn, ".gz"), ".nii")


def _format_duration(duration: Optional[float]) -> str:
    """Format a duration in seconds as a `_scans.tsv` cell (``'n/a'`` if None)."""
    return "%.3f" % duration if duration is not None else "n/a"


def _is_within_directory(path: str, directory: str) -> bool:
    """Return True if `path` resolves to somewhere at or under `directory`.

    Resolves symlinks (via `os.path.realpath`) on both sides, so a
    dataset-internal symlink that points outside `directory` is correctly
    treated as escaping it, rather than merely comparing lexical
    (unresolved) absolute paths.
    """
    path = op.realpath(path)
    directory = op.realpath(directory)
    return path == directory or path.startswith(directory + os.sep)


def _duration_from_nifti_sidecar(nifti_fn: str) -> Optional[float]:
    """Estimate a run's duration from its NIfTI + JSON sidecar.

    Prefers the sidecar's own ``AcquisitionDuration`` field when present
    and valid: per the BIDS `duration` proposal, that field is exactly
    what the `_scans.tsv` ``duration`` column represents for MRI data.
    The one exception is a sidecar carrying ``VolumeTiming`` (e.g. sparse
    or multiband BOLD/ASL designs): there, ``AcquisitionDuration`` (if any)
    describes per-volume timing rather than the whole run, so this falls
    through to the coarser estimate below instead.

    Otherwise, computes ``RepetitionTime`` (from the JSON sidecar) times
    the number of volumes (from the NIfTI header), which is only
    meaningful for multi-volume (e.g., functional) runs.  This is a
    coarse approximation: it cannot account for any preparation/dummy-scan
    time preceding the first recorded volume, so it is used only as a
    last resort, when no source DICOMs -- nor a usable
    ``AcquisitionDuration`` -- are available.

    Parameters
    ----------
    nifti_fn : str
        Path to the ``.nii``/``.nii.gz`` file. A same-named ``.json``
        sidecar is expected alongside it.

    Returns
    -------
    Optional[float]
        Duration in seconds, or None if it could not be determined.
    """
    json_fn = _nifti_stem(nifti_fn) + ".json"
    if not op.exists(json_fn):
        return None
    meta = load_json(json_fn)

    if "VolumeTiming" not in meta:
        duration = as_finite_positive_float(meta.get("AcquisitionDuration"))
        if duration is not None:
            return duration

    tr = as_finite_positive_float(meta.get("RepetitionTime"))
    if tr is None:
        return None
    try:
        from nibabel import load as nb_load

        shape = nb_load(nifti_fn).shape  # type: ignore[attr-defined]
    except Exception as exc:
        # nifti_fn is arbitrary, externally-produced (possibly corrupted or
        # truncated) user data, so we deliberately catch broadly here and
        # treat it as "could not determine", but do log at 'warning' since
        # -- unlike a missing sourcedata tarball -- this is a case we
        # otherwise expected to be able to measure
        lgr.warning("Failed to load %s to get the number of volumes: %s", nifti_fn, exc)
        return None
    nvols = shape[3] if len(shape) > 3 else 1
    if nvols <= 1:
        # a single-volume (e.g., anatomical) scan -- TR x 1 vastly
        # underestimates its actual acquisition time, so we do not guess
        return None
    return tr * nvols


def _get_retrospective_duration(nifti_fn: str, bids_root: str) -> Optional[float]:
    """Best-effort acquisition duration for an already-converted BIDS scan.

    Parameters
    ----------
    nifti_fn : str
        Path to the converted ``.nii``/``.nii.gz`` file.
    bids_root : str
        Path to the root of the BIDS dataset `nifti_fn` belongs to.

    Returns
    -------
    Optional[float]
        Duration in seconds, or None if it could not be determined by any
        of the methods below.

    Notes
    -----
    Tries, in order:

    1. The heudiconv-produced sourcedata DICOM tarball for this scan
       (``sourcedata/<same relative path>.dicom.tgz``), if present --
       see :func:`_duration_from_dicom_tarball`.  Note that this tarball is
       named after the *pre-conversion* item prefix (see
       :func:`heudiconv.convert.convert_dicom`), so for outputs whose BIDS
       filename gained suffixes at nifti-writing time -- e.g. ``_echo-1``
       for multi-echo, or ``_part-mag``/``_part-phase`` -- the expected
       tarball path below will not exist, and this transparently falls
       through to the NIfTI/JSON fallback.
    2. The NIfTI + JSON sidecar -- see :func:`_duration_from_nifti_sidecar`
       (its own sidecar ``AcquisitionDuration``, or else ``RepetitionTime``
       x number-of-volumes for multi-volume runs only).
    """
    rel = op.relpath(nifti_fn, bids_root)
    tarball = op.join(bids_root, "sourcedata", _nifti_stem(rel) + ".dicom.tgz")
    if op.exists(tarball):
        try:
            duration = _duration_from_dicom_tarball(tarball)
        except Exception as exc:
            # a corrupt archive, an extraction-filter rejection, or a
            # malformed DICOM inside it must not abort backfilling this
            # scan entirely -- fall through to the sidecar-based estimate
            # just as if the tarball had not yielded a duration
            lgr.warning(
                "Failed to read source DICOMs from %s for %s: %s",
                tarball,
                nifti_fn,
                exc,
            )
            duration = None
        if duration is not None:
            return duration
        lgr.debug(
            "Could not establish duration from source DICOMs %s for %s",
            tarball,
            nifti_fn,
        )
    return _duration_from_nifti_sidecar(nifti_fn)


def populate_scans_duration(path: str, overwrite: bool = False) -> None:
    """Retrospectively populate the 'duration' column of ``_scans.tsv`` file(s).

    This complements the automatic population of `duration` performed
    during regular BIDS conversion (see :func:`get_formatted_scans_key_row`),
    for datasets that were converted before this feature was added.

    Parameters
    ----------
    path : str
        Path to a BIDS dataset, to any directory within it (e.g., a subject
        or session folder) -- every ``*_scans.tsv`` file found at or under
        this path is processed -- or directly to a single ``*_scans.tsv``
        file.
    overwrite : bool, optional
        If True, also (re)compute `duration` for rows which already have a
        value. By default, existing non-empty values are left untouched.

    Notes
    -----
    Where the original DICOMs are no longer directly accessible, this can
    only do so much: it is a best-effort, retrospective backfill, not a
    replacement for populating `duration` at conversion time. See
    :func:`_get_retrospective_duration` for the resolution order used per
    scan; rows for which no method succeeds are (left) marked as 'n/a'.
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
            _populate_scans_duration_file(scans_tsv, overwrite=overwrite)
        except Exception as exc:
            # do not let one malformed/unexpected file abort the backfill
            # for the rest of the dataset
            lgr.error("Failed to populate 'duration' in %s: %s", scans_tsv, exc)


def _write_scans_tsv_atomically(
    scans_tsv: str, fieldnames: list[str], rows: list[dict[str, Optional[str]]]
) -> None:
    """Rewrite `scans_tsv` in place, atomically.

    Writes the new content to a temporary file in the same directory and
    ``os.replace``s it over `scans_tsv`.  This succeeds even when
    `scans_tsv` is read-only or a symlink into git-annex (as is the case
    for a DataLad-tracked dataset, see ``heudiconv/external/dlad.py``):
    replacing a directory entry only requires write permission on the
    *directory*, not on the file/symlink being replaced.  It also means a
    failure while writing the new content leaves the original file intact.

    The replacement file's permission bits are set to match the original
    (dereferencing a symlink, e.g. into git-annex) before the swap, since
    ``mkstemp`` otherwise creates it ``0600`` and ``os.replace`` does not
    itself carry over the destination's permissions -- which would
    silently narrow a shared or group-readable ``_scans.tsv`` to
    owner-only.
    """
    original_mode: Optional[int] = None
    if op.exists(scans_tsv):  # dereferences a symlink, e.g. into git-annex
        original_mode = stat.S_IMODE(os.stat(scans_tsv).st_mode)
    directory = op.dirname(scans_tsv) or "."
    fd, tmp_path = tempfile.mkstemp(
        dir=directory, prefix=".heudiconv-scans-", suffix=".tsv"
    )
    try:
        with os.fdopen(fd, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
        if original_mode is not None:
            os.chmod(tmp_path, original_mode)
        os.replace(tmp_path, scans_tsv)
    except BaseException:
        os.unlink(tmp_path)
        raise


def _populate_scans_duration_file(scans_tsv: str, overwrite: bool) -> None:
    """Backfill the 'duration' column of a single ``_scans.tsv`` file, in place."""
    session_dir = op.dirname(scans_tsv)
    bids_root = _find_bids_dataset_root(session_dir)

    with open(scans_tsv, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not fieldnames:
        return
    if "filename" not in fieldnames:
        lgr.warning("%s has no 'filename' column, skipping", scans_tsv)
        return
    if any(None in row for row in rows):
        # csv.DictReader stashes any fields beyond the header under the
        # `None` key; writing those back out under our (possibly extended)
        # `fieldnames` would raise deep inside csv.DictWriter, so bail with
        # a clear message instead of leaving a half-written file behind
        lgr.warning(
            "%s has row(s) with more fields than its header (possibly "
            "malformed); skipping duration backfill for this file",
            scans_tsv,
        )
        return

    # do this (and the scans.json sync below) even for a header-only file
    # with no data rows: a legacy _scans.tsv missing 'duration' should
    # still gain the column and get its dataset-level definition, not just
    # be left alone because there was nothing to compute per-row
    changed = "duration" not in fieldnames
    if changed:
        fieldnames = _merge_scans_header(
            fieldnames, ["filename", "acq_time", "duration"]
        )

    for row in rows:
        filename = row.get("filename")
        if not filename:
            lgr.warning("%s has a row with no filename, skipping it", scans_tsv)
            continue
        if maybe_na(row.get("duration")) != "n/a" and not overwrite:
            continue
        nifti_fn = op.join(session_dir, filename)
        if not _is_within_directory(nifti_fn, bids_root):
            lgr.warning(
                "Refusing %r in %s: resolves outside of the dataset (%s)",
                filename,
                scans_tsv,
                bids_root,
            )
            continue
        duration = _get_retrospective_duration(nifti_fn, bids_root)
        new_value = _format_duration(duration)
        if row.get("duration") != new_value:
            changed = True
        row["duration"] = new_value

    if changed:
        _write_scans_tsv_atomically(scans_tsv, fieldnames, rows)
        lgr.info("Updated 'duration' column in %s", scans_tsv)
    else:
        lgr.info("No new 'duration' values could be established for %s", scans_tsv)

    # keep the data dictionary in sync, regardless of whether the tsv
    # itself needed a rewrite this time (e.g. it may already carry correct
    # durations from a previous run, while scans.json still lacks the
    # description)
    scans_json = op.join(bids_root, "scans.json")
    if op.lexists(scans_json):
        _sync_scans_json_fields(scans_json)
    else:
        save_json(scans_json, SCANS_FILE_FIELDS, sort_keys=False)


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
) -> Optional[dict[str, dict[str, list[str]]]]:
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
) -> Optional[str]:
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
    with open(scans_tsv) as f:
        # read the contents, splitting by lines and by tab separators:
        scans_tsv_content = [line.split("\t") for line in f.read().splitlines()]
    # get column indices for filename and acq_time from the first line:
    (fname_idx, time_idx) = (
        scans_tsv_content[0].index(k) for k in ["filename", "acq_time"]
    )
    acq_times = {line[fname_idx]: line[time_idx] for line in scans_tsv_content[1:]}
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

    _known_entities = [
        "sub",
        "ses",
        "task",
        "acq",
        "ce",
        "rec",
        "dir",
        "run",
        "mod",
        "echo",
        "flip",
        "inv",
        "mt",
        "part",
        "recording",
    ]

    def __init__(
        self, entities: dict[str, str], suffix: str, extension: Optional[str]
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
        """Parse the filename for BIDS entities, suffix and extension"""
        # use re.findall to find all lower-case-letters + '-' + alphanumeric + '_' pairs:
        entities_list = re.findall("([a-z]+)-([a-zA-Z0-9]+)[_]*", filename)
        # keep only those in the _known_entities list:
        entities = {k: v for k, v in entities_list if k in BIDSFile._known_entities}
        # get whatever comes after the last key-value pair, and remove any '_' that
        # might come in front:
        ending = filename.split("-".join(entities_list[-1]))[-1]
        ending = remove_prefix(ending, "_")
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
        return (
            "_".join(
                [
                    "-".join([e, self._entities[e]])
                    for e in self._known_entities
                    if e in self._entities
                ]
            )
            + suffix
            + extension
        )

    def __getitem__(self, entity: str) -> Optional[str]:
        return self._entities[entity] if entity in self._entities else None

    def __setitem__(
        self, entity: str, value: str
    ) -> None:  # would puke with some exception if already known
        return self.set(entity, value, overwrite=False)

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
    def extension(self) -> Optional[str]:
        return self._extension


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
