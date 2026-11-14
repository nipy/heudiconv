"""Test functions in heudiconv.bids module."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from glob import glob
import itertools
from json import JSONDecodeError
import logging
import os
import os.path as op
from pathlib import Path
from random import choice, random, seed, shuffle
import re
import shutil
import stat
import string
import tempfile
from typing import Any
from unittest.mock import patch

import nibabel
import numpy as np
from numpy import testing as np_testing
import pydicom
import pytest

from heudiconv.bids import (
    SHIM_KEY,
    AllowedCriteriaForFmapAssignment,
    BIDSFile,
    KeyInfoForForce,
    _duration_from_nifti_sidecar,
    _extract_dicom_tarball,
    _find_bids_dataset_root,
    _find_json_sidecar,
    _merge_scans_header,
    _read_scans_tsv,
    check_acq_time_congruency,
    find_compatible_fmaps_for_run,
    find_compatible_fmaps_for_session,
    find_fmap_groups,
    get_key_info_for_fmap_assignment,
    get_shim_setting,
    maybe_na,
    populate_aggregated_jsons,
    populate_bids_templates,
    populate_intended_for,
    populate_scans_duration,
    sanitize_label,
    save_scans_key,
    select_fmap_from_compatible_groups,
    treat_age,
    tuneup_bids_json_files,
)
from heudiconv.cli.run import main as runner
from heudiconv.convert import add_taskname_to_infofile
from heudiconv.dicoms import compress_dicoms
from heudiconv.utils import (
    Load,
    TempDirs,
    create_tree,
    is_readonly,
    load_json,
    remove_suffix,
    save_json,
    set_readonly,
)

from .utils import TESTS_DATA_PATH, fetch_data, gen_heudiconv_args, make_timed_dicoms

have_datalad = True
try:
    from datalad.support.exceptions import IncompleteResultsError
except ImportError:
    have_datalad = False


def gen_rand_label(label_size: int, label_seed: int, seed_stdout: bool = True) -> str:
    seed(label_seed)
    rand_char = "".join(choice(string.ascii_letters) for _ in range(label_size - 1))
    seed(label_seed)
    rand_num = choice(string.digits)
    if seed_stdout:
        print(f"Seed used to generate custom label: {label_seed}")
    return rand_char + rand_num


def test_maybe_na() -> None:
    for na in "", " ", None, "n/a", "N/A", "NA":
        assert maybe_na(na) == "n/a"
    for notna in 0, 1, False, True, "value":
        assert maybe_na(notna) == str(notna)


def test_treat_age() -> None:
    assert treat_age(None) is None
    assert treat_age(0) == "0"
    assert treat_age("0") == "0"
    assert treat_age("0000") == "0"
    assert treat_age("0000Y") == "0"
    assert treat_age("000.1Y") == "0.1"
    assert treat_age("1M") == "0.08"
    assert treat_age("12M") == "1"
    assert treat_age("0000.1") == "0.1"
    assert treat_age(0000.1) == "0.1"


SHIM_LENGTH = 6
TODAY = datetime.today()
LABEL_SEED = int.from_bytes(os.urandom(8), byteorder="big")

A_SHIM = [random() for i in range(SHIM_LENGTH)]


def test_get_shim_setting(tmp_path: Path) -> None:
    """Tests for get_shim_setting"""
    json_dir = op.join(tmp_path, "foo")
    if not op.exists(json_dir):
        os.makedirs(json_dir)
    json_name = op.join(json_dir, "sub-foo.json")
    # 1) file with no "ShimSetting", should return None
    save_json(json_name, {})
    with pytest.raises(KeyError):
        assert get_shim_setting(json_name)

    # -file with "ShimSetting" field
    save_json(json_name, {SHIM_KEY: A_SHIM})
    assert get_shim_setting(json_name) == A_SHIM


def test_get_key_info_for_fmap_assignment(
    tmp_path: Path, label_size: int = 4, label_seed: int = LABEL_SEED
) -> None:
    """
    Test get_key_info_for_fmap_assignment.

    label_size and label_seed are used for the "CustomAcquisitionLabel" matching
    parameter. label_size is the size of the random label while label_seed is
    the seed for the random label creation.
    """

    nifti_file = op.join(TESTS_DATA_PATH, "sample_nifti.nii.gz")
    # Get the expected parameters from the NIfTI header:
    MY_HEADER = nibabel.ni1.np.loadtxt(
        op.join(TESTS_DATA_PATH, remove_suffix(nifti_file, ".nii.gz") + "_params.txt")
    )
    json_name = op.join(TESTS_DATA_PATH, remove_suffix(nifti_file, ".nii.gz") + ".json")

    # 1) Call for a non-existing file should give an error:
    with pytest.raises(FileNotFoundError):
        assert get_key_info_for_fmap_assignment("foo.json", "ImagingVolume")

    # 2) matching_parameters = 'Shims'
    json_name = op.join(TESTS_DATA_PATH, remove_suffix(nifti_file, ".nii.gz") + ".json")
    save_json(
        json_name, {SHIM_KEY: A_SHIM}
    )  # otherwise get_key_info_for_fmap_assignment will give an error
    key_info = get_key_info_for_fmap_assignment(json_name, matching_parameter="Shims")
    assert key_info == [A_SHIM]

    # 3) matching_parameters = 'ImagingVolume'
    key_info = get_key_info_for_fmap_assignment(
        json_name, matching_parameter="ImagingVolume"
    )
    np_testing.assert_almost_equal(key_info[0], MY_HEADER[:4], decimal=6)
    np_testing.assert_almost_equal(key_info[1], MY_HEADER[4][:3], decimal=6)

    # 4) matching_parameters = 'Force'
    key_info = get_key_info_for_fmap_assignment(json_name, matching_parameter="Force")
    assert key_info == [KeyInfoForForce]

    # 5) matching_parameter = 'ModalityAcquisitionLabel'
    for d in ["fmap", "func", "dwi", "anat"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    for dirname, fname, expected_key_info in [
        ("fmap", "sub-foo_acq-fmri_epi.json", "func"),
        ("fmap", "sub-foo_acq-bold_epi.json", "func"),
        ("fmap", "sub-foo_acq-func_epi.json", "func"),
        ("fmap", "sub-foo_acq-diff_epi.json", "dwi"),
        ("fmap", "sub-foo_acq-anat_epi.json", "anat"),
        ("fmap", "sub-foo_acq-struct_epi.json", "anat"),
        ("func", "sub-foo_bold.json", "func"),
        ("dwi", "sub-foo_dwi.json", "dwi"),
        ("anat", "sub-foo_T1w.json", "anat"),
    ]:
        json_name = op.join(tmp_path, dirname, fname)
        save_json(json_name, {SHIM_KEY: A_SHIM})
        assert [expected_key_info] == get_key_info_for_fmap_assignment(
            json_name, matching_parameter="ModalityAcquisitionLabel"
        )

    # 6) matching_parameter = 'CustomAcquisitionLabel'
    A_LABEL = gen_rand_label(label_size, label_seed)
    for d in ["fmap", "func", "dwi", "anat"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    for dirname, fname, expected_key_info in [
        ("fmap", f"sub-foo_acq-{A_LABEL}_epi.json", A_LABEL),
        ("func", f"sub-foo_task-{A_LABEL}_acq-foo_bold.json", A_LABEL),
        ("dwi", f"sub-foo_acq-{A_LABEL}_dwi.json", A_LABEL),
        ("anat", f"sub-foo_acq-{A_LABEL}_T1w.json", A_LABEL),
    ]:
        json_name = op.join(tmp_path, dirname, fname)
        save_json(json_name, {SHIM_KEY: A_SHIM})
        assert [expected_key_info] == get_key_info_for_fmap_assignment(
            json_name, matching_parameter="CustomAcquisitionLabel"
        )

    # 7) matching_parameter = 'PlainAcquisitionLabel'
    A_LABEL = gen_rand_label(label_size, label_seed)
    for d in ["fmap", "func", "dwi", "anat"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    for dirname, fname, expected_key_info in [
        ("fmap", f"sub-foo_acq-{A_LABEL}_epi.json", A_LABEL),
        ("func", f"sub-foo_task-foo_acq-{A_LABEL}_bold.json", A_LABEL),
        ("func", f"sub-foo_task-bar_acq-{A_LABEL}_bold.json", A_LABEL),
        ("dwi", f"sub-foo_acq-{A_LABEL}_dwi.json", A_LABEL),
        ("anat", f"sub-foo_acq-{A_LABEL}_T1w.json", A_LABEL),
    ]:
        json_name = op.join(tmp_path, dirname, fname)
        save_json(json_name, {SHIM_KEY: A_SHIM})
        assert [expected_key_info] == get_key_info_for_fmap_assignment(
            json_name, matching_parameter="PlainAcquisitionLabel"
        )

    # Finally: invalid matching_parameters:
    assert (
        get_key_info_for_fmap_assignment(json_name, matching_parameter="Invalid") == []
    )


def generate_scans_tsv(session_struct: dict[str, dict[str, Any]]) -> str:
    """
    Generates the contents of the "_scans.tsv" file, given a session structure.
    Currently, it will have the columns "filename" and "acq_time".
    The acq_time will increase by one minute from run to run.

    Parameters
    ----------
    session_struct : dict
        structure for the session, as a dict with modality: files

    Returns
    -------
    scans_file_content : str
        multi-line string with the content of the file
    """
    # for each modality in session_struct (k), get the filenames:
    scans_fnames = [
        op.join(k, vk)
        for k, v in session_struct.items()
        for vk in sorted(v.keys())
        if vk.endswith(".nii.gz")
    ]
    # for each file, increment the acq_time by one minute:
    scans_file_content = ["filename\tacq_time"] + [
        "%s\t%s" % (fn, (TODAY + timedelta(minutes=i)).isoformat())
        for fn, i in zip(scans_fnames, range(len(scans_fnames)))
    ]
    # convert to multiline string:
    return "\n".join(scans_file_content)


DummySession = tuple[
    dict[str, Load],
    dict[str, list[str] | None],
    dict[str, list[str]],
    dict[str, dict[str, list[str]]],
]


def create_dummy_pepolar_bids_session(session_path: str) -> DummySession:
    """
    Creates a dummy BIDS session, with slim json files and empty nii.gz
    The fmap files are pepolar
    The json files have ShimSettings

    Parameters
    ----------
    session_path : str
        path to the session (or subject) level folder

    Returns
    -------
    session_struct : dict
        Structure of the directory that was created
    expected_result : dict
        dictionary with fmap names as keys and the expected "IntendedFor" as
        values.
    expected_fmap_groups : dict
        dictionary with the expected fmap groups
    expected_compatible_fmaps : dict
        dictionary with the expected fmap groups for each non-fmap run in the
        session
    """
    session_parent, session_basename = op.split(session_path.rstrip(op.sep))
    if session_basename.startswith("ses-"):
        prefix = op.split(session_parent)[1] + "_" + session_basename
    else:
        prefix = session_basename

    # 1) Simulate the file structure for a session:

    # Generate some random ShimSettings:
    anat_shims = [random() for i in range(SHIM_LENGTH)]
    dwi_shims = [random() for i in range(SHIM_LENGTH)]
    func_shims_A = [random() for i in range(SHIM_LENGTH)]
    func_shims_B = [random() for i in range(SHIM_LENGTH)]

    # Dict with the file structure for the session:
    # -anat:
    anat_struct: dict[str, str | dict[str, list[float]]] = {
        "{p}_{m}.nii.gz".format(p=prefix, m=mod): "" for mod in ["T1w", "T2w"]
    }
    anat_struct.update(
        {
            "{p}_{m}.json".format(p=prefix, m=mod): {"ShimSetting": anat_shims}
            for mod in ["T1w", "T2w"]
        }
    )
    # -dwi:
    dwi_struct: dict[str, str | dict[str, list[float]]] = {
        "{p}_acq-A_run-{r}_dwi.nii.gz".format(p=prefix, r=runNo): "" for runNo in [1, 2]
    }
    dwi_struct.update(
        {
            "{p}_acq-A_run-{r}_dwi.json".format(p=prefix, r=runNo): {
                "ShimSetting": dwi_shims
            }
            for runNo in [1, 2]
        }
    )
    # -func:
    func_struct: dict[str, str | dict[str, list[float]]] = {
        "{p}_acq-{a}_bold.nii.gz".format(p=prefix, a=acq): ""
        for acq in ["A", "B", "unmatched"]
    }
    func_struct.update(
        {
            "{p}_acq-A_bold.json".format(p=prefix): {"ShimSetting": func_shims_A},
            "{p}_acq-B_bold.json".format(p=prefix): {"ShimSetting": func_shims_B},
            "{p}_acq-unmatched_bold.json".format(p=prefix): {
                "ShimSetting": [random() for i in range(SHIM_LENGTH)]
            },
        }
    )
    # -fmap:
    #  * NIfTI files:
    fmap_struct: dict[str, str | dict[str, list[float]]] = {
        "{p}_acq-{a}_dir-{d}_run-{r}_epi.nii.gz".format(p=prefix, a=acq, d=d, r=r): ""
        for acq in ["dwi", "fMRI"]
        for d in ["AP", "PA"]
        for r in [1, 2]
    }
    #  * dwi shims:
    expected_fmap_groups = {
        "{p}_acq-dwi_run-{r}_epi".format(p=prefix, r=r): [
            "{p}_acq-dwi_dir-{d}_run-{r}_epi.json".format(
                p=op.join(session_path, "fmap", prefix), d=d, r=r
            )
            for d in ["AP", "PA"]
        ]
        for r in [1, 2]
    }
    fmap_struct.update(
        {
            "{p}_acq-dwi_dir-{d}_run-{r}_epi.json".format(p=prefix, d=d, r=r): {
                "ShimSetting": dwi_shims
            }
            for d in ["AP", "PA"]
            for r in [1, 2]
        }
    )
    #  * func_shims (_A and _B):
    expected_fmap_groups.update(
        {
            "{p}_acq-fMRI_run-{r}_epi".format(p=prefix, r=r): [
                "{p}_acq-fMRI_dir-{d}_run-{r}_epi.json".format(
                    p=op.join(session_path, "fmap", prefix), d=d, r=r
                )
                for d in ["AP", "PA"]
            ]
            for r in [1, 2]
        }
    )
    fmap_struct.update(
        {
            "{p}_acq-fMRI_dir-{d}_run-{r}_epi.json".format(p=prefix, d=d, r=r): {
                "ShimSetting": shims
            }
            for r, shims in {"1": func_shims_A, "2": func_shims_B}.items()
            for d in ["AP", "PA"]
        }
    )
    # structure for the full session (init the OrderedDict as a list to preserve order):
    session_struct = {
        "fmap": fmap_struct,
        "anat": anat_struct,
        "dwi": dwi_struct,
        "func": func_struct,
    }
    # add "_scans.tsv" file to the session_struct
    scans_file_content = generate_scans_tsv(session_struct)
    session_struct2: dict[str, Load] = {
        **session_struct,
        f"{prefix}_scans.tsv": scans_file_content,
    }

    create_tree(session_path, session_struct2)

    # 2) Now, let's create a dict with the fmap groups compatible for each run
    # -anat: empty
    expected_compatible_fmaps: dict[str, dict[str, list[str]]] = {
        "{p}_{m}.json".format(p=op.join(session_path, "anat", prefix), m=mod): {}
        for mod in ["T1w", "T2w"]
    }
    # -dwi: each of the runs (1, 2) is compatible with both of the dwi fmaps (1, 2):
    expected_compatible_fmaps.update(
        {
            "{p}_acq-A_run-{r}_dwi.json".format(
                p=op.join(session_path, "dwi", prefix), r=runNo
            ): {
                key: val
                for key, val in expected_fmap_groups.items()
                if key
                in ["{p}_acq-dwi_run-{r}_epi".format(p=prefix, r=r) for r in [1, 2]]
            }
            for runNo in [1, 2]
        }
    )
    # -func: acq-A is compatible w/ fmap fMRI run 1; acq-2 w/ fmap fMRI run 2
    expected_compatible_fmaps.update(
        {
            "{p}_acq-{a}_bold.json".format(
                p=op.join(session_path, "func", prefix), a=acq
            ): {
                key: val
                for key, val in expected_fmap_groups.items()
                if key in ["{p}_acq-fMRI_run-{r}_epi".format(p=prefix, r=runNo)]
            }
            for runNo, acq in {"1": "A", "2": "B"}.items()
        }
    )
    # -func (cont): acq-unmatched is empty
    expected_compatible_fmaps.update(
        {
            "{p}_acq-unmatched_bold.json".format(
                p=op.join(session_path, "func", prefix)
            ): {}
        }
    )

    # 3) Then, let's create a dict with what we expect for the "IntendedFor":

    sub_match = re.findall("(sub-([a-zA-Z0-9]*))", session_path)
    sub_str = sub_match[0][0]
    expected_prefix = session_path.split(sub_str)[-1].split(op.sep)[-1]

    # dict, with fmap names as keys and the expected "IntendedFor" as values.
    expected_result = {
        "{p}_acq-dwi_dir-{d}_run-{r}_epi.json".format(
            p=prefix, d=d, r=runNo
        ): intended_for
        # (runNo=1 goes with the long list, runNo=2 goes with None):
        for runNo, intended_for in zip(
            [1, 2],
            [
                [
                    op.join(
                        expected_prefix,
                        "dwi",
                        "{p}_acq-A_run-{r}_dwi.nii.gz".format(p=prefix, r=r),
                    )
                    for r in [1, 2]
                ],
                None,
            ],
        )
        for d in ["AP", "PA"]
    }
    expected_result.update(
        {
            "{p}_acq-fMRI_dir-{d}_run-{r}_epi.json".format(p=prefix, d=d, r=runNo): [
                op.join(
                    expected_prefix,
                    "func",
                    "{p}_acq-{a}_bold.nii.gz".format(p=prefix, a=acq),
                )
            ]
            # runNo=1 goes with acq='A'; runNo=2 goes with acq='B'
            for runNo, acq in zip([1, 2], ["A", "B"])
            for d in ["AP", "PA"]
        }
    )

    return (
        session_struct2,
        expected_result,
        expected_fmap_groups,
        expected_compatible_fmaps,
    )


def create_dummy_no_shim_settings_bids_session(session_path: str) -> DummySession:
    """
    Creates a dummy BIDS session, with slim json files and empty nii.gz
    The fmap files are pepolar
    The json files don't have ShimSettings

    Parameters
    ----------
    session_path : str
        path to the session (or subject) level folder

    Returns
    -------
    session_struct : dict
        Structure of the directory that was created
    expected_result : dict
        dictionary with fmap names as keys and the expected "IntendedFor" as
        values.
    None
        it returns a third argument (None) to have the same signature as
        create_dummy_pepolar_bids_session
    """
    session_parent, session_basename = op.split(session_path.rstrip(op.sep))
    if session_basename.startswith("ses-"):
        prefix = op.split(session_parent)[1] + "_" + session_basename
    else:
        prefix = session_basename

    # 1) Simulate the file structure for a session:

    # Dict with the file structure for the session.
    # All json files will be empty.
    # -anat:
    anat_struct = mkstruct(f"{prefix}_{{0}}.{{ext}}", ["T1w", "T2w"])
    # -dwi:
    dwi_struct = mkstruct(f"{prefix}_acq-A_run-{{0}}_dwi.{{ext}}", [1, 2])
    # -func:
    func_struct = mkstruct(f"{prefix}_acq-{{0}}_bold.{{ext}}", ["A", "B"])
    # -fmap:
    fmap_struct = mkstruct(
        f"{prefix}_acq-{{0}}_dir-{{1}}_run-{{2}}_epi.{{ext}}",
        ["dwi", "fMRI"],
        ["AP", "PA"],
        [1, 2],
    )
    expected_fmap_groups = {
        "{p}_acq-{a}_run-{r}_epi".format(p=prefix, a=acq, r=r): [
            "{p}_acq-{a}_dir-{d}_run-{r}_epi.json".format(
                p=op.join(session_path, "fmap", prefix), a=acq, d=d, r=r
            )
            for d in ["AP", "PA"]
        ]
        for acq in ["dwi", "fMRI"]
        for r in [1, 2]
    }

    # structure for the full session (init the OrderedDict as a list to preserve order):
    session_struct = OrderedDict(
        [
            ("fmap", fmap_struct),
            ("anat", anat_struct),
            ("dwi", dwi_struct),
            ("func", func_struct),
        ]
    )
    # add "_scans.tsv" file to the session_struct
    scans_file_content = generate_scans_tsv(session_struct)
    session_struct2: dict[str, Load] = {
        **session_struct,
        f"{prefix}_scans.tsv": scans_file_content,
    }

    create_tree(session_path, session_struct2)

    # 2) Now, let's create a dict with the fmap groups compatible for each run
    # -anat: empty
    expected_compatible_fmaps: dict[str, dict[str, list[str]]] = {
        "{p}_{m}.json".format(p=op.join(session_path, "anat", prefix), m=mod): {}
        for mod in ["T1w", "T2w"]
    }
    # -dwi: each of the runs (1, 2) is compatible with both of the dwi fmaps (1, 2):
    expected_compatible_fmaps.update(
        {
            "{p}_acq-A_run-{r}_dwi.json".format(
                p=op.join(session_path, "dwi", prefix), r=runNo
            ): {
                key: val
                for key, val in expected_fmap_groups.items()
                if key
                in ["{p}_acq-dwi_run-{r}_epi".format(p=prefix, r=r) for r in [1, 2]]
            }
            for runNo in [1, 2]
        }
    )
    # -func: each of the acq (A, B) is compatible w/ both fmap fMRI runs (1, 2)
    expected_compatible_fmaps.update(
        {
            "{p}_acq-{a}_bold.json".format(
                p=op.join(session_path, "func", prefix), a=acq
            ): {
                key: val
                for key, val in expected_fmap_groups.items()
                if key
                in ["{p}_acq-fMRI_run-{r}_epi".format(p=prefix, r=r) for r in [1, 2]]
            }
            for acq in ["A", "B"]
        }
    )

    # 3) Now, let's create a dict with what we expect for the "IntendedFor":
    # NOTE: The "expected_prefix" (the beginning of the path to the
    # "IntendedFor") should be relative to the subject level (see:
    # https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data)

    sub_match = re.findall("(sub-([a-zA-Z0-9]*))", session_path)
    sub_str = sub_match[0][0]
    expected_prefix = session_path.split(sub_str)[-1].split(op.sep)[-1]

    # dict, with fmap names as keys and the expected "IntendedFor" as values.
    expected_result = {
        # (runNo=1 goes with the long list, runNo=2 goes with None):
        "{p}_acq-dwi_dir-{d}_run-{r}_epi.json".format(
            p=prefix, d=d, r=runNo
        ): intended_for
        for runNo, intended_for in zip(
            [1, 2],
            [
                [
                    op.join(
                        expected_prefix,
                        "dwi",
                        "{p}_acq-A_run-{r}_dwi.nii.gz".format(p=prefix, r=r),
                    )
                    for r in [1, 2]
                ],
                None,
            ],
        )
        for d in ["AP", "PA"]
    }
    expected_result.update(
        {
            # The first "fMRI" run gets all files in the "func" folder;
            # the second shouldn't get any.
            "{p}_acq-fMRI_dir-{d}_run-{r}_epi.json".format(
                p=prefix, d=d, r=runNo
            ): intended_for
            for runNo, intended_for in zip(
                [1, 2],
                [
                    [
                        op.join(
                            expected_prefix,
                            "func",
                            "{p}_acq-{a}_bold.nii.gz".format(p=prefix, a=acq),
                        )
                        for acq in ["A", "B"]
                    ],
                    None,
                ],
            )
            for d in ["AP", "PA"]
        }
    )

    return (
        session_struct2,
        expected_result,
        expected_fmap_groups,
        expected_compatible_fmaps,
    )


def create_dummy_no_shim_settings_custom_label_bids_session(
    session_path: str, label_size: int = 4, label_seed: int = LABEL_SEED
) -> DummySession:
    """
    Creates a dummy BIDS session, with slim json files and empty nii.gz
    The fmap files are pepolar
    The json files don't have ShimSettings
    The fmap files have a custom ACQ label matching:
        - TASK label for <func> modality
        - ACQ label for any other modality (e.g. <dwi>)

    Parameters
    ----------
    session_path : str
        path to the session (or subject) level folder
    label_size : int, optional
        size of the random label
    label_seed : int, optional
        seed for the random label creation

    Returns
    -------
    session_struct : dict
        Structure of the directory that was created
    expected_result : dict
        dictionary with fmap names as keys and the expected "IntendedFor" as
        values.
    None
        it returns a third argument (None) to have the same signature as
        create_dummy_pepolar_bids_session
    """
    session_parent, session_basename = op.split(session_path.rstrip(op.sep))
    if session_basename.startswith("ses-"):
        prefix = op.split(session_parent)[1] + "_" + session_basename
    else:
        prefix = session_basename

    # 1) Simulate the file structure for a session:

    # Dict with the file structure for the session.
    # All json files will be empty.
    # -anat:
    anat_struct = mkstruct(f"{prefix}_{{0}}.{{ext}}", ["T1w", "T2w"])
    # -dwi:
    label_seed += 1
    DWI_LABEL = gen_rand_label(label_size, label_seed)
    dwi_struct = mkstruct(f"{prefix}_acq-{DWI_LABEL}_run-{{0}}_dwi.{{ext}}", [1, 2])
    # -func:
    label_seed += 1
    FUNC_LABEL = gen_rand_label(label_size, label_seed)
    func_struct = mkstruct(
        f"{prefix}_task-{FUNC_LABEL}_acq-{{0}}_bold.{{ext}}",
        ["A", "B"],
    )
    # -fmap:
    fmap_struct = mkstruct(
        f"{prefix}_acq-{{0}}_dir-{{1}}_run-{{2}}_epi.{{ext}}",
        [DWI_LABEL, FUNC_LABEL],
        ["AP", "PA"],
        [1, 2],
    )
    expected_fmap_groups = {
        f"{prefix}_acq-{acq}_run-{r}_epi": [
            f'{op.join(session_path, "fmap", prefix)}_acq-{acq}_dir-{d}_run-{r}_epi.json'
            for d in ["AP", "PA"]
        ]
        for acq in [DWI_LABEL, FUNC_LABEL]
        for r in [1, 2]
    }

    # structure for the full session (init the OrderedDict as a list to preserve order):
    session_struct = OrderedDict(
        [
            ("fmap", fmap_struct),
            ("anat", anat_struct),
            ("dwi", dwi_struct),
            ("func", func_struct),
        ]
    )
    # add "_scans.tsv" file to the session_struct
    scans_file_content = generate_scans_tsv(session_struct)
    session_struct2: dict[str, Load] = {
        **session_struct,
        f"{prefix}_scans.tsv": scans_file_content,
    }

    create_tree(session_path, session_struct2)

    # 2) Now, let's create a dict with the fmap groups compatible for each run
    # -anat: empty
    expected_compatible_fmaps: dict[str, dict[str, list[str]]] = {
        f'{op.join(session_path, "anat", prefix)}_{mod}.json': {}
        for mod in ["T1w", "T2w"]
    }
    # -dwi: each of the runs (1, 2) is compatible with both of the dwi fmaps (1, 2):
    expected_compatible_fmaps.update(
        {
            f'{op.join(session_path, "dwi", prefix)}_acq-{DWI_LABEL}_run-{runNo}_dwi.json': {
                key: val
                for key, val in expected_fmap_groups.items()
                if key in [f"{prefix}_acq-{DWI_LABEL}_run-{r}_epi" for r in [1, 2]]
            }
            for runNo in [1, 2]
        }
    )
    # -func: each of the acq (A, B) is compatible w/ both fmap fMRI runs (1, 2)
    expected_compatible_fmaps.update(
        {
            f'{op.join(session_path, "func", prefix)}_task-{FUNC_LABEL}_acq-{acq}_bold.json': {
                key: val
                for key, val in expected_fmap_groups.items()
                if key in [f"{prefix}_acq-{FUNC_LABEL}_run-{r}_epi" for r in [1, 2]]
            }
            for acq in ["A", "B"]
        }
    )

    # 3) Now, let's create a dict with what we expect for the "IntendedFor":
    # NOTE: The "expected_prefix" (the beginning of the path to the
    # "IntendedFor") should be relative to the subject level (see:
    # https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data)

    sub_match = re.findall("(sub-([a-zA-Z0-9]*))", session_path)
    sub_str = sub_match[0][0]
    expected_prefix = session_path.split(sub_str)[-1].split(op.sep)[-1]

    # dict, with fmap names as keys and the expected "IntendedFor" as values.
    expected_result = {
        # (runNo=1 goes with the long list, runNo=2 goes with None):
        f"{prefix}_acq-{DWI_LABEL}_dir-{d}_run-{runNo}_epi.json": intended_for
        for runNo, intended_for in zip(
            [1, 2],
            [
                [
                    op.join(
                        expected_prefix,
                        "dwi",
                        f"{prefix}_acq-{DWI_LABEL}_run-{r}_dwi.nii.gz",
                    )
                    for r in [1, 2]
                ],
                None,
            ],
        )
        for d in ["AP", "PA"]
    }
    expected_result.update(
        {
            # The first "fMRI" run gets all files in the "func" folder;
            # the second shouldn't get any.
            f"{prefix}_acq-{FUNC_LABEL}_dir-{d}_run-{runNo}_epi.json": intended_for
            for runNo, intended_for in zip(
                [1, 2],
                [
                    [
                        op.join(
                            expected_prefix,
                            "func",
                            f"{prefix}_task-{FUNC_LABEL}_acq-{acq}_bold.nii.gz",
                        )
                        for acq in ["A", "B"]
                    ],
                    None,
                ],
            )
            for d in ["AP", "PA"]
        }
    )

    return (
        session_struct2,
        expected_result,
        expected_fmap_groups,
        expected_compatible_fmaps,
    )


def create_dummy_magnitude_phase_bids_session(session_path: str) -> DummySession:
    """
    Creates a dummy BIDS session, with slim json files and empty nii.gz
    The fmap files are a magnitude/phase pair
    The json files have ShimSettings
    We just need to test a very simple case to make sure the mag/phase have
    the same "IntendedFor" field:

    Parameters
    ----------
    session_path : str
        path to the session (or subject) level folder

    Returns
    -------
    session_struct : dict
        Structure of the directory that was created
    expected_result : dict
        dictionary with fmap names as keys and the expected "IntendedFor" as
        values.
    expected_fmap_groups : dict
        dictionary with the expected fmap groups
    """
    session_parent, session_basename = op.split(session_path.rstrip(op.sep))
    if session_basename.startswith("ses-"):
        prefix = op.split(session_parent)[1] + "_" + session_basename
    else:
        prefix = session_basename

    # 1) Simulate the file structure for a session:

    # Generate some random ShimSettings:
    dwi_shims = [random() for i in range(SHIM_LENGTH)]
    func_shims_A = [random() for i in range(SHIM_LENGTH)]
    func_shims_B = [random() for i in range(SHIM_LENGTH)]

    # Dict with the file structure for the session:
    # -dwi:
    dwi_struct: dict[str, str | dict[str, list[float]]] = {
        "{p}_acq-A_run-{r}_dwi.nii.gz".format(p=prefix, r=runNo): "" for runNo in [1, 2]
    }
    dwi_struct.update(
        {
            "{p}_acq-A_run-{r}_dwi.json".format(p=prefix, r=runNo): {
                "ShimSetting": dwi_shims
            }
            for runNo in [1, 2]
        }
    )
    # -func:
    func_struct: dict[str, str | dict[str, list[float]]] = {
        "{p}_acq-{a}_bold.nii.gz".format(p=prefix, a=acq): ""
        for acq in ["A", "B", "unmatched"]
    }
    func_struct.update(
        {
            "{p}_acq-A_bold.json".format(p=prefix): {"ShimSetting": func_shims_A},
            "{p}_acq-B_bold.json".format(p=prefix): {"ShimSetting": func_shims_B},
            "{p}_acq-unmatched_bold.json".format(p=prefix): {
                "ShimSetting": [random() for i in range(SHIM_LENGTH)]
            },
        }
    )
    # -fmap:
    #    * Case 1 in https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data
    fmap_struct: dict[str, str | dict[str, list[float]]] = {
        "{p}_acq-case1_{s}.nii.gz".format(p=prefix, s=suffix): ""
        for suffix in ["phasediff", "magnitude1", "magnitude2"]
    }
    expected_fmap_groups = {
        "{p}_acq-case1".format(p=prefix): [
            "{p}_acq-case1_phasediff.json".format(
                p=op.join(session_path, "fmap", prefix)
            )
        ]
    }
    fmap_struct.update(
        {"{p}_acq-case1_phasediff.json".format(p=prefix): {"ShimSetting": dwi_shims}}
    )
    #    * Case 2:
    fmap_struct.update(
        {
            "{p}_acq-case2_{s}.nii.gz".format(p=prefix, s=suffix): ""
            for suffix in ["magnitude1", "magnitude2", "phase1", "phase2"]
        }
    )
    expected_fmap_groups.update(
        {
            "{p}_acq-case2".format(p=prefix): [
                "{p}_acq-case2_phase{n}.json".format(
                    p=op.join(session_path, "fmap", prefix), n=n
                )
                for n in [1, 2]
            ]
        }
    )
    fmap_struct.update(
        {
            "{p}_acq-case2_phase{n}.json".format(p=prefix, n=n): {
                "ShimSetting": func_shims_A
            }
            for n in [1, 2]
        }
    )
    #    * Case 3:
    fmap_struct.update(
        {
            "{p}_acq-case3_{s}.nii.gz".format(p=prefix, s=suffix): ""
            for suffix in ["magnitude", "fieldmap"]
        }
    )
    expected_fmap_groups.update(
        {
            "{p}_acq-case3".format(p=prefix): [
                "{p}_acq-case3_fieldmap.json".format(
                    p=op.join(session_path, "fmap", prefix)
                )
            ]
        }
    )
    fmap_struct.update(
        {"{p}_acq-case3_fieldmap.json".format(p=prefix): {"ShimSetting": func_shims_B}}
    )
    # structure for the full session (init the OrderedDict as a list to preserve order):
    session_struct = OrderedDict(
        [
            ("fmap", fmap_struct),
            ("dwi", dwi_struct),
            ("func", func_struct),
        ]
    )
    # add "_scans.tsv" file to the session_struct
    scans_file_content = generate_scans_tsv(session_struct)
    session_struct2: dict[str, Load] = {
        **session_struct,
        f"{prefix}_scans.tsv": scans_file_content,
    }

    create_tree(session_path, session_struct2)

    # 2) Now, let's create a dict with the fmap groups compatible for each run
    # -dwi: each of the runs (1, 2) is compatible with case1 fmap:
    expected_compatible_fmaps = {
        "{p}_acq-A_run-{r}_dwi.json".format(
            p=op.join(session_path, "dwi", prefix), r=runNo
        ): {
            key: val
            for key, val in expected_fmap_groups.items()
            if key in ["{p}_acq-case1".format(p=prefix)]
        }
        for runNo in [1, 2]
    }
    # -func: acq-A is compatible w/ fmap case2; acq-B w/ fmap case3
    expected_compatible_fmaps.update(
        {
            "{p}_acq-{a}_bold.json".format(
                p=op.join(session_path, "func", prefix), a=acq
            ): {
                key: val
                for key, val in expected_fmap_groups.items()
                if key in ["{p}_acq-case{c}".format(p=prefix, c=caseNo)]
            }
            for caseNo, acq in {"2": "A", "3": "B"}.items()
        }
    )
    # -func (cont): acq-unmatched is empty
    expected_compatible_fmaps.update(
        {
            "{p}_acq-unmatched_bold.json".format(
                p=op.join(session_path, "func", prefix)
            ): {}
        }
    )

    # 3) Now, let's create a dict with what we expect for the "IntendedFor":

    sub_match = re.findall("(sub-([a-zA-Z0-9]*))", session_path)
    sub_str = sub_match[0][0]
    expected_prefix = session_path.split(sub_str)[-1].split(op.sep)[-1]

    # dict, with fmap names as keys and the expected "IntendedFor" as values.
    expected_result: dict[str, list[str] | None] = {
        "{p}_acq-case1_{s}.json".format(p=prefix, s="phasediff"): [
            op.join(
                expected_prefix,
                "dwi",
                "{p}_acq-A_run-{r}_dwi.nii.gz".format(p=prefix, r=r),
            )
            for r in [1, 2]
        ]
    }
    expected_result.update(
        {
            "{p}_acq-case2_phase{n}.json".format(p=prefix, n=n):
            # populate_intended_for writes lists:
            [op.join(expected_prefix, "func", "{p}_acq-A_bold.nii.gz".format(p=prefix))]
            for n in [1, 2]
        }
    )
    expected_result.update(
        {
            "{p}_acq-case3_fieldmap.json".format(p=prefix):
            # populate_intended_for writes lists:
            [op.join(expected_prefix, "func", "{p}_acq-B_bold.nii.gz".format(p=prefix))]
        }
    )

    return (
        session_struct2,
        expected_result,
        expected_fmap_groups,
        expected_compatible_fmaps,
    )


def mkstruct(template: str, *params: list) -> dict[str, str | dict[str, str]]:
    struct: dict[str, str | dict[str, str]] = {
        template.format(*ps, ext="nii.gz"): "" for ps in itertools.product(*params)
    }
    struct.update(
        {template.format(*ps, ext="json"): {} for ps in itertools.product(*params)}
    )
    return struct


# Test cases:
# A) pepolar fmaps with ShimSetting in json files
# B) same, with no ShimSetting
# C) magnitude/phase, with ShimSetting
@pytest.mark.parametrize(
    "simulation_function",
    [
        create_dummy_pepolar_bids_session,
        create_dummy_no_shim_settings_bids_session,
        create_dummy_magnitude_phase_bids_session,
    ],
)
def test_find_fmap_groups(
    tmp_path: Path, simulation_function: Callable[[str], DummySession]
) -> None:
    """Test for find_fmap_groups"""
    folder = op.join(tmp_path, "sub-foo")
    _, _, expected_fmap_groups, _ = simulation_function(folder)
    fmap_groups = find_fmap_groups(op.join(folder, "fmap"))
    assert fmap_groups == expected_fmap_groups


# Test cases:
# A) pepolar fmaps with ShimSetting in json files
# B) same, with no ShimSetting
# C) magnitude/phase, with ShimSetting
@pytest.mark.parametrize(
    "simulation_function, match_param",
    [
        (create_dummy_pepolar_bids_session, "Shims"),
        (create_dummy_no_shim_settings_bids_session, "ModalityAcquisitionLabel"),
        (
            create_dummy_no_shim_settings_custom_label_bids_session,
            "CustomAcquisitionLabel",
        ),
        (create_dummy_magnitude_phase_bids_session, "Shims"),
    ],
)
def test_find_compatible_fmaps_for_run(
    tmp_path: Path, simulation_function: Callable[[str], DummySession], match_param: str
) -> None:
    """
    Test find_compatible_fmaps_for_run.

    Parameters
    ----------
    tmp_path
    simulation_function : function
        function to create the directory tree and expected results
    match_param : str
        matching_parameter for assigning fmaps
    """
    folder = op.join(tmp_path, "sub-foo")
    _, _, expected_fmap_groups, expected_compatible_fmaps = simulation_function(folder)
    for modality in ["anat", "dwi", "func"]:
        for json_file in glob(op.join(folder, modality, "*.json")):
            compatible_fmaps = find_compatible_fmaps_for_run(
                json_file, expected_fmap_groups, matching_parameters=[match_param]
            )
            assert compatible_fmaps == expected_compatible_fmaps[json_file]


def test_find_compatible_fmaps_for_run_union(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test find_compatible_fmaps_for_run with multiple parameters.

    This tests the behavior of find_compatible_fmaps_for_run when it
    is given more than one parameter to match on. Expects multiple
    parameters to be treated as a union (AND).
    """

    def mock_get_key_info_for_fmap_assignment(
        json_file: str, matching_parameter: str
    ) -> list[Any]:
        """
        Mock matching parameters

        Mock a situation where we have three custom acquisition labels
        and two sets of shims - but only one pairing where both match.

        The names are bids-like but not quite bids - this should not
        matter since we are testing general logic.
        """
        shims1 = [1, 2, 3, 4]
        shims2 = [5, 6, 7, 8]
        mock_info = {
            "sub-01/func/sub-01_task-foo.json": {
                "ShimSetting": shims1,
                "CustomAcquisitionLabel": "foo",
            },
            "sub-01/func/sub-01_task-bar.json": {
                "ShimSetting": shims1,
                "CustomAcquisitionLabel": "bar",
            },
            "sub-01/func/sub-01_task-baz.json": {
                "ShimSetting": shims1,
                "CustomAcquisitionLabel": "baz",
            },
            "sub-01/fmap/sub-01_acq-foo.json": {
                "ShimSetting": shims1,
                "CustomAcquisitionLabel": "foo",
            },
            "sub-01/fmap/sub-01_acq-bar.json": {
                "ShimSetting": shims2,
                "CustomAcquisitionLabel": "bar",
            },
        }
        return [mock_info[json_file][matching_parameter]]

    monkeypatch.setattr(
        "heudiconv.bids.get_key_info_for_fmap_assignment",
        mock_get_key_info_for_fmap_assignment,
    )

    fmap_groups = {
        "foo": ["sub-01/fmap/sub-01_acq-foo.json"],
        "bar": ["sub-01/fmap/sub-01_acq-bar.json"],
    }
    param_union = ["ShimSetting", "CustomAcquisitionLabel"]

    # for task-foo, one fmap matches by label and shims
    x = find_compatible_fmaps_for_run(
        "sub-01/func/sub-01_task-foo.json", fmap_groups, param_union
    )
    assert "foo" in x.keys() and len(x) == 1

    # for task-bar, we have either shims or label, but not both
    x = find_compatible_fmaps_for_run(
        "sub-01/func/sub-01_task-bar.json", fmap_groups, param_union
    )
    assert len(x) == 0

    # for task-baz we have matching shims, but not label
    x = find_compatible_fmaps_for_run(
        "sub-01/func/sub-01_task-baz.json", fmap_groups, param_union
    )
    assert len(x) == 0


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "rel_diff,should_match",
    [
        (
            0.02,
            True,
        ),  # 2% difference - should be compatible (real-world case from ds005256)
        (0.03, True),  # 3% difference - should be compatible
        (0.049, True),  # 4.9% difference - just under threshold, should be compatible
        (
            0.06,
            False,
        ),  # 6% difference - clearly over 5% threshold, should NOT be compatible
        (0.07, False),  # 7% difference - should NOT be compatible
        (0.10, False),  # 10% difference - should NOT be compatible
    ],
)
def test_find_compatible_fmaps_rtol(
    tmp_path: Path, rel_diff: float, should_match: bool
) -> None:
    """
    Test that rtol=0.05 (5% relative tolerance) works correctly for fieldmap matching.

    This tests the enhancement from https://github.com/OpenNeuroDatasets/ds005256/pull/2
    which allows affine matrices and other numeric parameters to differ by up to 5%
    while still being considered compatible for fieldmap assignment.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory for test files
    rel_diff : float
        Relative difference to test (e.g., 0.02 for 2%, 0.06 for 6%)
    should_match : bool
        Whether the fmaps should be considered compatible at this tolerance
    """
    import numpy as np

    # Create a session directory
    session_path = op.join(tmp_path, "sub-test")
    os.makedirs(op.join(session_path, "func"), exist_ok=True)
    os.makedirs(op.join(session_path, "fmap"), exist_ok=True)

    # Create base affine matrix (typical neuroimaging affine)
    base_affine = np.array(
        [
            [2.0, 0.0, 0.0, -90.0],
            [0.0, 2.0, 0.0, -126.0],
            [0.0, 0.0, 2.0, -72.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )

    # Create a modified affine with the specified relative difference
    # Apply the difference to non-zero, non-1.0 elements
    modified_affine = base_affine.copy()
    # Modify diagonal elements (2.0 values) and translation components
    for i in range(3):
        modified_affine[i, i] = base_affine[i, i] * (1 + rel_diff)  # Apply to diagonal
        modified_affine[i, 3] = base_affine[i, 3] * (
            1 + rel_diff
        )  # Apply to translation

    # Create base ShimSettings
    base_shims = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    modified_shims = [s * (1 + rel_diff) for s in base_shims]

    # Test with ImagingVolume (affine-based matching)
    # Create NIfTI files with different affines
    func_nifti = op.join(session_path, "func", "sub-test_task-rest_bold.nii.gz")
    fmap_nifti = op.join(session_path, "fmap", "sub-test_dir-AP_epi.nii.gz")

    # Create minimal NIfTI files with the specific affines
    func_img = nibabel.Nifti1Image(np.zeros((64, 64, 30)), base_affine)
    nibabel.save(func_img, func_nifti)

    fmap_img = nibabel.Nifti1Image(np.zeros((64, 64, 30)), modified_affine)
    nibabel.save(fmap_img, fmap_nifti)

    # Create corresponding JSON files
    func_json = op.join(session_path, "func", "sub-test_task-rest_bold.json")
    fmap_json = op.join(session_path, "fmap", "sub-test_dir-AP_epi.json")

    save_json(func_json, {"EchoTime": 0.030})
    save_json(fmap_json, {"EchoTime": 0.030})

    # Create fmap groups
    fmap_groups = {"sub-test_epi": [fmap_json]}

    # Test compatibility with ImagingVolume matching
    compatible_fmaps = find_compatible_fmaps_for_run(
        func_json, fmap_groups, matching_parameters=["ImagingVolume"]
    )

    if should_match:
        assert len(compatible_fmaps) == 1, (
            f"Expected fmaps to be compatible with {rel_diff * 100:.1f}% difference, "
            f"but got {len(compatible_fmaps)} compatible groups"
        )
        assert "sub-test_epi" in compatible_fmaps
    else:
        assert len(compatible_fmaps) == 0, (
            f"Expected fmaps to be incompatible with {rel_diff * 100:.1f}% difference, "
            f"but got {len(compatible_fmaps)} compatible groups"
        )

    # Test with Shims matching
    # Update JSON files with ShimSettings
    save_json(func_json, {"ShimSetting": base_shims})
    save_json(fmap_json, {"ShimSetting": modified_shims})

    compatible_fmaps_shims = find_compatible_fmaps_for_run(
        func_json, fmap_groups, matching_parameters=["Shims"]
    )

    if should_match:
        assert len(compatible_fmaps_shims) == 1, (
            f"Expected fmaps with ShimSettings to be compatible with {rel_diff * 100:.1f}% difference, "
            f"but got {len(compatible_fmaps_shims)} compatible groups"
        )
        assert "sub-test_epi" in compatible_fmaps_shims
    else:
        assert len(compatible_fmaps_shims) == 0, (
            f"Expected fmaps with ShimSettings to be incompatible with {rel_diff * 100:.1f}% difference, "
            f"but got {len(compatible_fmaps_shims)} compatible groups"
        )


# Test two scenarios for each case:
# -study without sessions
# -study with sessions
# Cases:
# A) pepolar fmaps with ShimSetting in json files
# B) same, with no ShimSetting
# C) magnitude/phase, with ShimSetting
@pytest.mark.parametrize(
    "folder, expected_prefix, simulation_function, match_param",
    [
        (folder, expected_prefix, sim_func, mp)
        for folder, expected_prefix in zip(
            ["no_sessions/sub-1", "sessions/sub-1/ses-pre"], ["", "ses-pre"]
        )
        for sim_func, mp in [
            (create_dummy_pepolar_bids_session, "Shims"),
            (create_dummy_no_shim_settings_bids_session, "ModalityAcquisitionLabel"),
            (
                create_dummy_no_shim_settings_custom_label_bids_session,
                "CustomAcquisitionLabel",
            ),
            (create_dummy_magnitude_phase_bids_session, "Shims"),
        ]
    ],
)
def test_find_compatible_fmaps_for_session(
    tmp_path: Path,
    folder: str,
    expected_prefix: str,
    simulation_function: Callable[[str], DummySession],
    match_param: str,
) -> None:
    """
    Test find_compatible_fmaps_for_session.

    Parameters
    ----------
    tmp_path
    folder : str
        path to BIDS study to be simulated, relative to tmp_path
    expected_prefix : str
        expected start of the "IntendedFor" elements
    simulation_function : function
        function to create the directory tree and expected results
    match_param : str
        matching_parameter for assigning fmaps
    """
    session_folder = op.join(tmp_path, folder)
    _, _, _, expected_compatible_fmaps = simulation_function(session_folder)

    compatible_fmaps = find_compatible_fmaps_for_session(
        session_folder, matching_parameters=[match_param]
    )

    assert compatible_fmaps == expected_compatible_fmaps


# Test two scenarios for each case:
# -study without sessions
# -study with sessions
# Cases:
# A) pepolar fmaps with ShimSetting in json files
# B) same, with no ShimSetting
# C) magnitude/phase, with ShimSetting
@pytest.mark.parametrize(
    "folder, expected_prefix, simulation_function",
    [
        (folder, expected_prefix, sim_func)
        for folder, expected_prefix in zip(
            ["no_sessions/sub-1", "sessions/sub-1/ses-pre"], ["", "ses-pre"]
        )
        for sim_func in [
            create_dummy_pepolar_bids_session,
            create_dummy_no_shim_settings_bids_session,
            create_dummy_magnitude_phase_bids_session,
        ]
    ],
)
def test_select_fmap_from_compatible_groups(
    tmp_path: Path,
    folder: str,
    expected_prefix: str,
    simulation_function: Callable[[str], DummySession],
) -> None:
    """Test select_fmap_from_compatible_groups"""
    session_folder = op.join(tmp_path, folder)
    _, _, _, expected_compatible_fmaps = simulation_function(session_folder)

    for json_file, fmap_groups in expected_compatible_fmaps.items():
        for criterion in AllowedCriteriaForFmapAssignment:
            if not op.dirname(json_file).endswith("fmap"):
                selected_fmap = select_fmap_from_compatible_groups(
                    json_file, fmap_groups, criterion=criterion
                )
            # when the criterion is 'First', you should get the first of
            # the compatible_fmaps (for that json_file), if it is 'Closest',
            # it should be the last one (the fmaps are "run" at the
            # beginning of the session)
            if selected_fmap:
                if criterion == "First":
                    assert (
                        selected_fmap == sorted(expected_compatible_fmaps[json_file])[0]
                    )
                elif criterion == "Closest":
                    assert (
                        selected_fmap
                        == sorted(expected_compatible_fmaps[json_file])[-1]
                    )
            else:
                assert not expected_compatible_fmaps[json_file]


# Test two scenarios for each case:
# -study without sessions
# -study with sessions
# Cases:
# A) pepolar fmaps with ShimSetting in json files
# B) same, with no ShimSetting
# C) magnitude/phase, with ShimSetting
@pytest.mark.parametrize(
    "folder, expected_prefix, simulation_function, match_param",
    [
        (folder, expected_prefix, sim_func, mp)
        for folder, expected_prefix in zip(
            ["no_sessions/sub-1", "sessions/sub-1/ses-pre"], ["", "ses-pre"]
        )
        for sim_func, mp in [
            (create_dummy_pepolar_bids_session, "Shims"),
            (create_dummy_no_shim_settings_bids_session, "ModalityAcquisitionLabel"),
            (
                create_dummy_no_shim_settings_custom_label_bids_session,
                "CustomAcquisitionLabel",
            ),
            (create_dummy_magnitude_phase_bids_session, "Shims"),
        ]
    ],
)
def test_populate_intended_for(
    tmp_path: Path,
    folder: str,
    expected_prefix: str,
    simulation_function: Callable[[str], DummySession],
    match_param: str,
) -> None:
    """
    Test populate_intended_for.
    Parameters
    ----------
    tmp_path
    folder : str
        path to BIDS study to be simulated, relative to tmp_path
    expected_prefix : str
        expected start of the "IntendedFor" elements
    simulation_function : function
        function to create the directory tree and expected results
    match_param : str
        matching_parameter for assigning fmaps
    """

    session_folder = op.join(tmp_path, folder)
    session_struct, expected_result, _, _ = simulation_function(session_folder)
    populate_intended_for(
        session_folder, matching_parameters=match_param, criterion="First"
    )

    # Now, loop through the jsons in the fmap folder and make sure it matches
    # the expected result:
    fmap_folder = op.join(session_folder, "fmap")
    fmap = session_struct["fmap"]
    assert isinstance(fmap, dict)
    for j in fmap.keys():
        if j.endswith(".json"):
            assert j in expected_result.keys()
            data = load_json(op.join(fmap_folder, j))
            if expected_result[j]:
                assert data["IntendedFor"] == expected_result[j]
                # Also, make sure the run with random shims is not here:
                # (It is assured by the assert above, but let's make it
                # explicit)
                run_prefix = j.split("_acq")[0]
                assert (
                    "{p}_acq-unmatched_bold.nii.gz".format(p=run_prefix)
                    not in data["IntendedFor"]
                )
            else:
                assert "IntendedFor" not in data.keys()


def test_BIDSFile() -> None:
    """Tests for the BIDSFile class"""

    # define entities in the correct order:
    sorted_entities = [
        ("sub", "Jason"),
        ("acq", "Treadstone"),
        ("run", "2"),
        ("echo", "1"),
    ]
    # 'sub-Jason_acq-Treadstone_run-2_echo-1':
    expected_sorted_str = "_".join(["-".join(e) for e in sorted_entities])
    # expected BIDSFile:
    suffix = "T1w"
    extension = "nii.gz"
    expected_bids_file = BIDSFile(OrderedDict(sorted_entities), suffix, extension)

    # entities in random order:
    idcs = list(range(len(sorted_entities)))
    shuffle(idcs)
    shuffled_entities = [sorted_entities[i] for i in idcs]
    shuffled_str = "_".join(["-".join(e) for e in shuffled_entities])

    # Test __eq__ method.
    # It should consider equal BIDSFiles with the same entities even in different order:
    assert (
        BIDSFile(OrderedDict(shuffled_entities), suffix, extension)
        == expected_bids_file
    )

    # Test __getitem__:
    assert all([expected_bids_file[k] == v for k, v in shuffled_entities])

    # Test filename parser and  __str__ method:
    # Note: the __str__ method should return entities in the correct order
    ending = "_T1w.nii.gz"  # suffix + extension
    my_bids_file = BIDSFile.parse(shuffled_str + ending)
    assert my_bids_file == expected_bids_file
    assert str(my_bids_file) == expected_sorted_str + ending

    ending = ".json"  # just extension
    my_bids_file = BIDSFile.parse(shuffled_str + ending)
    assert my_bids_file.suffix == ""
    assert str(my_bids_file) == expected_sorted_str + ending

    ending = "_T1w"  # just suffix
    my_bids_file = BIDSFile.parse(shuffled_str + ending)
    assert my_bids_file.extension is None
    assert str(my_bids_file) == expected_sorted_str + ending

    # Complain if entity 'sub' is not set:
    with pytest.raises(ValueError) as e_info:
        assert str(BIDSFile.parse("dir-reversed.json"))
        assert "sub-" in str(e_info.value)

    # Test set method:
    # -for a new entity, just set it without a complaint:
    my_bids_file["dir"] = "AP"
    assert my_bids_file["dir"] == "AP"
    # -for an existing entity, don't change it by default:
    my_bids_file["echo"] = "2"
    assert (
        my_bids_file["echo"] == expected_bids_file["echo"]
    )  # still the original value
    # -for an existing entity, you can overwrite it with "set":
    my_bids_file.set("echo", "2")
    assert my_bids_file["echo"] == "2"

    # Test drop method
    my_bids_file.drop("dir")
    assert "dir" not in my_bids_file
    # dropping an entity which is not set raises unless missing_ok is given.
    # test previously dropped entity and entirely non-existing
    for entity in ["dir", "not_existing"]:
        with pytest.raises(ValueError, match=f"does not contain entity {entity!r}"):
            my_bids_file.drop(entity)
        # implicitly assert that no exception is thrown when using missing_ok
        my_bids_file.drop(entity, missing_ok=True)


@pytest.mark.ai_generated
def test_populate_aggregated_jsons_events(tmp_path: Path) -> None:
    """A single _events.tsv is generated for files differing only in
    entities the events are independent of ('chunk', 'echo', and 'part')"""
    func_path = tmp_path / "sub-01" / "func"
    bold_json = {"RepetitionTime": 1.0, "TaskName": "rest"}
    create_tree(
        str(func_path),
        {
            f"sub-01_task-rest_{entity}_bold.json": dict(bold_json)
            for entity in [
                "chunk-1",
                "chunk-2",
                "echo-1",
                "echo-2",
                "part-mag",
                "part-phase",
            ]
        },
    )

    populate_aggregated_jsons(str(tmp_path))

    events_files = sorted(func_path.glob("*_events.tsv"))
    assert events_files == [func_path / "sub-01_task-rest_events.tsv"]
    # and nothing got written elsewhere in the dataset:
    assert sorted(tmp_path.rglob("*_events.tsv")) == events_files


@pytest.mark.parametrize(
    "shuffled,expected",
    [
        # entities which heudiconv itself adds, all of them at once
        (
            "sub-1_chunk-2_part-mag_echo-1_acq-A_dir-AP_ses-B_run-3_rec-C_ce-D_task-E",
            "sub-1_ses-B_task-E_acq-A_ce-D_rec-C_dir-AP_run-3_echo-1_part-mag_chunk-2",
        ),
        # entities from the non-MR modalities, which the entity table
        # interleaves with the ones above
        (
            "sub-1_stain-A_nuc-1H_trc-C_voi-D_tracksys-E_acq-F_task-G",
            "sub-1_task-G_tracksys-E_acq-F_nuc-1H_voi-D_trc-C_stain-A",
        ),
        # entities we never produce ourselves still have to round-trip
        ("sub-1_space-T1w_hemi-L_run-1", "sub-1_run-1_hemi-L_space-T1w"),
    ],
)
@pytest.mark.ai_generated
def test_BIDSFile_entity_order(shuffled: str, expected: str) -> None:
    """__str__ must order entities as the BIDS entity table mandates"""
    assert str(BIDSFile.parse(shuffled + "_T1w.nii.gz")) == expected + "_T1w.nii.gz"


@pytest.mark.parametrize(
    "filename,entities,suffix",
    [
        # reproin's marker for duplicated series is part of the suffix
        (
            "sub-1_task-rest_bold__dup-01.json",
            {"sub": "1", "task": "rest"},
            "bold__dup-01",
        ),
        # so is a '-' within the suffix itself
        ("sub-1_run-1_T1w-mod.nii.gz", {"sub": "1", "run": "1"}, "T1w-mod"),
        # a non-alphanumeric value (e.g. from a heuristic) is kept whole, and
        # does not hide the entities which follow it
        (
            "sub-01_task-rest-state_acq-fmri_dir-AP_epi.json",
            {"sub": "01", "task": "rest-state", "acq": "fmri", "dir": "AP"},
            "epi",
        ),
        (
            "sub-01_acq-a+b_run-2_T1w.json",
            {"sub": "01", "acq": "a+b", "run": "2"},
            "T1w",
        ),
    ],
)
@pytest.mark.ai_generated
def test_BIDSFile_parse(filename: str, entities: dict[str, str], suffix: str) -> None:
    """parse must split entities from the suffix, and round-trip the name"""
    bids_file = BIDSFile.parse(filename)
    assert {e: bids_file[e] for e in entities} == entities
    assert all(bids_file[e] is None for e in ("ses", "chunk"))
    assert bids_file.suffix == suffix
    assert str(bids_file) == filename


@pytest.mark.ai_generated
def test_BIDSFile_unknown_entities(caplog: pytest.LogCaptureFixture) -> None:
    """Entities we do not know about must be kept, not silently dropped"""
    with caplog.at_level(logging.WARNING):
        out = str(BIDSFile.parse("sub-1_run-1_madeup-X_T1w.nii.gz"))
    assert out == "sub-1_run-1_madeup-X_T1w.nii.gz"
    assert "madeup" in caplog.text


@pytest.mark.ai_generated
def test_convert_multiorient(
    tmp_path: Path,
    heuristic: str = "bids_localizer.py",
    subID: str = "loc",
) -> None:
    """Test conversion of a series which dcm2niix splits into several images
    because they were acquired with different orientations (a 3-plane
    localizer): each of them should get its own `chunk-` index.
    """
    datadir = op.join(TESTS_DATA_PATH, "01-localizer_64ch")
    outdir = tmp_path / "out"
    outdir.mkdir()
    args = gen_heudiconv_args(datadir, str(outdir), subID, heuristic)
    runner(args)

    anatdir = outdir / f"sub-{subID}" / "anat"
    expected = {
        f"sub-{subID}_chunk-{chunk}_localizer.{ext}"
        for chunk in (1, 2, 3)
        for ext in ("nii.gz", "json")
    }
    # nothing more, nothing less -- in particular no file left with the
    # dcm2niix `_i0000<N>` postfix or with a mangled suffix
    assert {f.name for f in anatdir.iterdir()} == expected


@pytest.mark.ai_generated
def test_convert_multiorient_nonunique(
    tmp_path: Path,
    heuristic: str = "bids_localizer.py",
    subID: str = "loc",
) -> None:
    """dcm2niix splits a series on more than the orientation, so it can produce
    two images which share one.  `chunk-` cannot tell those apart, and we must
    not end up overwriting (or failing to move onto) our own output.
    """
    import pydicom

    datadir = tmp_path / "dicoms"
    shutil.copytree(op.join(TESTS_DATA_PATH, "01-localizer_64ch"), datadir)
    # add a 4th image repeating the 1st one's orientation, at a different
    # matrix size so that dcm2niix writes it out separately
    ds = pydicom.dcmread(sorted(datadir.iterdir())[0])
    arr = ds.pixel_array[::2, ::2]
    ds.PixelData = arr.tobytes()
    ds.Rows, ds.Columns = arr.shape
    ds.PixelSpacing = [float(v) * 2 for v in ds.PixelSpacing]
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    ds.InstanceNumber = 99
    ds.save_as(datadir / "extra.dcm")

    outdir = tmp_path / "out"
    outdir.mkdir()
    runner(gen_heudiconv_args(str(datadir), str(outdir), subID, heuristic))

    niftis = sorted((outdir / f"sub-{subID}" / "anat").glob("*.nii.gz"))
    # every converted image is still there, under a name of its own
    assert len(niftis) == 4
    assert len({f.name for f in niftis}) == 4
    # and since chunk- could not do it, none of them claims to be a chunk
    assert not any("chunk-" in f.name for f in niftis)


@pytest.mark.skipif(not have_datalad, reason="no datalad")
def test_ME_mag_phase_conversion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    subID: str = "MEGRE",
    heuristic: str = "bids_ME.py",
) -> None:
    """Unit test for the case of multi-echo GRE data with
    magnitude and phase.
    The different echoes should be labeled automatically.
    """
    monkeypatch.chdir(tmp_path)
    try:
        datadir = fetch_data(tmp_path, f"dicoms/velasco/{subID}")
    except IncompleteResultsError as exc:
        pytest.skip("Failed to fetch test data: %s" % str(exc))

    outdir = tmp_path / "out"
    outdir.mkdir()
    args = gen_heudiconv_args(datadir, str(outdir), subID, heuristic)
    runner(args)  # run conversion

    # Check that the expected files have been extracted.
    # This also checks that the "echo" entity comes before "part":
    for part in ["mag", "phase"]:
        for e in range(1, 4):
            for ext in ["nii.gz", "json"]:
                assert op.exists(
                    op.join(outdir, "sub-%s", "anat", "sub-%s_echo-%s_part-%s_MEGRE.%s")
                    % (subID, subID, e, part, ext)
                )


def test_sanitize_label() -> None:
    assert sanitize_label("az XZ-@09") == "azXZ09"
    with pytest.raises(ValueError):
        sanitize_label(" @ ")


BOLD = "func/sub-01_task-rest_bold"


class ScansDataset:
    """A minimal BIDS dataset with the `_scans.tsv` of its sub-01."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.root = tmp_path / "bids"
        (self.root / "sub-01" / "func").mkdir(parents=True)
        save_json(
            self.root / "dataset_description.json",
            {"Name": "test", "BIDSVersion": "1.8.0"},
        )
        self.scans_tsv = self.root / "sub-01" / "sub-01_scans.tsv"
        self.scans_tsv.write_text("filename\tacq_time\n")

    def add_row(self, *cells: str) -> None:
        with self.scans_tsv.open("a") as f:
            f.write("\t".join(cells) + "\n")

    def add_scan(
        self,
        stem: str = BOLD,
        acq_time: str = "2020-01-01T12:00:02",
        sidecar: dict[str, Any] | str | None = None,
        nvols: int | None = None,
        dicom_offsets: Sequence[float] = (),
        tz_offset: str | None = None,
    ) -> Path:
        """Add a scan with its row, and return the path of its JSON sidecar.

        The NIfTI is of `nvols` volumes, or empty if None.  The `sidecar` is
        JSON or, if a str, written as is; none is written if None.  DICOMs
        acquired at `dicom_offsets`, if any, go under sourcedata/.
        """
        nifti, json_file = (
            self.root / "sub-01" / (stem + ext) for ext in (".nii.gz", ".json")
        )
        if nvols is None:
            nifti.write_bytes(b"")
        else:
            nibabel.Nifti1Image(np.zeros((2, 2, 2, nvols)), np.eye(4)).to_filename(
                nifti
            )
        if isinstance(sidecar, str):
            json_file.write_text(sidecar)
        elif sidecar is not None:
            save_json(json_file, sidecar)
        if dicom_offsets:
            self.add_sourcedata(self.make_dicoms(dicom_offsets, tz_offset), stem)
        self.add_row(stem + ".nii.gz", acq_time)
        return json_file

    def make_dicoms(
        self, offsets: Sequence[float], tz_offset: str | None = None
    ) -> list[str]:
        dicom_dir = Path(tempfile.mkdtemp(dir=self.tmp_path))
        return make_timed_dicoms(dicom_dir, offsets, tz_offset=tz_offset)

    def add_sourcedata(self, dicom_list: list[str], stem: str = BOLD) -> None:
        """Package `dicom_list` under sourcedata/ as heudiconv does for `stem`."""
        prefix = self.root / "sourcedata" / "sub-01" / stem
        prefix.parent.mkdir(parents=True, exist_ok=True)
        compress_dicoms(dicom_list, str(prefix), TempDirs(), overwrite=True)

    def read(self) -> tuple[list[str], list[dict[str, str | None]]]:
        return _read_scans_tsv(str(self.scans_tsv))

    @property
    def rows(self) -> list[dict[str, str | None]]:
        return self.read()[1]


@pytest.fixture
def scans_ds(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> ScansDataset:
    caplog.set_level(logging.INFO, logger="heudiconv.bids")
    return ScansDataset(tmp_path)


def _bids_log(caplog: pytest.LogCaptureFixture, level: int = logging.WARNING) -> str:
    """Messages of `level` and above, logged by heudiconv.bids."""
    return "\n".join(
        f"{r.levelname}: {r.getMessage()}"
        for r in caplog.records
        if r.name == "heudiconv.bids" and r.levelno >= level
    )


@pytest.mark.ai_generated
@pytest.mark.parametrize("target", ["dataset", "scans_tsv"])
def test_populate_scans_duration_from_sourcedata(
    scans_ds: ScansDataset, target: str
) -> None:
    scans_ds.add_scan()
    scans_ds.add_sourcedata(
        sorted(glob(op.join(TESTS_DATA_PATH, "b0dwiForFmap", "*.dcm")))
    )

    populate_scans_duration(
        str(scans_ds.root if target == "dataset" else scans_ds.scans_tsv)
    )

    fieldnames, rows = scans_ds.read()
    assert fieldnames == ["filename", "acq_time", "duration"]
    assert rows[0]["duration"] == "12.450"
    # and the data dictionary of the dataset documents it
    assert "duration" in load_json(scans_ds.root / "scans.json")


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "outputs,tarball",
    [
        # heudiconv inserts an entity into the name of each output ...
        (["task-rest_echo-1_bold", "task-rest_echo-2_bold"], "task-rest_bold"),
        (["task-rest_part-mag_bold", "task-rest_part-phase_bold"], "task-rest_bold"),
        (["task-rest_ch-1_bold", "task-rest_ch-2_bold"], "task-rest_bold"),
        (["task-rest_chunk-1_bold", "task-rest_chunk-2_bold"], "task-rest_bold"),
        # ... or appends an index to its suffix
        (["magnitude1", "magnitude2"], "magnitude"),
    ],
)
def test_populate_scans_duration_of_multi_output_item(
    scans_ds: ScansDataset, outputs: list[str], tarball: str
) -> None:
    # sidecar times of the outputs of an item may legitimately differ (e.g.
    # localizer planes)
    sidecar_times = ["12:00:02.000000", "12:00:04.000000"]
    sidecars = [
        scans_ds.add_scan(f"func/sub-01_{output}", sidecar={"AcquisitionTime": time})
        for output, time in zip(outputs, sidecar_times, strict=True)
    ]
    # they share one sourcedata tarball, named after the item
    scans_ds.add_sourcedata(
        scans_ds.make_dicoms([2, 0, 4, 7]), f"func/sub-01_{tarball}"
    )
    # which is the longest of those their names start with
    scans_ds.add_sourcedata(scans_ds.make_dicoms([0, 100]), "func/sub-01")

    with patch(
        "heudiconv.bids._extract_dicom_tarball", wraps=_extract_dicom_tarball
    ) as extract:
        populate_scans_duration(str(scans_ds.root), fix_acq_time=True)

    assert extract.call_count == 1
    # duration and acq_time, the same for all outputs of an item, are fixed ...
    assert [(row["acq_time"], row["duration"]) for row in scans_ds.rows] == [
        ("2020-01-01T12:00:00", "9.000")
    ] * 2
    # ... but not the sidecars, which only conversion sees all together
    assert [load_json(f)["AcquisitionTime"] for f in sidecars] == sidecar_times


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "filename", ["../../outside.nii.gz", "/outside.nii.gz", "escape/outside.nii.gz"]
)
def test_populate_scans_duration_refuses_paths_outside_dataset(
    scans_ds: ScansDataset, caplog: pytest.LogCaptureFixture, filename: str
) -> None:
    (scans_ds.root / "sub-01" / "escape").symlink_to(scans_ds.tmp_path)
    scans_ds.add_row(filename, "n/a")

    populate_scans_duration(str(scans_ds.root), overwrite=True)

    assert "resolves outside of the dataset" in caplog.text
    assert scans_ds.rows[0]["duration"] == "n/a"


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "stored,tz_offset,fixed",
    [
        # https://github.com/nipy/heudiconv/issues/876: acq_time is of the
        # first DICOM, which is not the earliest acquired
        ("2020-01-01T12:00:02", None, "2020-01-01T12:00:00"),
        # heudiconv < 1.3.0 stored it timezone-naive, whereas DICOMs with
        # TimezoneOffsetFromUTC give aware ones: the stored style is kept
        ("2020-01-01T12:00:02", "+0100", "2020-01-01T12:00:00"),
        # a gap of days is rather of date-shifting anonymization, which
        # fixing would undo
        ("1900-01-01T12:00:02", None, None),
    ],
)
def test_populate_scans_duration_acq_time(
    scans_ds: ScansDataset,
    caplog: pytest.LogCaptureFixture,
    stored: str,
    tz_offset: str | None,
    fixed: str | None,
) -> None:
    # dcm2niix's AcquisitionTime is biased the same way
    # (https://github.com/rordenlab/dcm2niix/issues/1039), and heudiconv
    # leaves converted files read-only
    sidecar = scans_ds.add_scan(
        acq_time=stored,
        sidecar={"AcquisitionTime": "12:00:02.000000"},
        dicom_offsets=[2, 0, 4, 7],
        tz_offset=tz_offset,
    )
    set_readonly(str(sidecar))

    populate_scans_duration(str(scans_ds.root))

    # the span of 7s + the median interval of 2s, whatever the acq_time,
    # which is only warned about
    assert scans_ds.rows == [
        {"filename": BOLD + ".nii.gz", "acq_time": stored, "duration": "9.000"}
    ]
    assert "differs from the earliest acquisition" in caplog.text
    assert ("pass --fix-acq-time" in caplog.text) == bool(fixed)
    assert ("looks anonymized/date-shifted, not fixing" in caplog.text) != bool(fixed)
    # and the sidecar agrees with it
    assert "disagrees with AcquisitionTime" not in caplog.text

    populate_scans_duration(str(scans_ds.root), overwrite=True, fix_acq_time=True)

    assert scans_ds.rows[0]["acq_time"] == (fixed or stored)
    assert load_json(sidecar)["AcquisitionTime"] == (
        "12:00:00.000000" if fixed else "12:00:02.000000"
    )
    assert is_readonly(str(sidecar))


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "sidecar,sidecar_time,dicom_offsets",
    [
        # shared with other scans (Inheritance Principle)
        ("task-rest_bold.json", "12:00:02.000000", [2, 0, 4, 7]),
        # no source DICOMs to tell by whether it is the one which is off
        (f"sub-01/{BOLD}.json", "12:00:05.000000", []),
    ],
    ids=["inherited", "no-tarball"],
)
def test_populate_scans_duration_fix_acq_time_leaves_sidecar(
    scans_ds: ScansDataset,
    caplog: pytest.LogCaptureFixture,
    sidecar: str,
    sidecar_time: str,
    dicom_offsets: list[float],
) -> None:
    scans_ds.add_scan(dicom_offsets=dicom_offsets)
    content = {"AcquisitionTime": sidecar_time}
    save_json(scans_ds.root / sidecar, content)

    populate_scans_duration(str(scans_ds.root), overwrite=True, fix_acq_time=True)

    assert load_json(scans_ds.root / sidecar) == content
    assert "disagrees with AcquisitionTime" in caplog.text
    assert "would fix it" not in caplog.text


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "sidecar_time,expected,expected_log",
    [
        # dcm2niix recorded the time of the first DICOM (as ordered for
        # conversion), acquired 2s after the earliest one
        ("12:00:02.000000", "12:00:00.000000", ""),
        # must not get in the way of the conversion
        ("junk", "junk", "WARNING: Failed to check acq_time of prefix"),
    ],
)
def test_save_scans_key_checks_sidecar_acquisition_time(
    scans_ds: ScansDataset,
    caplog: pytest.LogCaptureFixture,
    sidecar_time: str,
    expected: str,
    expected_log: str,
) -> None:
    sidecar = scans_ds.root / "sub-01" / (BOLD + ".json")
    save_json(sidecar, {"AcquisitionTime": sidecar_time})
    scans_ds.scans_tsv.unlink()

    save_scans_key(
        ("prefix", ("nii.gz",), scans_ds.make_dicoms([2, 0, 1, 3])), [str(sidecar)]
    )

    assert load_json(sidecar)["AcquisitionTime"] == expected
    log = _bids_log(caplog)
    assert log.startswith(expected_log) and bool(log) == bool(expected_log)
    assert scans_ds.rows[0] | {"randstr": ""} == {
        "filename": BOLD + ".nii.gz",
        "acq_time": "2020-01-01T12:00:00",
        "duration": "4.000",
        "operator": "Yarik",
        "randstr": "",
    }


_VOLUME_TIMING = {"VolumeTiming": [0.0, 2.0, 4.0]}


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "sidecar,nvols,expected,expected_log",
    [
        pytest.param({"RepetitionTime": 2.0}, 10, 20.0, "", id="TR-x-volumes"),
        # TR x 1 is no estimate for e.g. an anatomical
        pytest.param({"RepetitionTime": 2.0}, 1, None, "", id="single-volume"),
        pytest.param(
            {"RepetitionTime": 2.0},
            None,
            None,
            "WARNING: Failed to load",
            id="unreadable-nifti",
        ),
        *(
            pytest.param({"RepetitionTime": tr}, 10, None, "", id=f"TR-{tr}")
            for tr in (-1.0, 0, float("nan"), float("inf"), "abc")
        ),
        pytest.param(
            {"RepetitionTime": 2.0, "AcquisitionDuration": 20.5},
            10,
            20.5,
            "",
            id="AcquisitionDuration",
        ),
        # for which TR x volumes is no measure, e.g. for the 2 volumes of a
        # fieldmap's magnitude, or with dummy scans
        pytest.param(
            {"RepetitionTime": 0.488, "AcquisitionDuration": 54.0},
            2,
            54.0,
            "",
            id="AcquisitionDuration-of-fmap",
        ),
        pytest.param(
            {"RepetitionTime": 2.3, "AcquisitionDuration": 312.0},
            None,
            312.0,
            "",
            id="AcquisitionDuration-of-unreadable-nifti",
        ),
        pytest.param(
            {"AcquisitionDuration": 17.5}, 10, 17.5, "", id="AcquisitionDuration-only"
        ),
        # with VolumeTiming: the last onset + the duration of a volume, for
        # which AcquisitionDuration is the deprecated name ...
        pytest.param(
            _VOLUME_TIMING | {"AcquisitionDuration": 1.5},
            3,
            5.5,
            "",
            id="VolumeTiming",
        ),
        pytest.param(
            _VOLUME_TIMING
            | {"AcquisitionDuration": 1.5, "FrameAcquisitionDuration": 0.5},
            3,
            4.5,
            "",
            id="VolumeTiming-FrameAcquisitionDuration",
        ),
        # ... or else the median interval between onsets, here of 1, 2, 4, 1
        pytest.param(
            {"VolumeTiming": [0.0, 1.0, 3.0, 7.0, 8.0]},
            5,
            9.5,
            "",
            id="VolumeTiming-only",
        ),
        *(
            pytest.param({"VolumeTiming": onsets}, 1, None, "", id=f"onsets-{onsets}")
            for onsets in ([0.0], [], ["junk"], 5, "123", {"1": 0, "3": 0})
        ),
        # seen on OpenNeuro, although the two are mutually exclusive per
        # BIDS: TR could be of a much longer silent gap of a sparse design
        pytest.param(
            _VOLUME_TIMING | {"RepetitionTime": 5.0},
            3,
            None,
            "WARNING: ",
            id="VolumeTiming-and-TR",
        ),
        *(
            pytest.param(text, 10, None, "WARNING: Failed to load", id=text)
            for text in ("{not valid json", "[1, 2, 3]", '"a string"')
        ),
    ],
)
def test_duration_from_nifti_sidecar(
    scans_ds: ScansDataset,
    caplog: pytest.LogCaptureFixture,
    sidecar: dict[str, Any] | str,
    nvols: int | None,
    expected: float | None,
    expected_log: str,
) -> None:
    scans_ds.add_scan(sidecar=sidecar, nvols=nvols)
    nifti = scans_ds.root / "sub-01" / (BOLD + ".nii.gz")
    assert _duration_from_nifti_sidecar(str(nifti), str(scans_ds.root)) == expected
    log = _bids_log(caplog)
    assert log.startswith(expected_log) and bool(log) == bool(expected_log)


@pytest.mark.ai_generated
@pytest.mark.parametrize("tz", ["", "+01:00"])
@pytest.mark.parametrize(
    "acq_time,sidecar_times,expected",
    [
        # agreement
        ("12:00:00", ["12:00:00.000000"], []),
        # differences within ACQ_TIME_TOLERANCE are ignored
        ("12:00:00", ["12:00:00.000500"], []),
        # no (parseable) AcquisitionTime in the sidecar -- nothing to compare
        ("12:00:00", [None], []),
        ("12:00:00", [], []),
        # no acq_time to compare them to
        (None, ["12:00:05.000000"], []),
        # dcm2niix's own AcquisitionTime disagrees
        # (https://github.com/rordenlab/dcm2niix/issues/1039)
        (
            "12:00:00",
            ["12:00:02.586000"],
            [
                "acq_time 12:00:00 disagrees with AcquisitionTime 12:00:02.586000 "
                "(+2.586000 seconds) recorded by dcm2niix in f0.json"
            ],
        ),
        # several outputs (e.g. localizer planes) with different times: only
        # the earliest one corresponds to acq_time
        ("12:00:00", ["12:00:05.000000", "12:00:00.000000"], []),
        # a run straddling midnight is compared across it, not a day apart
        (
            "23:59:59.900000",
            ["00:00:00.500000"],
            ["(+0.600000 seconds)"],
        ),
    ],
)
def test_check_acq_time_congruency(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    tz: str,
    acq_time: str | None,
    sidecar_times: list[str | None],
    expected: list[str],
) -> None:
    sidecars = []
    for i, sidecar_time in enumerate(sidecar_times):
        sidecar = tmp_path / f"f{i}.json"
        save_json(sidecar, {"AcquisitionTime": sidecar_time} if sidecar_time else {})
        sidecars.append(str(sidecar))
    caplog.set_level(logging.WARNING, logger="heudiconv.bids")
    # timezone-aware datetimes come from DICOMs with TimezoneOffsetFromUTC,
    # and must be comparable to the sidecars' (local wall clock) times
    check_acq_time_congruency(
        datetime.fromisoformat("2020-01-01T" + acq_time + tz) if acq_time else None,
        sidecars,
        label="sub-01_task-rest_bold",
    )
    warnings_ = "\n".join(
        r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    )
    if not expected:
        assert not warnings_
    for e in expected:
        assert e in warnings_


@pytest.mark.ai_generated
@pytest.mark.parametrize("tz", ["", "+01:00"])
@pytest.mark.parametrize(
    "fix,acq,timestamps,sidecars,corrected,expected_log",
    [
        # https://github.com/rordenlab/dcm2niix/issues/1039: dcm2niix took
        # the time of a DICOM which is not the earliest acquired
        (
            True,
            0,
            [2.586, 0, 1],
            [2.586],
            [0],
            [
                "INFO: run: corrected AcquisitionTime recorded by dcm2niix "
                "from 12:00:02.586000 to 12:00:00.000000"
            ],
        ),
        # ... in all outputs alike, e.g. echoes
        (True, 0, [2.586, 0, 1], [2.586, 2.586], [0, 0], ["INFO: run: corrected"]),
        # ... but not asked to fix it
        (
            False,
            0,
            [2.586, 0, 1],
            [2.586],
            [2.586],
            ["WARNING: ", "--fix-acq-time` would fix it"],
        ),
        # not one of the run's DICOM timestamps: unclear what happened
        (True, 0, [2.586, 0, 1], [5], [5], ["WARNING: ", "(+5.000000 seconds)"]),
        # not all sidecars record an AcquisitionTime
        (True, 0, [2.586, 0, 1], [2.586, None], [2.586, None], ["WARNING: "]),
        # sidecars disagree among themselves
        (True, 0, [2.586, 0, 1], [1, 2.586], [1, 2.586], ["WARNING: "]),
        # acq_time is not the earliest DICOM timestamp
        (True, 1, [2.586, 0, 1], [2.586], [2.586], ["WARNING: "]),
        # no DICOM timestamps to tell by
        (True, 0, [], [2.586], [2.586], ["WARNING: "]),
    ],
)
def test_check_acq_time_congruency_fix(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    tz: str,
    fix: bool,
    acq: float,
    timestamps: list[float],
    sidecars: list[float | None],
    corrected: list[float | None],
    expected_log: list[str],
) -> None:
    start = datetime.fromisoformat("2020-01-01T12:00:00" + tz)

    def at(offset: float) -> datetime:
        return start + timedelta(seconds=offset)

    def fmt(offset: float | None) -> str | None:
        return at(offset).strftime("%H:%M:%S.%f") if offset is not None else None

    json_files = []
    for i, offset in enumerate(sidecars):
        json_file = tmp_path / f"f{i}.json"
        save_json(
            json_file, {"AcquisitionTime": fmt(offset)} if offset is not None else {}
        )
        set_readonly(str(json_file))
        json_files.append(str(json_file))
    caplog.set_level(logging.INFO, logger="heudiconv.bids")
    check_acq_time_congruency(
        at(acq),
        json_files,
        label="run",
        timestamps=[at(t) for t in timestamps],
        fix=fix,
    )
    assert [load_json(f).get("AcquisitionTime") for f in json_files] == [
        fmt(o) for o in corrected
    ]
    assert all(is_readonly(f) for f in json_files)
    log = "\n".join(
        "%s: %s" % (r.levelname, r.getMessage())
        for r in caplog.records
        if r.name == "heudiconv.bids"
    )
    for e in expected_log:
        assert e in log
    if fix:
        # nothing to suggest -- it either got fixed or is not unambiguous
        assert "--fix-acq-time" not in log


@pytest.mark.ai_generated
@pytest.mark.parametrize("tarball", ["corrupt", "of-no-duration"])
def test_populate_scans_duration_resorts_to_nifti_sidecar(
    scans_ds: ScansDataset, caplog: pytest.LogCaptureFixture, tarball: str
) -> None:
    scans_ds.add_scan(sidecar={"RepetitionTime": 2.0}, nvols=10)
    if tarball == "corrupt":
        tarball_file = scans_ds.root / "sourcedata" / "sub-01" / (BOLD + ".dicom.tgz")
        tarball_file.parent.mkdir(parents=True)
        tarball_file.write_bytes(b"not a tarball")
    else:
        # a single DICOM, stripped of the CSA header with the duration which
        # Siemens declares, so there is neither a tag nor timestamps to go by
        dcm_data = pydicom.dcmread(
            op.join(TESTS_DATA_PATH, "01-anat-scout", "0001.dcm"),
            stop_before_pixels=True,
        )
        del dcm_data[(0x0029, 0x1020)]
        pydicom.dcmwrite(scans_ds.tmp_path / "stripped.dcm", dcm_data)
        scans_ds.add_sourcedata([str(scans_ds.tmp_path / "stripped.dcm")])

    populate_scans_duration(str(scans_ds.root))

    assert scans_ds.rows[0]["duration"] == "20.000"
    assert ("Failed to read source DICOMs" in caplog.text) == (tarball == "corrupt")


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "nvols,recomputed",
    [
        (10, "20.000"),
        # a value which cannot be re-established, e.g. the one Siemens
        # declared for an anatomical whose DICOMs were not kept, is kept
        (1, "312.000"),
    ],
)
def test_populate_scans_duration_overwrite(
    scans_ds: ScansDataset, nvols: int, recomputed: str
) -> None:
    scans_ds.scans_tsv.write_text("filename\tacq_time\tduration\n")
    scans_ds.add_scan(sidecar={"RepetitionTime": 2.0}, nvols=nvols)
    scans_ds.scans_tsv.write_text(scans_ds.scans_tsv.read_text()[:-1] + "\t312.000\n")

    populate_scans_duration(str(scans_ds.root))
    assert scans_ds.rows[0]["duration"] == "312.000"

    populate_scans_duration(str(scans_ds.root), overwrite=True)
    assert scans_ds.rows[0]["duration"] == recomputed


@pytest.mark.ai_generated
def test_populate_scans_duration_no_scans_tsv(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    populate_scans_duration(str(tmp_path))
    assert "No '*_scans.tsv' files found" in caplog.text
    assert list(tmp_path.iterdir()) == []


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "flags",
    [[], ["--overwrite"], ["--fix-acq-time"], ["--overwrite", "--fix-acq-time"]],
)
def test_populate_scans_duration_cli(tmp_path: Path, flags: list[str]) -> None:
    with patch("heudiconv.main.populate_scans_duration") as populate:
        runner(
            ["--command", "populate-scans-duration", "--files", str(tmp_path), *flags]
        )
    populate.assert_called_once_with(
        str(tmp_path),
        overwrite="--overwrite" in flags,
        fix_acq_time="--fix-acq-time" in flags,
    )


@pytest.mark.ai_generated
def test_find_bids_dataset_root(tmp_path: Path) -> None:
    session_dir = tmp_path / "sub-01" / "ses-01"
    session_dir.mkdir(parents=True)
    assert _find_bids_dataset_root(str(session_dir)) is None
    (tmp_path / "dataset_description.json").write_text("{}")
    assert _find_bids_dataset_root(str(session_dir)) == str(tmp_path)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "content,in_dataset,error",
    [
        ("", True, "it has no 'filename' column"),
        ("acq_time\n2020-01-01T12:00:00\n", True, "it has no 'filename' column"),
        ("filename\tacq_time\n", False, "it is not within a BIDS dataset"),
    ],
)
def test_populate_scans_duration_skips_malformed_file(
    scans_ds: ScansDataset,
    caplog: pytest.LogCaptureFixture,
    content: str,
    in_dataset: bool,
    error: str,
) -> None:
    scans_ds.scans_tsv.write_text(content)
    # a proper one of another subject
    other = scans_ds.root / "sub-02" / "sub-02_scans.tsv"
    other.parent.mkdir()
    other.write_text("filename\tacq_time\n")
    if not in_dataset:
        (scans_ds.root / "dataset_description.json").unlink()

    populate_scans_duration(str(scans_ds.root))

    # is reported, and left as it was ...
    assert f"ERROR: Failed to populate 'duration' in {scans_ds.scans_tsv}" in (
        log := _bids_log(caplog)
    )
    assert error in log
    assert scans_ds.scans_tsv.read_text() == content
    assert sorted(os.listdir(scans_ds.scans_tsv.parent)) == ["func", "sub-01_scans.tsv"]
    # ... without getting in the way of the others
    assert _read_scans_tsv(str(other))[0] == (
        ["filename", "acq_time", "duration"] if in_dataset else ["filename", "acq_time"]
    )
    assert (scans_ds.root / "scans.json").exists() == in_dataset


_OTHER = "func/sub-01_task-other_bold.nii.gz"


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "cells,sidecar,with_dicoms,expected,expected_log",
    [
        (["", "2020-01-01T12:00:00"], None, False, "n/a", "WARNING: "),
        # not a BIDS name to look the sidecar up for
        (["func/x_bold.nii.gz", "2020-01-01T12:00:00"], None, False, "n/a", ""),
        # a short row, and one with fields beyond the header, which are kept
        ([_OTHER], None, False, "n/a", ""),
        ([_OTHER, "2020-01-01T12:00:00", "stray", ""], None, False, "n/a", ""),
        # no acq_time to check, which is no reason not to get the duration
        ([_OTHER, "junk"], None, True, "3.000", ""),
        # nor is a sidecar which cannot be checked
        *(
            (
                [_OTHER, "2020-01-01T12:00:00"],
                sidecar,
                True,
                "3.000",
                "WARNING: Failed to process",
            )
            for sidecar in ('{"AcquisitionTime": "garbage"}', "[1]", "")
        ),
    ],
)
def test_populate_scans_duration_of_odd_row(
    scans_ds: ScansDataset,
    caplog: pytest.LogCaptureFixture,
    cells: list[str],
    sidecar: str | None,
    with_dicoms: bool,
    expected: str,
    expected_log: str,
) -> None:
    scans_ds.add_row(*cells)
    if sidecar is not None:
        (scans_ds.root / "sub-01" / _OTHER).with_suffix("").with_suffix(
            ".json"
        ).write_text(sidecar)
    if with_dicoms:
        scans_ds.add_sourcedata(
            scans_ds.make_dicoms([0, 1, 2]), cells[0].removesuffix(".nii.gz")
        )
    scans_ds.add_scan(acq_time="2020-01-01T12:00:00", dicom_offsets=[2, 0, 4, 7])

    populate_scans_duration(str(scans_ds.root))

    odd, regular = scans_ds.rows
    assert odd == {
        "filename": cells[0],
        "acq_time": cells[1] if len(cells) > 1 else "n/a",
        "duration": expected,
    } | ({None: cells[2:]} if cells[2:] else {})
    assert regular["duration"] == "9.000"
    log = _bids_log(caplog)
    assert log.startswith(expected_log) and bool(log) == bool(expected_log)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "rows,encoding",
    [
        # nothing to compute, which is no reason not to add the column
        ([], "utf-8"),
        # a byte-order mark, as seen on OpenNeuro, must not stick to the
        # name of the "filename" column
        ([["meg/sub-01_task-x_meg.fif", "2000-01-01T00:00:00Z"]], "utf-8-sig"),
    ],
)
def test_populate_scans_duration_adds_column(
    scans_ds: ScansDataset, rows: list[list[str]], encoding: str
) -> None:
    scans_ds.scans_tsv.write_text("filename\tacq_time\n", encoding=encoding)
    for row in rows:
        scans_ds.add_row(*row)

    populate_scans_duration(str(scans_ds.root))

    assert scans_ds.read() == (
        ["filename", "acq_time", "duration"],
        [
            dict(zip(["filename", "acq_time", "duration"], [*row, "n/a"]))
            for row in rows
        ],
    )
    assert "duration" in load_json(scans_ds.root / "scans.json")


@pytest.mark.ai_generated
@pytest.mark.parametrize("mode", [0o664, 0o444])
def test_populate_scans_duration_preserves_permissions(
    scans_ds: ScansDataset, mode: int
) -> None:
    os.chmod(scans_ds.scans_tsv, mode)
    populate_scans_duration(str(scans_ds.root))
    assert stat.S_IMODE(os.stat(scans_ds.scans_tsv).st_mode) == mode
    assert "duration" in scans_ds.scans_tsv.read_text()


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "sidecars,stem,expected",
    [
        # the same-named one next to it
        (
            [f"sub-01/{BOLD}.json", "task-rest_bold.json"],
            "sub-01_task-rest_bold",
            f"sub-01/{BOLD}.json",
        ),
        # or else, per the Inheritance Principle, one of an ancestor
        # directory, as many datasets (e.g. on OpenNeuro) rely on
        (
            ["task-rest_bold.json"],
            "sub-01_task-rest_run-01_bold",
            "task-rest_bold.json",
        ),
        # the most specific of them
        (
            ["bold.json", "task-rest_bold.json"],
            "sub-01_task-rest_run-01_bold",
            "task-rest_bold.json",
        ),
        (["bold.json"], "sub-01_task-rest_run-01_bold", "bold.json"),
        # but not of other entities, or suffix
        (["task-other_bold.json"], "sub-01_task-rest_run-01_bold", None),
        (["task-rest_sbref.json"], "sub-01_task-rest_run-01_bold", None),
        # nor from outside of the dataset
        (["../bold.json"], "sub-01_task-rest_run-01_bold", None),
        # nor for what is not a BIDS name
        (["bold.json"], "x_bold", None),
    ],
)
def test_find_json_sidecar(
    scans_ds: ScansDataset, sidecars: list[str], stem: str, expected: str | None
) -> None:
    for sidecar in sidecars:
        save_json(scans_ds.root / sidecar, {})
    nifti = scans_ds.root / "sub-01" / "func" / f"{stem}.nii.gz"
    assert _find_json_sidecar(str(nifti), str(scans_ds.root)) == (
        expected and str(scans_ds.root / expected)
    )


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "existing_header,expected",
    [
        (["filename", "acq_time"], ["filename", "acq_time", "duration"]),
        (["filename", "acq_time", "duration"], ["filename", "acq_time", "duration"]),
        (["filename"], ["filename", "acq_time", "duration"]),
        (["acq_time"], ["acq_time", "duration", "filename"]),
        # a custom, dataset-specific column is preserved as-is
        (
            ["filename", "acq_time", "notes"],
            ["filename", "acq_time", "duration", "notes"],
        ),
    ],
)
def test_merge_scans_header(existing_header: list[str], expected: list[str]) -> None:
    additions = ["filename", "acq_time", "duration"]
    assert _merge_scans_header(existing_header, additions) == expected


@pytest.mark.ai_generated
def test_populate_bids_templates_syncs_existing_scans_json(tmp_path: Path) -> None:
    # one predating "duration" gains it, without losing any user-added key
    save_json(
        str(tmp_path / "scans.json"),
        {"acq_time": {"Description": "old"}, "MyCustomField": {"Description": "x"}},
    )
    set_readonly(str(tmp_path / "scans.json"))

    populate_bids_templates(str(tmp_path))

    assert is_readonly(str(tmp_path / "scans.json"))

    scans_json = load_json(str(tmp_path / "scans.json"))
    assert "duration" in scans_json
    assert scans_json["acq_time"] == {"Description": "old"}  # untouched
    assert scans_json["MyCustomField"] == {"Description": "x"}  # untouched


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "content,error", [("not json", JSONDecodeError), ("[1]", ValueError)]
)
def test_populate_bids_templates_errors_on_malformed_scans_json(
    tmp_path: Path, content: str, error: type[Exception]
) -> None:
    # a malformed scans.json is for the user to fix, not something to
    # silently leave out of date
    (tmp_path / "scans.json").write_text(content)
    with pytest.raises(error):
        populate_bids_templates(str(tmp_path))


@pytest.mark.ai_generated
def test_populate_bids_templates_leaves_scans_json_without_content(
    tmp_path: Path,
) -> None:
    # e.g. annexed, and not present
    (tmp_path / "scans.json").symlink_to("nowhere")
    populate_bids_templates(str(tmp_path))
    assert os.readlink(tmp_path / "scans.json") == "nowhere"


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "rewrite",
    [
        lambda fn: tuneup_bids_json_files([fn]),
        lambda fn: check_acq_time_congruency(
            datetime(2020, 1, 1, 12),
            [fn],
            label="run",
            timestamps=[datetime(2020, 1, 1, 12, 0, s) for s in (2, 0)],
            fix=True,
        ),
        add_taskname_to_infofile,
    ],
    ids=["tuneup_bids_json_files", "check_acq_time_congruency", "add_taskname"],
)
def test_sidecar_rewrites_keep_pretty_json(
    tmp_path: Path, rewrite: Callable[[str], None]
) -> None:
    # sidecars rewritten during conversion must keep numeric arrays on one
    # line, rather than reformat them one value per line -- a pure-noise diff
    # on datasets re-converted across heudiconv versions
    json_fn = tmp_path / "sub-01_task-rest_bold.json"
    shim = [1, 2, 3, 4, 5, 6, 7, 8]
    save_json(
        str(json_fn),
        {"AcquisitionTime": "12:00:02.000000", "ShimSetting": shim},
        pretty=True,
    )

    rewrite(str(json_fn))

    assert '"ShimSetting": [1, 2, 3, 4, 5, 6, 7, 8]' in json_fn.read_text()
    assert load_json(str(json_fn))["ShimSetting"] == shim
