"""Test functions in heudiconv.convert module.
"""
import os.path as op
from glob import glob

import pytest
from heudiconv.bids import BIDSError
from heudiconv.cli.run import main as runner
from heudiconv.convert import (
    DW_IMAGE_IN_FMAP_FOLDER_WARNING,
    update_complex_name,
    update_multiecho_name,
    update_uncombined_name,
)

from .utils import TESTS_DATA_PATH


def test_update_complex_name():
    """Unit testing for heudiconv.convert.update_complex_name(), which updates
    filenames with the part field if appropriate.
    """
    # Standard name update
    fn = 'sub-X_ses-Y_task-Z_run-01_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'P', 'MB', 'TE3', 'ND', 'MOSAIC']}
    file_counter = 3  # This is the third file with the same name
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_part-phase_sbref'
    out_fn_test = update_complex_name(metadata, fn, file_counter)
    assert out_fn_test == out_fn_true

    # Catch an unsupported type and *do not* update
    fn = 'sub-X_ses-Y_task-Z_run-01_phase'
    out_fn_test = update_complex_name(metadata, fn, file_counter)
    assert out_fn_test == fn

    # Data type is missing from metadata so use suffix
    fn = 'sub-X_ses-Y_task-Z_run-01_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'MB', 'TE3', 'ND', 'MOSAIC']}
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_part-3_sbref'
    out_fn_test = update_complex_name(metadata, fn, file_counter)
    assert out_fn_test == out_fn_true

    # Catch existing field with value (part is already in the filename)
    # that *does not match* metadata and raise Exception
    fn = 'sub-X_ses-Y_task-Z_run-01_part-mag_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'P', 'MB', 'TE3', 'ND', 'MOSAIC']}
    file_counter = 3
    with pytest.raises(BIDSError):
        update_complex_name(metadata, fn, file_counter)

    # Catch existing field with value (part is already in the filename)
    # that *does match* metadata and do not update
    fn = 'sub-X_ses-Y_task-Z_run-01_part-phase_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'P', 'MB', 'TE3', 'ND', 'MOSAIC']}
    file_counter = 3
    out_fn_test = update_complex_name(metadata, fn, file_counter)
    assert out_fn_test == fn


def test_update_multiecho_name():
    """Unit testing for heudiconv.convert.update_multiecho_name(), which updates
    filenames with the echo field if appropriate.
    """
    # Standard name update
    fn = 'sub-X_ses-Y_task-Z_run-01_bold'
    metadata = {'EchoTime': 0.01,
                'EchoNumber': 1}
    echo_times = [0.01, 0.02, 0.03]
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_echo-1_bold'
    out_fn_test = update_multiecho_name(metadata, fn, echo_times)
    assert out_fn_test == out_fn_true

    # EchoNumber field is missing from metadata, so use echo_times
    metadata = {'EchoTime': 0.01}
    out_fn_test = update_multiecho_name(metadata, fn, echo_times)
    assert out_fn_test == out_fn_true

    # Catch an unsupported type and *do not* update
    fn = 'sub-X_ses-Y_task-Z_run-01_phasediff'
    out_fn_test = update_multiecho_name(metadata, fn, echo_times)
    assert out_fn_test == fn

    # EchoTime is missing, but use EchoNumber (which is the first thing it checks)
    fn = 'sub-X_ses-Y_task-Z_run-01_bold'
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_echo-1_bold'
    metadata = {'EchoNumber': 1}
    echo_times = [False, 0.02, 0.03]
    out_fn_test = update_multiecho_name(metadata, fn, echo_times)
    assert out_fn_test == out_fn_true

    # Both EchoTime and EchoNumber are missing, which raises a KeyError
    fn = 'sub-X_ses-Y_task-Z_run-01_bold'
    metadata = {}
    echo_times = [False, 0.02, 0.03]
    with pytest.raises(KeyError):
        update_multiecho_name(metadata, fn, echo_times)

    # Providing echo times as something other than a list should raise a TypeError
    fn = 'sub-X_ses-Y_task-Z_run-01_bold'
    with pytest.raises(TypeError):
        update_multiecho_name(metadata, fn, set(echo_times))


def test_update_uncombined_name():
    """Unit testing for heudiconv.convert.update_uncombined_name(), which updates
    filenames with the ch field if appropriate.
    """
    # Standard name update
    fn = 'sub-X_ses-Y_task-Z_run-01_bold'
    metadata = {'CoilString': 'H1'}
    channel_names = ['H1', 'H2', 'H3', 'HEA;HEP']
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_ch-01_bold'
    out_fn_test = update_uncombined_name(metadata, fn, channel_names)
    assert out_fn_test == out_fn_true

    # CoilString field has no number in it, so we index the channel_names list
    metadata = {'CoilString': 'HEA;HEP'}
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_ch-04_bold'
    out_fn_test = update_uncombined_name(metadata, fn, channel_names)
    assert out_fn_test == out_fn_true

    # Extract the number from the CoilString and use that
    channel_names = ['H1', 'B1', 'H3', 'HEA;HEP']
    metadata = {'CoilString': 'H1'}
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_ch-01_bold'
    out_fn_test = update_uncombined_name(metadata, fn, channel_names)
    assert out_fn_test == out_fn_true

    # NOTE: Extracting the number does not protect against multiple coils with the same number
    # (but, say, different letters)
    # Note that this is still "ch-01"
    metadata = {'CoilString': 'B1'}
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_ch-01_bold'
    out_fn_test = update_uncombined_name(metadata, fn, channel_names)
    assert out_fn_test == out_fn_true

    # Providing echo times as something other than a list should raise a TypeError
    fn = 'sub-X_ses-Y_task-Z_run-01_bold'
    with pytest.raises(TypeError):
        update_uncombined_name(metadata, fn, set(channel_names))


def test_b0dwi_for_fmap(tmpdir, caplog):
    """Make sure we raise a warning when .bvec and .bval files
    are present but the modality is not dwi.
    We check it by extracting a few DICOMs from a series with
    bvals: 5 5 1500
    """
    import logging
    caplog.set_level(logging.WARNING)
    tmppath = tmpdir.strpath
    subID = 'b0dwiForFmap'
    args = (
        "-c dcm2niix -o %s -b -f test_b0dwi_for_fmap --files %s -s %s"
        % (tmpdir, op.join(TESTS_DATA_PATH, 'b0dwiForFmap'), subID)
    ).split(' ')
    runner(args)

    # assert that it raised a warning that the fmap directory will contain
    # bvec and bval files.
    expected_msg = DW_IMAGE_IN_FMAP_FOLDER_WARNING.format(folder=op.join(tmppath, 'sub-%s', 'fmap') % subID)
    assert any(expected_msg in c.message for c in caplog.records)

    # check that both 'fmap' and 'dwi' directories have been extracted and they contain
    # *.bvec and a *.bval files
    for mod in ['fmap', 'dwi']:
        assert op.isdir(op.join(tmppath, 'sub-%s', mod) % (subID))
        for ext in ['bval', 'bvec']:
            assert glob(op.join(tmppath, 'sub-%s', mod, 'sub-%s_*.%s') % (subID, subID, ext))
