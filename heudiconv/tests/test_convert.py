"""Test functions in heudiconv.convert module.
"""
from os import path as op
import pytest

from heudiconv import convert
from heudiconv.bids import BIDSError


def test_update_complex_name():
    """Unit testing for heudiconv.convert.update_complex_name(), which updates
    filenames with the part field if appropriate.
    """
    # Standard name update
    fn = 'sub-X_ses-Y_task-Z_run-01_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'P', 'MB', 'TE3', 'ND', 'MOSAIC']}
    suffix = 3
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_part-phase_sbref'
    out_fn_test = convert.update_complex_name(metadata, fn, suffix)
    assert out_fn_test == out_fn_true
    # Catch an unsupported type and *do not* update
    fn = 'sub-X_ses-Y_task-Z_run-01_phase'
    out_fn_test = convert.update_complex_name(metadata, fn, suffix)
    assert out_fn_test == fn
    # Data type is missing from metadata so use suffix
    fn = 'sub-X_ses-Y_task-Z_run-01_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'MB', 'TE3', 'ND', 'MOSAIC']}
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_part-3_sbref'
    out_fn_test = convert.update_complex_name(metadata, fn, suffix)
    assert out_fn_test == out_fn_true
    # Catch existing field with value that *does not match* metadata
    # and raise Exception
    fn = 'sub-X_ses-Y_task-Z_run-01_part-mag_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'P', 'MB', 'TE3', 'ND', 'MOSAIC']}
    suffix = 3
    with pytest.raises(BIDSError):
        assert convert.update_complex_name(metadata, fn, suffix)


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
    out_fn_test = convert.update_multiecho_name(metadata, fn, echo_times)
    assert out_fn_test == out_fn_true
    # EchoNumber field is missing from metadata, so use echo_times
    metadata = {'EchoTime': 0.01}
    out_fn_test = convert.update_multiecho_name(metadata, fn, echo_times)
    assert out_fn_test == out_fn_true
    # Catch an unsupported type and *do not* update
    fn = 'sub-X_ses-Y_task-Z_run-01_phasediff'
    out_fn_test = convert.update_multiecho_name(metadata, fn, echo_times)
    assert out_fn_test == fn


def test_update_uncombined_name():
    """Unit testing for heudiconv.convert.update_uncombined_name(), which updates
    filenames with the ch field if appropriate.
    """
    # Standard name update
    fn = 'sub-X_ses-Y_task-Z_run-01_bold'
    metadata = {'CoilString': 'H1'}
    channel_names = ['H1', 'H2', 'H3', 'HEA;HEP']
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_ch-01_bold'
    out_fn_test = convert.update_uncombined_name(metadata, fn, channel_names)
    assert out_fn_test == out_fn_true
    # CoilString field has no number in it
    metadata = {'CoilString': 'HEA;HEP'}
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_ch-04_bold'
    out_fn_test = convert.update_uncombined_name(metadata, fn, channel_names)
    assert out_fn_test == out_fn_true


# Test two scenarios for each case:
# -study without sessions
# -study with sessions
@pytest.mark.parametrize(
    "subjects, sesID, expected_session_folder", [
        (['Jason', 'Bourne'], None, 'sub-{sID}'),
        ('Bourne', 'Treadstone', 'sub-{{sID}}{sep}ses-{{ses}}'.format(sep=op.sep)),
    ]
)
def test_convert(tmpdir, monkeypatch, capfd,
                 subjects, sesID, expected_session_folder):
    """
    Test convert

    For now, I'm just going to test that the call to populate_intended_for is
    done with the correct argument.
    More tests can be added here.
    """

    def mock_populate_intended_for(session):
        """
        Pretend we run populate_intended_for, but just print out the argument.
        """
        print('session: {}'.format(session))
        return
    monkeypatch.setattr(convert, "populate_intended_for", mock_populate_intended_for)

    outdir = op.join(str(tmpdir), 'foo')
    outfolder = op.join(outdir, 'sub-{sID}', 'ses-{ses}' if sesID else '')
    sub_ses = 'sub-{sID}' + ('_ses-{ses}' if sesID else '')

    # items are a list of tuples, with each tuple having three elements:
    #   prefix, outtypes, item_dicoms
    items = [
        (op.join(outfolder, 'anat', sub_ses + '_T1w').format(sID=s, ses=sesID), ('',), [])
        for s in subjects
    ]

    convert.convert(items,
                    converter='',
                    scaninfo_suffix='.json',
                    custom_callable=None,
                    with_prov=None,
                    bids_options=[],
                    outdir=outdir,
                    min_meta=True,
                    overwrite=False)
    output = capfd.readouterr()
    assert ['session: sub-{}'.format(s) in output.out for s in subjects]
