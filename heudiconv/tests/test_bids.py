import re
import os
import os.path as op
from random import random

from heudiconv.utils import (
    load_json,
    save_json,
    create_tree,
)
from heudiconv.bids import (
    populate_intended_for,
    get_shim_setting,
    SHIM_KEY,
)

import pytest

SHIM_LENGTH = 6


# Test scenarios:
# -file with "ShimSetting" field
# -file with no "ShimSetting", in "foo" dir, should return "foo"
# -file with no "ShimSetting", in "fmap" dir, acq-CatchThis, should return
#       "CatchThis"
# -file with no "ShimSetting", in "fmap" dir, acq-fMRI, should return "func"
A_SHIM = ['{0:.4f}'.format(random()) for i in range(SHIM_LENGTH)]
@pytest.mark.parametrize(
    "fname, content, expected_return", [
        (op.join('foo', 'bar.json'), {SHIM_KEY: A_SHIM}, A_SHIM),
        (op.join('dont_catch_this', 'foo', 'bar.json'), {}, 'foo'),
        (op.join('dont_catch_this', 'fmap', 'bar_acq-CatchThis.json'), {}, 'CatchThis'),
        (op.join('dont_catch_this', 'fmap', 'bar_acq-fMRI.json'), {}, 'func'),
    ]
)
def test_get_shim_setting(tmpdir, fname, content, expected_return):
    """ Tests for get_shim_setting """
    json_name = op.join(str(tmpdir), fname)
    json_dir = op.dirname(json_name)
    if not op.exists(json_dir):
        os.makedirs(json_dir)
    save_json(json_name, content)
    assert get_shim_setting(json_name) == expected_return


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
    """
    session_parent, session_basename = op.split(session_path)
    if session_basename.startswith('ses-'):
        prefix = op.split(session_parent)[1] + '_' + session_basename
    else:
        prefix = session_basename

    # 1) Simulate the file structure for a session:

    # Generate some random ShimSettings:
    dwi_shims = ['{0:.4f}'.format(random()) for i in range(SHIM_LENGTH)]
    func_shims_A = ['{0:.4f}'.format(random()) for i in range(SHIM_LENGTH)]
    func_shims_B = ['{0:.4f}'.format(random()) for i in range(SHIM_LENGTH)]

    # Dict with the file structure for the session:
    # -anat:
    anat_struct = {
        '{p}_{m}.{e}'.format(p=prefix, m=mod, e=ext): dummy_content
        for ext, dummy_content in zip(['nii.gz', 'json'], ['', {}])
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
            'ShimSetting': ['{0:.4f}'.format(random()) for i in range(SHIM_LENGTH)]
        },
    })
    # -fmap:
    fmap_struct = {
        '{p}_acq-{a}_dir-{d}_run-{r}_epi.nii.gz'.format(p=prefix, a=acq, d=d, r=r): ''
        for acq in ['dwi', 'fMRI']
        for d in ['AP', 'PA']
        for r in [1, 2]
    }
    fmap_struct.update({
        '{p}_acq-dwi_dir-{d}_run-{r}_epi.json'.format(p=prefix, d=d, r=r): {'ShimSetting': dwi_shims}
        for d in ['AP', 'PA']
        for r in [1, 2]
    })
    fmap_struct.update({
        '{p}_acq-fMRI_dir-{d}_run-{r}_epi.json'.format(p=prefix, d=d, r=r): {'ShimSetting': shims}
        for r, shims in {'1': func_shims_A, '2': func_shims_B}.items()
        for d in ['AP', 'PA']
    })
    # structure for the full session:
    session_struct = {
        'anat': anat_struct,
        'dwi': dwi_struct,
        'func': func_struct,
        'fmap': fmap_struct
    }

    create_tree(session_path, session_struct)

    # 2) Now, let's create a dict with what we expect for the "IntendedFor":

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
    
    return session_struct, expected_result


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
    """
    session_parent, session_basename = op.split(session_path)
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
    # structure for the full session:
    session_struct = {
        'anat': anat_struct,
        'dwi': dwi_struct,
        'func': func_struct,
        'fmap': fmap_struct
    }

    create_tree(session_path, session_struct)

    # 2) Now, let's create a dict with what we expect for the "IntendedFor":

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

    return session_struct, expected_result


# Test two scenarios for each case:
# -study without sessions
# -study with sessions
# Cases:
# A) pepolar fmaps with ShimSetting in json files
# B) same, with no ShimSetting
# TODO: Do the same with a GRE fmap (magnitude/phase, etc.)
# The "expected_prefix" (the beginning of the path to the "IntendedFor")
# should be relative to the subject level
@pytest.mark.parametrize(
    "folder, expected_prefix, simulation_function", [
        (folder, expected_prefix, sim_func)
        for folder, expected_prefix in zip(['no_sessions/sub-1', 'sessions/sub-1/ses-pre'], ['', 'ses-pre'])
        for sim_func in [create_dummy_pepolar_bids_session, create_dummy_no_shim_settings_bids_session]
    ]
)
def test_populate_intended_for(tmpdir, folder, expected_prefix, simulation_function):
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
    """

    session_folder = op.join(str(tmpdir), folder)
    session_struct, expected_result = simulation_function(session_folder)
    populate_intended_for(session_folder)

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
