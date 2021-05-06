"""Test functions in heudiconv.convert module.
"""
import os.path as op
from glob import glob

import pytest
from .utils import TESTS_DATA_PATH

from heudiconv.convert import (update_complex_name,
                               update_multiecho_name,
                               update_uncombined_name,
                               DW_IMAGE_IN_FMAP_FOLDER_WARNING,
                               )
import heudiconv.convert
from heudiconv.bids import BIDSError
from heudiconv.utils import load_heuristic
from heudiconv.cli.run import main as runner


def test_update_complex_name():
    """Unit testing for heudiconv.convert.update_complex_name(), which updates
    filenames with the part field if appropriate.
    """
    # Standard name update
    fn = 'sub-X_ses-Y_task-Z_run-01_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'P', 'MB', 'TE3', 'ND', 'MOSAIC']}
    suffix = 3
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_part-phase_sbref'
    out_fn_test = update_complex_name(metadata, fn, suffix)
    assert out_fn_test == out_fn_true
    # Catch an unsupported type and *do not* update
    fn = 'sub-X_ses-Y_task-Z_run-01_phase'
    out_fn_test = update_complex_name(metadata, fn, suffix)
    assert out_fn_test == fn
    # Data type is missing from metadata so use suffix
    fn = 'sub-X_ses-Y_task-Z_run-01_sbref'
    metadata = {'ImageType': ['ORIGINAL', 'PRIMARY', 'MB', 'TE3', 'ND', 'MOSAIC']}
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_part-3_sbref'
    out_fn_test = update_complex_name(metadata, fn, suffix)
    assert out_fn_test == out_fn_true
    # Catch existing field with value that *does not match* metadata
    # and raise Exception
    fn = 'sub-X_ses-Y_task-Z_run-01_part-mag_sbref'
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
    # CoilString field has no number in it
    metadata = {'CoilString': 'HEA;HEP'}
    out_fn_true = 'sub-X_ses-Y_task-Z_run-01_ch-04_bold'
    out_fn_test = update_uncombined_name(metadata, fn, channel_names)
    assert out_fn_test == out_fn_true


def test_b0dwi_for_fmap(tmpdir, capfd):
    """Make sure we raise a warning when .bvec and .bval files
    are present but the modality is not dwi.
    We check it by extracting a few DICOMs from a series with
    bvals: 5 5 1500
    """
    tmppath = tmpdir.strpath
    subID = 'b0dwiForFmap'
    args = (
        "-c dcm2niix -o %s -b -f test_b0dwi_for_fmap --files %s -s %s"
        % (tmpdir, op.join(TESTS_DATA_PATH, 'b0dwiForFmap'), subID)
    ).split(' ')
    runner(args)

    # assert that it raised a warning that the fmap directory will contain
    # bvec and bval files.
    output = capfd.readouterr().err.split('\n')
    expected_msg = DW_IMAGE_IN_FMAP_FOLDER_WARNING.format(folder=op.join(tmppath, 'sub-%s', 'fmap') % subID)
    assert [o for o in output if expected_msg in o]

    # check that both 'fmap' and 'dwi' directories have been extracted and they contain
    # *.bvec and a *.bval files
    for mod in ['fmap', 'dwi']:
        assert op.isdir(op.join(tmppath, 'sub-%s', mod) % (subID))
        for ext in ['bval', 'bvec']:
            assert glob(op.join(tmppath, 'sub-%s', mod, 'sub-%s_*.%s') % (subID, subID, ext))


# Test two scenarios for each case:
# -study without sessions
# -study with sessions
@pytest.mark.parametrize(
    "subjects, sesID, expected_session_folder", [
        (['Jason', 'Bourne'], None, 'sub-{sID}'),
        (['Bourne'], 'Treadstone', op.join('sub-{{sID}}', 'ses-{{ses}}')),
    ]
)
# Two possibilities: with or without heuristics:
@pytest.mark.parametrize(
    "heuristic", ['example', None]       # heuristics/example.py
)
def test_populate_intended_for(tmpdir, monkeypatch, capfd,
                 subjects, sesID, expected_session_folder,
                 heuristic):
    """
    Test convert

    For now, I'm just going to test that the call to populate_intended_for is
    done with the correct argument.
    More tests can be added here.
    """

    def mock_populate_intended_for(session, matching_parameter='Shims', criterion='Closest'):
        """
        Pretend we run populate_intended_for, but just print out the arguments.
        """
        print('session: {}'.format(session))
        print('matching_parameter: {}'.format(matching_parameter))
        print('criterion: {}'.format(criterion))
        return
    # mock the "populate_intended_for":
    monkeypatch.setattr(
        heudiconv.convert, "populate_intended_for", mock_populate_intended_for
    )

    outdir = op.join(str(tmpdir), 'foo')
    outfolder = op.join(outdir, 'sub-{sID}', 'ses-{ses}') if sesID else op.join(outdir,'sub-{sID}')
    sub_ses = 'sub-{sID}' + ('_ses-{ses}' if sesID else '')

    # items are a list of tuples, with each tuple having three elements:
    #   prefix, outtypes, item_dicoms
    items = [
        (op.join(outfolder, 'anat', sub_ses + '_T1w').format(sID=s, ses=sesID), ('',), [])
        for s in subjects
    ]

    heuristic = load_heuristic('example') if heuristic else None
    heudiconv.convert.convert(items,
            converter='',
            scaninfo_suffix='.json',
            custom_callable=None,
            populate_intended_for_opts=getattr(heuristic, 'POPULATE_INTENDED_FOR_OPTS', None),
            with_prov=None,
            bids_options=[],
            outdir=outdir,
            min_meta=True,
            overwrite=False)
    output = capfd.readouterr()
    if heuristic:
        assert all([
            "\n".join([
                "session: " + outfolder.format(sID=s, ses=sesID),
                # "ImagingVolume" is defined in heuristic file; "Shims" is the default
                "matching_parameter: " + ("ImagingVolume" if heuristic else "Shims"),
                "criterion: Closest"
            ]) in output.out
            for s in subjects
        ])
    else:
        # If there was no heuristic, make sure populate_intended_for was not called
        assert not output.out
