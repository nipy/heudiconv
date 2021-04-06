"""Test functions in heudiconv.bids module.
"""

import re
import os
import os.path as op
from random import random
from datetime import (datetime,
                      timedelta,
                      )
from collections import namedtuple
from glob import glob

import nibabel

from heudiconv.utils import (
    load_json,
    save_json,
    create_tree,
)
from heudiconv.bids import (
    maybe_na,
    treat_age,
    find_fmap_groups,
    populate_intended_for,
    get_shim_setting,
    get_key_info_for_fmap_assignment,
    find_compatible_fmaps_for_run,
    find_compatible_fmaps_for_session,
    select_fmap_from_compatible_groups,
    SHIM_KEY,
    AllowedCriteriaForFmapAssignment,
)

import pytest

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


def test_get_key_info_for_fmap_assignment(tmpdir, monkeypatch):
    """
    Test get_key_info_for_fmap_assignment
    """

    # Stuff needed to mock reading of a NIfTI file header:

    # affines (qforms/sforms) are 4x4 matrices
    MY_AFFINE = [[random() for i in range(4)] for j in range(4)]
    # dims are arrays with 8 elements with the first one indicating the number
    # of dims in the image; remaining elements are 1:
    MY_DIM = [4] + [round(256 * random()) for i in range(4)] + [1] * 3
    # We use namedtuples so that we can use the .dot notation, to mock
    # nibabel headers:
    MyHeader = namedtuple('MyHeader', 'affine dim')
    MY_HEADER = MyHeader(MY_AFFINE, MY_DIM)
    MyMockNifti = namedtuple('MyMockNifti', 'header')

    def mock_nibabel_load(file):
        """
        Pretend we run nibabel.load, but return only a header with just a few fields
        """
        return MyMockNifti(MY_HEADER)
    monkeypatch.setattr(nibabel, "load", mock_nibabel_load)

    json_name = op.join(str(tmpdir), 'foo.json')

    # 1) Call for a non-existing file should give an error:
    with pytest.raises(FileNotFoundError):
        assert get_key_info_for_fmap_assignment('foo.json')

    # 2) matching_parameter = 'Shims'
    save_json(json_name, {SHIM_KEY: A_SHIM})      # otherwise get_key_info_for_fmap_assignment will give an error
    key_info = get_key_info_for_fmap_assignment(
        json_name, matching_parameter='Shims'
    )
    assert key_info == [A_SHIM]

    # 3) matching_parameter = 'ImagingVolume'
    key_info = get_key_info_for_fmap_assignment(
        json_name, matching_parameter='ImagingVolume'
    )
    assert key_info == [MY_AFFINE, MY_DIM[1:3]]

    # 4) invalid matching_parameter:
    with pytest.raises(ValueError):
        assert get_key_info_for_fmap_assignment(
            json_name, matching_parameter='Invalid'
        )


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
            for vk in v.keys()
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
    # structure for the full session:
    session_struct = {
        'fmap': fmap_struct,
        'anat': anat_struct,
        'dwi': dwi_struct,
        'func': func_struct,
    }
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
    expected_fmap_groups = {
        '{p}_acq-{a}_run-{r}_epi'.format(p=prefix, a=acq, r=r): [
            '{p}_acq-{a}_dir-{d}_run-{r}_epi.json'.format(
                p=op.join(session_path, 'fmap', prefix), a=acq, d=d, r=r
            ) for d in ['AP', 'PA']
        ]
        for acq in ['dwi', 'fMRI']
        for r in [1, 2]
    }

    # structure for the full session:
    session_struct = {
        'fmap': fmap_struct,
        'anat': anat_struct,
        'dwi': dwi_struct,
        'func': func_struct,
    }
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
    # structure for the full session:
    session_struct = {
        'fmap': fmap_struct,
        'dwi': dwi_struct,
        'func': func_struct,
    }
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
    "simulation_function", [create_dummy_pepolar_bids_session,
                            create_dummy_no_shim_settings_bids_session,
                            create_dummy_magnitude_phase_bids_session]
)
def test_find_compatible_fmaps_for_run(tmpdir, simulation_function):
    """
    Test find_compatible_fmaps_for_run.

    Parameters:
    ----------
    tmpdir
    simulation_function : function
        function to create the directory tree and expected results
    """
    folder = op.join(str(tmpdir), 'sub-foo')
    _, _, expected_fmap_groups, expected_compatible_fmaps = simulation_function(folder)
    for modality in ['anat', 'dwi', 'func']:
        for json_file in glob(op.join(folder, modality, '*.json')):
            compatible_fmaps = find_compatible_fmaps_for_run(
                json_file,
                expected_fmap_groups,
                matching_parameter='Shims'
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
    "folder, expected_prefix, simulation_function", [
        (folder, expected_prefix, sim_func)
        for folder, expected_prefix in zip(['no_sessions/sub-1', 'sessions/sub-1/ses-pre'], ['', 'ses-pre'])
        for sim_func in [create_dummy_pepolar_bids_session,
                         create_dummy_no_shim_settings_bids_session,
                         create_dummy_magnitude_phase_bids_session]
    ]
)
def test_find_compatible_fmaps_for_session(tmpdir, folder, expected_prefix, simulation_function):
    """
    Test find_compatible_fmaps_for_session.

    Parameters:
    ----------
    tmpdir
    simulation_function : function
        function to create the directory tree and expected results
    """
    session_folder = op.join(str(tmpdir), folder)
    _, _, _, expected_compatible_fmaps = simulation_function(session_folder)

    compatible_fmaps = find_compatible_fmaps_for_session(session_folder, matching_parameter='Shims')

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
                    assert selected_fmap == list(expected_compatible_fmaps[json_file])[0]
                elif criterion == 'Closest':
                    assert selected_fmap == list(expected_compatible_fmaps[json_file])[-1]
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
    "folder, expected_prefix, simulation_function", [
        (folder, expected_prefix, sim_func)
        for folder, expected_prefix in zip(['no_sessions/sub-1', 'sessions/sub-1/ses-pre'], ['', 'ses-pre'])
        for sim_func in [create_dummy_pepolar_bids_session,
                         create_dummy_no_shim_settings_bids_session,
                         create_dummy_magnitude_phase_bids_session]
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
    session_struct, expected_result, _, _ = simulation_function(session_folder)
    populate_intended_for(session_folder, matching_parameter='Shims', criterion='First')

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
