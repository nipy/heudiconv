"""Test functions of heudiconv.bids.utils module.
"""

import os
import os.path as op
import re
import string
from collections import OrderedDict
from datetime import (
    datetime,
    timedelta,
)
from glob import glob
from pathlib import Path
from random import (
    choice,
    random,
    seed,
)

import nibabel
import pytest
from numpy import testing as np_testing

from heudiconv.tests.utils import TESTS_DATA_PATH
from heudiconv.utils import (
    create_tree,
    load_json,
    remove_suffix,
    save_json,
)

from .. import (
    SHIM_KEY,
    AllowedCriteriaForFmapAssignment,
    KeyInfoForForce,
    find_compatible_fmaps_for_run,
    find_compatible_fmaps_for_session,
    find_fmap_groups,
    get_key_info_for_fmap_assignment,
    get_shim_setting,
    maybe_na,
    populate_intended_for,
    select_fmap_from_compatible_groups,
    treat_age,
)


def gen_rand_label(label_size, label_seed, seed_stdout=True):
    seed(label_seed)
    rand_char = ''.join(choice(string.ascii_letters) for _ in range(label_size-1))
    seed(label_seed)
    rand_num = choice(string.digits)
    if seed_stdout:
        print(f'Seed used to generate custom label: {label_seed}')
    return rand_char + rand_num

def test_maybe_na():
    for na in '', ' ', None, 'n/a', 'N/A', 'NA':
        assert maybe_na(na) == 'n/a'
    for notna in 0, 1, False, True, 'value':
        assert maybe_na(notna) == str(notna)


def test_treat_age():
    assert treat_age(0) == '0'
    assert treat_age('0') == '0'
    assert treat_age('0000') == '0'
    assert treat_age('0000Y') == '0'
    assert treat_age('000.1Y') == '0.1'
    assert treat_age('1M') == '0.08'
    assert treat_age('12M') == '1'
    assert treat_age('0000.1') == '0.1'
    assert treat_age(0000.1) == '0.1'


SHIM_LENGTH = 6
TODAY = datetime.today()
LABEL_SEED = int.from_bytes(os.urandom(8), byteorder="big")

A_SHIM = [random() for i in range(SHIM_LENGTH)]
def test_get_shim_setting(tmpdir):
    """ Tests for get_shim_setting """
    json_dir = op.join(str(tmpdir), 'foo')
    if not op.exists(json_dir):
        os.makedirs(json_dir)
    json_name = op.join(json_dir, 'sub-foo.json')
    # 1) file with no "ShimSetting", should return None
    save_json(json_name, {})
    with pytest.raises(KeyError):
        assert get_shim_setting(json_name)

    # -file with "ShimSetting" field
    save_json(json_name, {SHIM_KEY: A_SHIM})
    assert get_shim_setting(json_name) == A_SHIM


def test_get_key_info_for_fmap_assignment(tmpdir, label_size=4, label_seed=LABEL_SEED):
    """
    Test get_key_info_for_fmap_assignment.
    
    label_size and label_seed are used for the "CustomAcquisitionLabel" matching
    parameter. label_size is the size of the random label while label_seed is 
    the seed for the random label creation.
    """

    nifti_file = op.join(TESTS_DATA_PATH, 'sample_nifti.nii.gz')
    # Get the expected parameters from the NIfTI header:
    MY_HEADER = nibabel.ni1.np.loadtxt(
        op.join(TESTS_DATA_PATH, remove_suffix(nifti_file, '.nii.gz') + '_params.txt')
    )
    json_name = op.join(TESTS_DATA_PATH, remove_suffix(nifti_file, '.nii.gz') + '.json')

    # 1) Call for a non-existing file should give an error:
    with pytest.raises(FileNotFoundError):
        assert get_key_info_for_fmap_assignment('foo.json', 'ImagingVolume')

    # 2) matching_parameters = 'Shims'
    json_name = op.join(TESTS_DATA_PATH, remove_suffix(nifti_file, '.nii.gz') + '.json')
    save_json(json_name, {SHIM_KEY: A_SHIM})      # otherwise get_key_info_for_fmap_assignment will give an error
    key_info = get_key_info_for_fmap_assignment(
        json_name, matching_parameter='Shims'
    )
    assert key_info == [A_SHIM]

    # 3) matching_parameters = 'ImagingVolume'
    key_info = get_key_info_for_fmap_assignment(
        json_name, matching_parameter='ImagingVolume'
    )
    np_testing.assert_almost_equal(key_info[0], MY_HEADER[:4], decimal=6)
    np_testing.assert_almost_equal(key_info[1], MY_HEADER[4][:3], decimal=6)

    # 4) matching_parameters = 'Force'
    key_info = get_key_info_for_fmap_assignment(
        json_name, matching_parameter='Force'
    )
    assert key_info == [KeyInfoForForce]

    # 5) matching_parameter = 'ModalityAcquisitionLabel'
    for d in ['fmap', 'func', 'dwi', 'anat']:
        Path(op.join(str(tmpdir), d)).mkdir(parents=True, exist_ok=True)
    for (dirname, fname, expected_key_info) in [
        ('fmap', 'sub-foo_acq-fmri_epi.json', 'func'),
        ('fmap', 'sub-foo_acq-bold_epi.json', 'func'),
        ('fmap', 'sub-foo_acq-func_epi.json', 'func'),
        ('fmap', 'sub-foo_acq-diff_epi.json', 'dwi'),
        ('fmap', 'sub-foo_acq-anat_epi.json', 'anat'),
        ('fmap', 'sub-foo_acq-struct_epi.json', 'anat'),
        ('func', 'sub-foo_bold.json', 'func'),
        ('dwi', 'sub-foo_dwi.json', 'dwi'),
        ('anat', 'sub-foo_T1w.json', 'anat'),
    ]:
        json_name = op.join(str(tmpdir), dirname, fname)
        save_json(json_name, {SHIM_KEY: A_SHIM})
        assert [expected_key_info] == get_key_info_for_fmap_assignment(
            json_name, matching_parameter='ModalityAcquisitionLabel'
        )

    # 6) matching_parameter = 'CustomAcquisitionLabel'
    A_LABEL = gen_rand_label(label_size, label_seed)
    for d in ['fmap', 'func', 'dwi', 'anat']:
        Path(op.join(str(tmpdir), d)).mkdir(parents=True, exist_ok=True)
        
    for (dirname, fname, expected_key_info) in [
        ('fmap', f'sub-foo_acq-{A_LABEL}_epi.json', A_LABEL),
        ('func', f'sub-foo_task-{A_LABEL}_acq-foo_bold.json', A_LABEL),
        ('dwi', f'sub-foo_acq-{A_LABEL}_dwi.json', A_LABEL),
        ('anat', f'sub-foo_acq-{A_LABEL}_T1w.json', A_LABEL),
    ]:
        json_name = op.join(str(tmpdir), dirname, fname)
        save_json(json_name, {SHIM_KEY: A_SHIM})
        assert [expected_key_info] == get_key_info_for_fmap_assignment(
            json_name, matching_parameter='CustomAcquisitionLabel'
        )

    # Finally: invalid matching_parameters:
    assert get_key_info_for_fmap_assignment(
            json_name, matching_parameter='Invalid'
        ) == []


