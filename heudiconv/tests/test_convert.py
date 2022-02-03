"""Test functions in heudiconv.convert module.
"""
import pytest
from heudiconv.bids import BIDSError
from heudiconv.convert import (
    update_complex_name,
    update_multiecho_name,
    update_uncombined_name,
)


def test_update_complex_name():
    """Unit testing for heudiconv.convert.update_complex_name(), which updates
    filenames with the rec field if appropriate.
    """
    # Standard name update
    fn = 'sub-X_ses-Y_task-Z_run-01_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'P', 'MB', 'TE3', 'ND', 'MOSAIC']}
    suffix = 3
    out_fn_true = 'sub-X_ses-Y_task-Z_rec-phase_run-01_sbref'
    out_fn_test = update_complex_name(metadata, fn, suffix)
    assert out_fn_test == out_fn_true

    # Catch an unsupported type and *do not* update
    fn = 'sub-X_ses-Y_task-Z_run-01_phase'
    out_fn_test = update_complex_name(metadata, fn, suffix)
    assert out_fn_test == fn

    # Data type is missing from metadata so use suffix
    fn = 'sub-X_ses-Y_task-Z_run-01_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'MB', 'TE3', 'ND', 'MOSAIC']}
    out_fn_true = 'sub-X_ses-Y_task-Z_rec-3_run-01_sbref'
    out_fn_test = update_complex_name(metadata, fn, suffix)
    assert out_fn_test == out_fn_true

    # Catch existing field with value that *does not match* metadata
    # and raise Exception
    fn = 'sub-X_ses-Y_task-Z_rec-magnitude_run-01_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'P', 'MB', 'TE3', 'ND', 'MOSAIC']}
    suffix = 3
    with pytest.raises(BIDSError):
        assert update_complex_name(metadata, fn, suffix)


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
