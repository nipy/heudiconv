"""Handle BIDS specific operations"""

from __future__ import annotations

__docformat__ = "numpy"

from collections import OrderedDict
import csv
import errno
from glob import glob
import hashlib
import logging
import os
import os.path as op
from pathlib import Path
import re
from typing import Any, Optional
import warnings

import numpy as np
import pydicom as dcm

from . import __version__, dicoms
from .parser import find_files
from .utils import (
    create_file_if_missing,
    is_readonly,
    json_dumps,
    load_json,
    remove_prefix,
    remove_suffix,
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
            (
                "TODO: Provide description about source data, e.g. \n"
                "Directory below contains DICOMS compressed into tarballs per "
                "each sequence, replicating directory hierarchy of the BIDS dataset"
                " itself."
            ),
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
    )
    create_file_if_missing(
        op.join(path, "scans.json"), json_dumps(SCANS_FILE_FIELDS, sort_keys=False)
    )
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
    for bids_file in bids_files:
        # get filenames
        f_name = "/".join(bids_file.split("/")[-2:])
        f_name = f_name.replace("json", "nii.gz")
        rows[f_name] = get_formatted_scans_key_row(item[-1][0])
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


def add_rows_to_scans_keys_file(fn: str, newrows: dict[str, list[str]]) -> None:
    """Add new rows to the _scans file.

    Parameters
    ----------
    fn: str
      filename
    newrows: dict
      extra rows to add (acquisition time, referring physician, random string)
    """
    if op.lexists(fn):
        with open(fn, "r") as csvfile:
            reader = csv.reader(csvfile, delimiter="\t")
            existing_rows = [row for row in reader]
        # skip header
        fnames2info = {row[0]: row[1:] for row in existing_rows[1:]}

        newrows_key = newrows.keys()
        newrows_toadd = list(set(newrows_key) - set(fnames2info.keys()))
        for key_toadd in newrows_toadd:
            fnames2info[key_toadd] = newrows[key_toadd]
        # remove
        os.unlink(fn)
    else:
        fnames2info = newrows

    header = list(SCANS_FILE_FIELDS.keys())
    # prepare all the data rows
    data_rows = [[k] + v for k, v in fnames2info.items()]
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


def get_formatted_scans_key_row(dcm_fn: str | Path) -> list[str]:
    """
    Parameters
    ----------
    dcm_fn: str

    Returns
    -------
    row: list
        [ISO acquisition time, performing physician name, random string]

    """
    dcm_data = dcm.dcmread(dcm_fn, stop_before_pixels=True, force=True)
    # we need to store filenames and acquisition datetimes
    acq_datetime = dicoms.get_datetime_from_dcm(dcm_data=dcm_data)
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
    row = [acq_datetime.isoformat() if acq_datetime else "", perfphys, randstr]
    # empty entries should be 'n/a'
    # https://github.com/dartmouth-pbs/heudiconv/issues/32
    row = ["n/a" if not str(e) else e for e in row]
    return row


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
                    np.allclose(x, y) for x, y in zip(json_info[param], fm_info)
                )
            if not compatible:
                continue  # don't bother checking more params
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