def generate_scans_tsv(session_struct):
    """
    Generates the contents of the "_scans.tsv" file, given a session structure.
    Currently, it will have the columns "filename" and "acq_time".
    The acq_time will increase by one minute from run to run.

    Parameters:
    ----------
    session_struct : dict
        structure for the session, as a dict with modality: files

    Returns:
    -------
    scans_file_content : str
        multi-line string with the content of the file
    """
    # for each modality in session_struct (k), get the filenames:
    scans_fnames = [
        op.join(k, vk)
            for k, v in session_struct.items()
            for vk in sorted(v.keys())
            if vk.endswith('.nii.gz')
    ]
    # for each file, increment the acq_time by one minute:
    scans_file_content = ['filename\tacq_time'] + [
        '%s\t%s' % (fn, (TODAY + timedelta(minutes=i)).isoformat()) for fn, i in
        zip(scans_fnames, range(len(scans_fnames)))
    ]
    # convert to multiline string:
    return "\n".join(scans_file_content)


def create_dummy_pepolar_bids_session(session_path):
    """
    Creates a dummy BIDS session, with slim json files and empty nii.gz
    The fmap files are pepolar
    The json files have ShimSettings

    Parameters:
    ----------
    session_path : str or os.path
        path to the session (or subject) level folder

    Returns:
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
    if session_basename.startswith('ses-'):
        prefix = op.split(session_parent)[1] + '_' + session_basename
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
    anat_struct = {
        '{p}_{m}.{e}'.format(p=prefix, m=mod, e=ext): dummy_content
        for ext, dummy_content in zip(['nii.gz', 'json'], ['', {'ShimSetting': anat_shims}])
        for mod in ['T1w', 'T2w']
    }
    # -dwi:
    dwi_struct = {
        '{p}_acq-A_run-{r}_dwi.nii.gz'.format(p=prefix, r=runNo): '' for runNo in [1, 2]
    }
    dwi_struct.update({
        '{p}_acq-A_run-{r}_dwi.json'.format(p=prefix, r=runNo): {'ShimSetting': dwi_shims} for runNo in [1, 2]
    })
    # -func:
    func_struct = {
        '{p}_acq-{a}_bold.nii.gz'.format(p=prefix, a=acq): '' for acq in ['A', 'B', 'unmatched']
    }
    func_struct.update({
        '{p}_acq-A_bold.json'.format(p=prefix): {'ShimSetting': func_shims_A},
        '{p}_acq-B_bold.json'.format(p=prefix): {'ShimSetting': func_shims_B},
        '{p}_acq-unmatched_bold.json'.format(p=prefix): {
            'ShimSetting': [random() for i in range(SHIM_LENGTH)]
        },
    })
    # -fmap:
    #  * NIfTI files:
    fmap_struct = {
        '{p}_acq-{a}_dir-{d}_run-{r}_epi.nii.gz'.format(p=prefix, a=acq, d=d, r=r): ''
        for acq in ['dwi', 'fMRI']
        for d in ['AP', 'PA']
        for r in [1, 2]
    }
    #  * dwi shims:
    expected_fmap_groups = {
        '{p}_acq-dwi_run-{r}_epi'.format(p=prefix, r=r): [
            '{p}_acq-dwi_dir-{d}_run-{r}_epi.json'.format(
                p=op.join(session_path, 'fmap', prefix), d=d, r=r
            ) for d in ['AP', 'PA']
        ]
        for r in [1, 2]
    }
    fmap_struct.update({
        '{p}_acq-dwi_dir-{d}_run-{r}_epi.json'.format(p=prefix, d=d, r=r): {'ShimSetting': dwi_shims}
        for d in ['AP', 'PA']
        for r in [1, 2]
    })
    #  * func_shims (_A and _B):
    expected_fmap_groups.update({
        '{p}_acq-fMRI_run-{r}_epi'.format(p=prefix, r=r): [
            '{p}_acq-fMRI_dir-{d}_run-{r}_epi.json'.format(
                p=op.join(session_path, 'fmap', prefix), d=d, r=r
            ) for d in ['AP', 'PA']
        ]
        for r in [1, 2]
    })
    fmap_struct.update({
        '{p}_acq-fMRI_dir-{d}_run-{r}_epi.json'.format(p=prefix, d=d, r=r): {'ShimSetting': shims}
        for r, shims in {'1': func_shims_A, '2': func_shims_B}.items()
        for d in ['AP', 'PA']
    })
    # structure for the full session (init the OrderedDict as a list to preserve order):
    session_struct = OrderedDict([
        ('fmap', fmap_struct),
        ('anat', anat_struct),
        ('dwi', dwi_struct),
        ('func', func_struct),
    ])
    # add "_scans.tsv" file to the session_struct
    scans_file_content = generate_scans_tsv(session_struct)
    session_struct.update({'{p}_scans.tsv'.format(p=prefix): scans_file_content})

    create_tree(session_path, session_struct)

    # 2) Now, let's create a dict with the fmap groups compatible for each run
    # -anat: empty
    expected_compatible_fmaps = {
        '{p}_{m}.json'.format(p=op.join(session_path, 'anat', prefix), m=mod): {}
        for mod in ['T1w', 'T2w']
    }
    # -dwi: each of the runs (1, 2) is compatible with both of the dwi fmaps (1, 2):
    expected_compatible_fmaps.update({
        '{p}_acq-A_run-{r}_dwi.json'.format(p=op.join(session_path, 'dwi', prefix), r=runNo): {
            key: val for key, val in expected_fmap_groups.items() if key in [
                '{p}_acq-dwi_run-{r}_epi'.format(p=prefix, r=r) for r in [1, 2]
            ]
        }
        for runNo in [1, 2]
    })
    # -func: acq-A is compatible w/ fmap fMRI run 1; acq-2 w/ fmap fMRI run 2
    expected_compatible_fmaps.update({
        '{p}_acq-{a}_bold.json'.format(p=op.join(session_path, 'func', prefix), a=acq): {
            key: val for key, val in expected_fmap_groups.items() if key in [
                '{p}_acq-fMRI_run-{r}_epi'.format(p=prefix, r=runNo)
            ]
        }
        for runNo, acq in {'1': 'A', '2': 'B'}.items()
    })
    # -func (cont): acq-unmatched is empty
    expected_compatible_fmaps.update({
        '{p}_acq-unmatched_bold.json'.format(p=op.join(session_path, 'func', prefix)): {}
    })

    # 3) Then, let's create a dict with what we expect for the "IntendedFor":

    sub_match = re.findall('(sub-([a-zA-Z0-9]*))', session_path)
    sub_str = sub_match[0][0]
    expected_prefix = session_path.split(sub_str)[-1].split(op.sep)[-1]

    # dict, with fmap names as keys and the expected "IntendedFor" as values.
    expected_result = {
        '{p}_acq-dwi_dir-{d}_run-{r}_epi.json'.format(p=prefix, d=d, r=runNo):
        intended_for
        # (runNo=1 goes with the long list, runNo=2 goes with None):
        for runNo, intended_for in zip(
            [1, 2],
            [[op.join(expected_prefix, 'dwi', '{p}_acq-A_run-{r}_dwi.nii.gz'.format(p=prefix, r=r)) for r in [1,2]],
             None]
        )
        for d in ['AP', 'PA']
    }
    expected_result.update(
        {
            '{p}_acq-fMRI_dir-{d}_run-{r}_epi.json'.format(p=prefix, d=d, r=runNo):
            [
                op.join(expected_prefix,
                        'func',
                        '{p}_acq-{a}_bold.nii.gz'.format(p=prefix, a=acq))
            ]
            # runNo=1 goes with acq='A'; runNo=2 goes with acq='B'
            for runNo, acq in zip([1, 2], ['A', 'B'])
            for d in ['AP', 'PA']
        }
    )
    
    return session_struct, expected_result, expected_fmap_groups, expected_compatible_fmaps


def create_dummy_no_shim_settings_bids_session(session_path):
    """
    Creates a dummy BIDS session, with slim json files and empty nii.gz
    The fmap files are pepolar
    The json files don't have ShimSettings

    Parameters:
    ----------
    session_path : str or os.path
        path to the session (or subject) level folder

    Returns:
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
    if session_basename.startswith('ses-'):
        prefix = op.split(session_parent)[1] + '_' + session_basename
    else:
        prefix = session_basename

    # 1) Simulate the file structure for a session:

    # Dict with the file structure for the session.
    # All json files will be empty.
    # -anat:
    anat_struct = {
        '{p}_{m}.{e}'.format(p=prefix, m=mod, e=ext): dummy_content
        for ext, dummy_content in zip(['nii.gz', 'json'], ['', {}])
        for mod in ['T1w', 'T2w']
    }
    # -dwi:
    dwi_struct = {
        '{p}_acq-A_run-{r}_dwi.{e}'.format(p=prefix, r=runNo, e=ext): dummy_content
        for ext, dummy_content in zip(['nii.gz', 'json'], ['', {}])
        for runNo in [1, 2]
    }
    # -func:
    func_struct = {
        '{p}_acq-{a}_bold.{e}'.format(p=prefix, a=acq, e=ext): dummy_content
        for ext, dummy_content in zip(['nii.gz', 'json'], ['', {}])
        for acq in ['A', 'B']
    }
    # -fmap:
    fmap_struct = {
        '{p}_acq-{a}_dir-{d}_run-{r}_epi.{e}'.format(p=prefix, a=acq, d=d, r=r, e=ext): dummy_content
        for ext, dummy_content in zip(['nii.gz', 'json'], ['', {}])
        for acq in ['dwi', 'fMRI']
        for d in ['AP', 'PA']
        for r in [1, 2]
    }
    expected_fmap_groups = {
        '{p}_acq-{a}_run-{r}_epi'.format(p=prefix, a=acq, r=r): [
            '{p}_acq-{a}_dir-{d}_run-{r}_epi.json'.format(
                p=op.join(session_path, 'fmap', prefix), a=acq, d=d, r=r
            ) for d in ['AP', 'PA']
        ]
        for acq in ['dwi', 'fMRI']
        for r in [1, 2]
    }

    # structure for the full session (init the OrderedDict as a list to preserve order):
    session_struct = OrderedDict([
        ('fmap', fmap_struct),
        ('anat', anat_struct),
        ('dwi', dwi_struct),
        ('func', func_struct),
    ])
    # add "_scans.tsv" file to the session_struct
    scans_file_content = generate_scans_tsv(session_struct)
    session_struct.update({'{p}_scans.tsv'.format(p=prefix): scans_file_content})

    create_tree(session_path, session_struct)

    # 2) Now, let's create a dict with the fmap groups compatible for each run
    # -anat: empty
    expected_compatible_fmaps = {
        '{p}_{m}.json'.format(p=op.join(session_path, 'anat', prefix), m=mod): {}
        for mod in ['T1w', 'T2w']
    }
    # -dwi: each of the runs (1, 2) is compatible with both of the dwi fmaps (1, 2):
    expected_compatible_fmaps.update({
        '{p}_acq-A_run-{r}_dwi.json'.format(p=op.join(session_path, 'dwi', prefix), r=runNo): {
            key: val for key, val in expected_fmap_groups.items() if key in [
                '{p}_acq-dwi_run-{r}_epi'.format(p=prefix, r=r) for r in [1, 2]
            ]
        }
        for runNo in [1, 2]
    })
    # -func: each of the acq (A, B) is compatible w/ both fmap fMRI runs (1, 2)
    expected_compatible_fmaps.update({
        '{p}_acq-{a}_bold.json'.format(p=op.join(session_path, 'func', prefix), a=acq): {
            key: val for key, val in expected_fmap_groups.items() if key in [
                '{p}_acq-fMRI_run-{r}_epi'.format(p=prefix, r=r) for r in [1, 2]
           ]
        }
        for acq in ['A', 'B']
    })

    # 3) Now, let's create a dict with what we expect for the "IntendedFor":
    # NOTE: The "expected_prefix" (the beginning of the path to the
    # "IntendedFor") should be relative to the subject level (see:
    # https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data)

    sub_match = re.findall('(sub-([a-zA-Z0-9]*))', session_path)
    sub_str = sub_match[0][0]
    expected_prefix = session_path.split(sub_str)[-1].split(op.sep)[-1]

    # dict, with fmap names as keys and the expected "IntendedFor" as values.
    expected_result = {
        # (runNo=1 goes with the long list, runNo=2 goes with None):
        '{p}_acq-dwi_dir-{d}_run-{r}_epi.json'.format(p=prefix, d=d, r=runNo): intended_for
        for runNo, intended_for in zip(
            [1, 2],
            [[op.join(expected_prefix, 'dwi', '{p}_acq-A_run-{r}_dwi.nii.gz'.format(p=prefix, r=r)) for r in [1,2]],
             None]
        )
        for d in ['AP', 'PA']
    }
    expected_result.update(
        {
            # The first "fMRI" run gets all files in the "func" folder;
            # the second shouldn't get any.
            '{p}_acq-fMRI_dir-{d}_run-{r}_epi.json'.format(p=prefix, d=d, r=runNo): intended_for
            for runNo, intended_for in zip(
                [1, 2],
                [[op.join(expected_prefix, 'func', '{p}_acq-{a}_bold.nii.gz'.format(p=prefix, a=acq))
                  for acq in ['A', 'B']],
                  None]
            )
            for d in ['AP', 'PA']
        }
    )

    return session_struct, expected_result, expected_fmap_groups, expected_compatible_fmaps

