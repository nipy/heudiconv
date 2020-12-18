import json
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


# TODO: Do the same with a GRE fmap (magnitude/phase, etc.)
# TODO: Add test for when there are no ShimSettings
def create_dummy_pepolar_bids_session(session_path):
    """
    Creates a dummy BIDS session, with slim json files and empty nii.gz
    The fmap files are pepolar
    The json files have ShimSettings

    Parameters:
    ----------
    session_path : str or os.path
        path to the session (or subject) level folder
    """
    session_parent, session_basename = op.split(session_path)
    if session_basename.startswith('ses-'):
        prefix = op.split(session_parent)[1] + '_' + session_basename
    else:
        prefix = session_basename

    # Generate some random ShimSettings:
    dwi_shims = ['{0:.4f}'.format(random()) for i in range(SHIM_LENGTH)]
    func_shims_A = ['{0:.4f}'.format(random()) for i in range(SHIM_LENGTH)]
    func_shims_B = ['{0:.4f}'.format(random()) for i in range(SHIM_LENGTH)]

    # Dict with the file structure for the session:
    # -anat:
    anat_struct = {
        '{p}_{m}.nii.gz'.format(p=prefix, m=mod): '' for mod in ['T1w', 'T2w']
    }
    anat_struct.update({
        # empty json:
        '{p}_{m}.json'.format(p=prefix, m=mod): {} for mod in ['T1w', 'T2w']
    })
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
    return session_struct


# Test two scenarios:
# -study without sessions
# -study with sessions
# The "expected_prefix" (the beginning of the path to the "IntendedFor")
# should be relative to the subject level
@pytest.mark.parametrize(
    "folder, expected_prefix", [
        ('no_sessions/sub-1', ''),
        ('sessions/sub-1/ses-pre', 'ses-pre')
    ]
)
def test_populate_intended_for(tmpdir, folder, expected_prefix):
    """
    Test populate_intended_for.
    Parameters:
    ----------
    tmpdir
    folder : str or os.path
        path to BIDS study to be simulated, relative to tmpdir
    expected_prefix : str
        expected start of the "IntendedFor" elements
    """

    session_folder = op.join(str(tmpdir), folder)
    session_struct = create_dummy_pepolar_bids_session(session_folder)
    populate_intended_for(session_folder)

    run_prefix = 'sub-1' + ('_' + expected_prefix if expected_prefix else '')
    # dict, with fmap names as keys and the expected "IntendedFor" as values.
    expected_result = {
        '{p}_acq-dwi_dir-{d}_run-{r}_epi.json'.format(p=run_prefix, d=d, r=runNo):
        intended_for
        # (runNo=1 goes with the long list, runNo=2 goes with None):
        for runNo, intended_for in zip(
            [1, 2],
            [[op.join(expected_prefix, 'dwi', '{p}_acq-A_run-{r}_dwi.nii.gz'.format(p=run_prefix, r=r)) for r in [1,2]],
             None]
        )
        for d in ['AP', 'PA']
    }
    expected_result.update(
        {
            '{p}_acq-fMRI_dir-{d}_run-{r}_epi.json'.format(p=run_prefix, d=d, r=runNo):
            [
                op.join(expected_prefix,
                        'func',
                        '{p}_acq-{a}_bold.nii.gz'.format(p=run_prefix, a=acq))
            ]
            # runNo=1 goes with acq='A'; runNo=2 goes with acq='B'
            for runNo, acq in zip([1, 2], ['A', 'B'])
            for d in ['AP', 'PA']
        }
    )

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
                assert '{p}_acq-unmatched_bold.nii.gz'.format(p=run_prefix) not in data['IntendedFor']
            else:
                assert 'IntendedFor' not in data.keys()