def create_dummy_no_shim_settings_custom_label_bids_session(session_path, label_size=4, label_seed=LABEL_SEED):
    """
    Creates a dummy BIDS session, with slim json files and empty nii.gz
    The fmap files are pepolar
    The json files don't have ShimSettings
    The fmap files have a custom ACQ label matching:
        - TASK label for <func> modality
        - ACQ label for any other modality (e.g. <dwi>)

    Parameters:
    ----------
    session_path : str or os.path
        path to the session (or subject) level folder
    label_size : int, optional
        size of the random label
    label_seed : int, optional
        seed for the random label creation

    Returns:
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
    if session_basename.startswith('ses-'):
        prefix = op.split(session_parent)[1] + '_' + session_basename
    else:
        prefix = session_basename

    # 1) Simulate the file structure for a session:

    # Dict with the file structure for the session.
    # All json files will be empty.
    # -anat:
    anat_struct = {
        f'{prefix}_{mod}.{ext}': dummy_content
        for ext, dummy_content in zip(['nii.gz', 'json'], ['', {}])
        for mod in ['T1w', 'T2w']
    }
    # -dwi:
    label_seed += 1
    DWI_LABEL = gen_rand_label(label_size, label_seed)
    dwi_struct = {
        f'{prefix}_acq-{DWI_LABEL}_run-{runNo}_dwi.{ext}': dummy_content
        for ext, dummy_content in zip(['nii.gz', 'json'], ['', {}])
        for runNo in [1, 2]
    }
    # -func:
    label_seed += 1
    FUNC_LABEL = gen_rand_label(label_size, label_seed)
    func_struct = {
        f'{prefix}_task-{FUNC_LABEL}_acq-{acq}_bold.{ext}': dummy_content
        for ext, dummy_content in zip(['nii.gz', 'json'], ['', {}])
        for acq in ['A', 'B']
    }
    # -fmap:
    fmap_struct = {
        f'{prefix}_acq-{acq}_dir-{d}_run-{r}_epi.{ext}': dummy_content
        for ext, dummy_content in zip(['nii.gz', 'json'], ['', {}])
        for acq in [DWI_LABEL, FUNC_LABEL]
        for d in ['AP', 'PA']
        for r in [1, 2]
    }
    expected_fmap_groups = {
        f'{prefix}_acq-{acq}_run-{r}_epi': [
            f'{op.join(session_path, "fmap", prefix)}_acq-{acq}_dir-{d}_run-{r}_epi.json'
            for d in ['AP', 'PA']
        ]
        for acq in [DWI_LABEL, FUNC_LABEL]
        for r in [1, 2]
    }

    # structure for the full session (init the OrderedDict as a list to preserve order):
    session_struct = OrderedDict([
        ('fmap', fmap_struct),
        ('anat', anat_struct),
        ('dwi', dwi_struct),
        ('func', func_struct),
    ])
    # add "_scans.tsv" file to the session_struct
    scans_file_content = generate_scans_tsv(session_struct)
    session_struct.update({'{p}_scans.tsv'.format(p=prefix): scans_file_content})

    create_tree(session_path, session_struct)

    # 2) Now, let's create a dict with the fmap groups compatible for each run
    # -anat: empty
    expected_compatible_fmaps = {
        f'{op.join(session_path, "anat", prefix)}_{mod}.json': {}
        for mod in ['T1w', 'T2w']
    }
    # -dwi: each of the runs (1, 2) is compatible with both of the dwi fmaps (1, 2):
    expected_compatible_fmaps.update({
        f'{op.join(session_path, "dwi", prefix)}_acq-{DWI_LABEL}_run-{runNo}_dwi.json': {
            key: val for key, val in expected_fmap_groups.items() if key in [
                f'{prefix}_acq-{DWI_LABEL}_run-{r}_epi' for r in [1, 2]
            ]
        }
        for runNo in [1, 2]
    })
    # -func: each of the acq (A, B) is compatible w/ both fmap fMRI runs (1, 2)
    expected_compatible_fmaps.update({
        f'{op.join(session_path, "func", prefix)}_task-{FUNC_LABEL}_acq-{acq}_bold.json': {
            key: val for key, val in expected_fmap_groups.items() if key in [
                f'{prefix}_acq-{FUNC_LABEL}_run-{r}_epi' for r in [1, 2]
           ]
        }
        for acq in ['A', 'B']
    })

    # 3) Now, let's create a dict with what we expect for the "IntendedFor":
    # NOTE: The "expected_prefix" (the beginning of the path to the
    # "IntendedFor") should be relative to the subject level (see:
    # https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data)

    sub_match = re.findall('(sub-([a-zA-Z0-9]*))', session_path)
    sub_str = sub_match[0][0]
    expected_prefix = session_path.split(sub_str)[-1].split(op.sep)[-1]

    # dict, with fmap names as keys and the expected "IntendedFor" as values.
    expected_result = {
        # (runNo=1 goes with the long list, runNo=2 goes with None):
        f'{prefix}_acq-{DWI_LABEL}_dir-{d}_run-{runNo}_epi.json': intended_for
        for runNo, intended_for in zip(
            [1, 2],
            [[op.join(expected_prefix, 'dwi', f'{prefix}_acq-{DWI_LABEL}_run-{r}_dwi.nii.gz') for r in [1,2]],
             None]
        )
        for d in ['AP', 'PA']
    }
    expected_result.update(
        {
            # The first "fMRI" run gets all files in the "func" folder;
            # the second shouldn't get any.
            f'{prefix}_acq-{FUNC_LABEL}_dir-{d}_run-{runNo}_epi.json': intended_for
            for runNo, intended_for in zip(
                [1, 2],
                [[op.join(expected_prefix, 'func', f'{prefix}_task-{FUNC_LABEL}_acq-{acq}_bold.nii.gz')
                  for acq in ['A', 'B']],
                  None]
            )
            for d in ['AP', 'PA']
        }
    )

    return session_struct, expected_result, expected_fmap_groups, expected_compatible_fmaps

def create_dummy_magnitude_phase_bids_session(session_path):
    """
    Creates a dummy BIDS session, with slim json files and empty nii.gz
    The fmap files are a magnitude/phase pair
    The json files have ShimSettings
    We just need to test a very simple case to make sure the mag/phase have
    the same "IntendedFor" field:

    Parameters:
    ----------
    session_path : str or os.path
        path to the session (or subject) level folder

    Returns:
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
    if session_basename.startswith('ses-'):
        prefix = op.split(session_parent)[1] + '_' + session_basename
    else:
        prefix = session_basename

    # 1) Simulate the file structure for a session:

    # Generate some random ShimSettings:
    dwi_shims = [random() for i in range(SHIM_LENGTH)]
    func_shims_A = [random() for i in range(SHIM_LENGTH)]
    func_shims_B = [random() for i in range(SHIM_LENGTH)]

    # Dict with the file structure for the session:
    # -dwi:
    dwi_struct = {
        '{p}_acq-A_run-{r}_dwi.nii.gz'.format(p=prefix, r=runNo): '' for runNo in [1, 2]
    }
    dwi_struct.update({
        '{p}_acq-A_run-{r}_dwi.json'.format(p=prefix, r=runNo): {'ShimSetting': dwi_shims} for runNo in [1, 2]
    })
    # -func:
    func_struct = {
        '{p}_acq-{a}_bold.nii.gz'.format(p=prefix, a=acq): '' for acq in ['A', 'B', 'unmatched']
    }
    func_struct.update({
        '{p}_acq-A_bold.json'.format(p=prefix): {'ShimSetting': func_shims_A},
        '{p}_acq-B_bold.json'.format(p=prefix): {'ShimSetting': func_shims_B},
        '{p}_acq-unmatched_bold.json'.format(p=prefix): {
            'ShimSetting': [random() for i in range(SHIM_LENGTH)]
        },
    })
    # -fmap:
    #    * Case 1 in https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data
    fmap_struct = {
        '{p}_acq-case1_{s}.nii.gz'.format(p=prefix, s=suffix): ''
        for suffix in ['phasediff', 'magnitude1', 'magnitude2']
    }
    expected_fmap_groups = {
        '{p}_acq-case1'.format(p=prefix): [
            '{p}_acq-case1_phasediff.json'.format(p=op.join(session_path, 'fmap', prefix))
        ]
    }
    fmap_struct.update({
        '{p}_acq-case1_phasediff.json'.format(p=prefix): {'ShimSetting': dwi_shims}
    })
    #    * Case 2:
    fmap_struct.update({
        '{p}_acq-case2_{s}.nii.gz'.format(p=prefix, s=suffix): ''
        for suffix in ['magnitude1', 'magnitude2', 'phase1', 'phase2']
    })
    expected_fmap_groups.update({
        '{p}_acq-case2'.format(p=prefix): [
            '{p}_acq-case2_phase{n}.json'.format(
                p=op.join(session_path, 'fmap', prefix), n=n
            ) for n in [1, 2]
        ]
    })
    fmap_struct.update({
        '{p}_acq-case2_phase{n}.json'.format(p=prefix, n=n): {'ShimSetting': func_shims_A}
        for n in [1, 2]
    })
    #    * Case 3:
    fmap_struct.update({
        '{p}_acq-case3_{s}.nii.gz'.format(p=prefix, s=suffix): ''
        for suffix in ['magnitude', 'fieldmap']
    })
    expected_fmap_groups.update({
        '{p}_acq-case3'.format(p=prefix): [
            '{p}_acq-case3_fieldmap.json'.format(p=op.join(session_path, 'fmap', prefix))
        ]
    })
    fmap_struct.update({
        '{p}_acq-case3_fieldmap.json'.format(p=prefix): {'ShimSetting': func_shims_B}
    })
    # structure for the full session (init the OrderedDict as a list to preserve order):
    session_struct = OrderedDict([
        ('fmap', fmap_struct),
        ('dwi', dwi_struct),
        ('func', func_struct),
    ])
    # add "_scans.tsv" file to the session_struct
    scans_file_content = generate_scans_tsv(session_struct)
    session_struct.update({'{p}_scans.tsv'.format(p=prefix): scans_file_content})

    create_tree(session_path, session_struct)

    # 2) Now, let's create a dict with the fmap groups compatible for each run
    # -dwi: each of the runs (1, 2) is compatible with case1 fmap:
    expected_compatible_fmaps = {
        '{p}_acq-A_run-{r}_dwi.json'.format(p=op.join(session_path, 'dwi', prefix), r=runNo): {
            key: val for key, val in expected_fmap_groups.items() if key in [
                '{p}_acq-case1'.format(p=prefix)
            ]
        }
        for runNo in [1, 2]
    }
    # -func: acq-A is compatible w/ fmap case2; acq-B w/ fmap case3
    expected_compatible_fmaps.update({
        '{p}_acq-{a}_bold.json'.format(p=op.join(session_path, 'func', prefix), a=acq): {
            key: val for key, val in expected_fmap_groups.items() if key in [
                '{p}_acq-case{c}'.format(p=prefix, c=caseNo)
            ]
        }
        for caseNo, acq in {'2': 'A', '3': 'B'}.items()
    })
    # -func (cont): acq-unmatched is empty
    expected_compatible_fmaps.update({
        '{p}_acq-unmatched_bold.json'.format(p=op.join(session_path, 'func', prefix)): {}
    })

    # 3) Now, let's create a dict with what we expect for the "IntendedFor":

    sub_match = re.findall('(sub-([a-zA-Z0-9]*))', session_path)
    sub_str = sub_match[0][0]
    expected_prefix = session_path.split(sub_str)[-1].split(op.sep)[-1]

    # dict, with fmap names as keys and the expected "IntendedFor" as values.
    expected_result = {
        '{p}_acq-case1_{s}.json'.format(p=prefix, s='phasediff'):
            [op.join(expected_prefix, 'dwi', '{p}_acq-A_run-{r}_dwi.nii.gz'.format(p=prefix, r=r)) for r in [1, 2]]
    }
    expected_result.update({
        '{p}_acq-case2_phase{n}.json'.format(p=prefix, n=n):
            # populate_intended_for writes lists:
            [op.join(expected_prefix, 'func', '{p}_acq-A_bold.nii.gz'.format(p=prefix))]
        for n in [1, 2]
    })
    expected_result.update({
        '{p}_acq-case3_fieldmap.json'.format(p=prefix):
            # populate_intended_for writes lists:
            [op.join(expected_prefix, 'func', '{p}_acq-B_bold.nii.gz'.format(p=prefix))]
    })

    return session_struct, expected_result, expected_fmap_groups, expected_compatible_fmaps


# Test cases:
# A) pepolar fmaps with ShimSetting in json files
# B) same, with no ShimSetting
# C) magnitude/phase, with ShimSetting
@pytest.mark.parametrize(
    "simulation_function", [create_dummy_pepolar_bids_session,
                            create_dummy_no_shim_settings_bids_session,
                            create_dummy_magnitude_phase_bids_session]
)
def test_find_fmap_groups(tmpdir, simulation_function):
    """ Test for find_fmap_groups """
    folder = op.join(str(tmpdir), 'sub-foo')
    _, _, expected_fmap_groups, _ = simulation_function(folder)
    fmap_groups = find_fmap_groups(op.join(folder, 'fmap'))
    assert fmap_groups == expected_fmap_groups


# Test cases:
# A) pepolar fmaps with ShimSetting in json files
# B) same, with no ShimSetting
# C) magnitude/phase, with ShimSetting
@pytest.mark.parametrize(
    "simulation_function, match_param", [
        (create_dummy_pepolar_bids_session, 'Shims'),
        (create_dummy_no_shim_settings_bids_session, 'ModalityAcquisitionLabel'),
        (create_dummy_no_shim_settings_custom_label_bids_session, 'CustomAcquisitionLabel'),
        (create_dummy_magnitude_phase_bids_session, 'Shims')
    ]
)
def test_find_compatible_fmaps_for_run(tmpdir, simulation_function, match_param):
    """
    Test find_compatible_fmaps_for_run.

    Parameters:
    ----------
    tmpdir
    simulation_function : function
        function to create the directory tree and expected results
    match_param : str
        matching_parameter for assigning fmaps
    """
    folder = op.join(str(tmpdir), 'sub-foo')
    _, _, expected_fmap_groups, expected_compatible_fmaps = simulation_function(folder)
    for modality in ['anat', 'dwi', 'func']:
        for json_file in glob(op.join(folder, modality, '*.json')):
            compatible_fmaps = find_compatible_fmaps_for_run(
                json_file,
                expected_fmap_groups,
                matching_parameters=[match_param]
            )
            assert compatible_fmaps == expected_compatible_fmaps[json_file]


# Test two scenarios for each case:
# -study without sessions
# -study with sessions
# Cases:
# A) pepolar fmaps with ShimSetting in json files
# B) same, with no ShimSetting
# C) magnitude/phase, with ShimSetting
@pytest.mark.parametrize(
    "folder, expected_prefix, simulation_function, match_param", [
        (folder, expected_prefix, sim_func, mp)
        for folder, expected_prefix in zip(['no_sessions/sub-1', 'sessions/sub-1/ses-pre'], ['', 'ses-pre'])
        for sim_func, mp in [
            (create_dummy_pepolar_bids_session, 'Shims'),
            (create_dummy_no_shim_settings_bids_session, 'ModalityAcquisitionLabel'),
            (create_dummy_no_shim_settings_custom_label_bids_session, 'CustomAcquisitionLabel'),
            (create_dummy_magnitude_phase_bids_session, 'Shims')
        ]
    ]
)
def test_find_compatible_fmaps_for_session(
        tmpdir,
        folder,
        expected_prefix,
        simulation_function,
        match_param
):
    """
    Test find_compatible_fmaps_for_session.

    Parameters:
    ----------
    tmpdir
    folder : str or os.path
        path to BIDS study to be simulated, relative to tmpdir
    expected_prefix : str
        expected start of the "IntendedFor" elements
    simulation_function : function
        function to create the directory tree and expected results
    match_param : str
        matching_parameter for assigning fmaps
    """
    session_folder = op.join(str(tmpdir), folder)
    _, _, _, expected_compatible_fmaps = simulation_function(session_folder)

    compatible_fmaps = find_compatible_fmaps_for_session(session_folder, matching_parameters=[match_param])

    assert compatible_fmaps == expected_compatible_fmaps


# Test two scenarios for each case:
# -study without sessions
# -study with sessions
# Cases:
# A) pepolar fmaps with ShimSetting in json files
# B) same, with no ShimSetting
# C) magnitude/phase, with ShimSetting
@pytest.mark.parametrize(
    "folder, expected_prefix, simulation_function", [
        (folder, expected_prefix, sim_func)
        for folder, expected_prefix in zip(['no_sessions/sub-1', 'sessions/sub-1/ses-pre'], ['', 'ses-pre'])
        for sim_func in [create_dummy_pepolar_bids_session,
                         create_dummy_no_shim_settings_bids_session,
                         create_dummy_magnitude_phase_bids_session]
    ]
)
def test_select_fmap_from_compatible_groups(tmpdir, folder, expected_prefix, simulation_function):
    """Test select_fmap_from_compatible_groups"""
    session_folder = op.join(str(tmpdir), folder)
    _, _, _, expected_compatible_fmaps = simulation_function(session_folder)

    for json_file, fmap_groups in expected_compatible_fmaps.items():
        for criterion in AllowedCriteriaForFmapAssignment:
            if not op.dirname(json_file).endswith('fmap'):
                selected_fmap = select_fmap_from_compatible_groups(
                    json_file,
                    fmap_groups,
                    criterion=criterion
                )
            # when the criterion is 'First', you should get the first of
            # the compatible_fmaps (for that json_file), if it is 'Closest',
            # it should be the last one (the fmaps are "run" at the
            # beginning of the session)
            if selected_fmap:
                if criterion == 'First':
                    assert selected_fmap == sorted(expected_compatible_fmaps[json_file])[0]
                elif criterion == 'Closest':
                    assert selected_fmap == sorted(expected_compatible_fmaps[json_file])[-1]
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
    "folder, expected_prefix, simulation_function, match_param", [
        (folder, expected_prefix, sim_func, mp)
        for folder, expected_prefix in zip(['no_sessions/sub-1', 'sessions/sub-1/ses-pre'], ['', 'ses-pre'])
        for sim_func, mp in [
            (create_dummy_pepolar_bids_session, 'Shims'),
            (create_dummy_no_shim_settings_bids_session, 'ModalityAcquisitionLabel'),
            (create_dummy_no_shim_settings_custom_label_bids_session, 'CustomAcquisitionLabel'),
            (create_dummy_magnitude_phase_bids_session, 'Shims')
        ]
    ]
)
def test_populate_intended_for(
    tmpdir,
    folder,
    expected_prefix,
    simulation_function,
    match_param
):
    """
    Test populate_intended_for.
    Parameters:
    ----------
    tmpdir
    folder : str or os.path
        path to BIDS study to be simulated, relative to tmpdir
    expected_prefix : str
        expected start of the "IntendedFor" elements
    simulation_function : function
        function to create the directory tree and expected results
    match_param : str
        matching_parameter for assigning fmaps
    """

    session_folder = op.join(str(tmpdir), folder)
    session_struct, expected_result, _, _ = simulation_function(session_folder)
    populate_intended_for(session_folder, matching_parameters=match_param, criterion='First')

    # Now, loop through the jsons in the fmap folder and make sure it matches
    # the expected result:
    fmap_folder = op.join(session_folder, 'fmap')
    for j in session_struct['fmap'].keys():
        if j.endswith('.json'):
            assert j in expected_result.keys()
            data = load_json(op.join(fmap_folder, j))
            if expected_result[j]:
                assert data['IntendedFor'] == expected_result[j]
                # Also, make sure the run with random shims is not here:
                # (It is assured by the assert above, but let's make it
                # explicit)
                run_prefix = j.split('_acq')[0]
                assert '{p}_acq-unmatched_bold.nii.gz'.format(p=run_prefix) not in data['IntendedFor']
            else:
                assert 'IntendedFor' not in data.keys()
