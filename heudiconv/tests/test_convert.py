"""Test functions in heudiconv.convert module.
"""
from __future__ import annotations

from glob import glob
import os.path as op
from pathlib import Path
from typing import Optional

import pytest

from heudiconv.bids import BIDSError
from heudiconv.cli.run import main as runner
import heudiconv.convert
from heudiconv.convert import (
    DW_IMAGE_IN_FMAP_FOLDER_WARNING,
    bvals_are_zero,
    update_complex_name,
    update_multiecho_name,
    update_uncombined_name,
)
from heudiconv.utils import load_heuristic

from .utils import TESTS_DATA_PATH


def test_update_complex_name() -> None:
    """Unit testing for heudiconv.convert.update_complex_name(), which updates
    filenames with the part field if appropriate.
    """
    # Standard name update
    base_fn = "sub-X_ses-Y_task-Z_run-01_sbref"
    metadata = {"ImageType": ["ORIGINAL", "PRIMARY", "P", "MB", "TE3", "ND", "MOSAIC"]}
    out_fn_true = "sub-X_ses-Y_task-Z_run-01_part-phase_sbref"
    out_fn_test = update_complex_name(metadata, base_fn)
    assert out_fn_test == out_fn_true

    # Catch an unsupported type and *do not* update
    base_fn = "sub-X_ses-Y_task-Z_run-01_phase"
    out_fn_test = update_complex_name(metadata, base_fn)
    assert out_fn_test == base_fn

    # Data type is missing from metadata so raise a RuntimeError
    base_fn = "sub-X_ses-Y_task-Z_run-01_sbref"
    metadata = {"ImageType": ["ORIGINAL", "PRIMARY", "MB", "TE3", "ND", "MOSAIC"]}
    with pytest.raises(RuntimeError):
        update_complex_name(metadata, base_fn)

    # Catch existing field with value (part is already in the filename)
    # that *does not match* metadata and raise Exception
    base_fn = "sub-X_ses-Y_task-Z_run-01_part-mag_sbref"
    metadata = {"ImageType": ["ORIGINAL", "PRIMARY", "P", "MB", "TE3", "ND", "MOSAIC"]}
    with pytest.raises(BIDSError):
        update_complex_name(metadata, base_fn)

    # Catch existing field with value (part is already in the filename)
    # that *does match* metadata and do not update
    base_fn = "sub-X_ses-Y_task-Z_run-01_part-phase_sbref"
    metadata = {"ImageType": ["ORIGINAL", "PRIMARY", "P", "MB", "TE3", "ND", "MOSAIC"]}
    out_fn_test = update_complex_name(metadata, base_fn)
    assert out_fn_test == base_fn


def test_update_multiecho_name() -> None:
    """Unit testing for heudiconv.convert.update_multiecho_name(), which updates
    filenames with the echo field if appropriate.
    """
    # Standard name update
    base_fn = "sub-X_ses-Y_task-Z_run-01_bold"
    metadata = {"EchoTime": 0.01, "EchoNumber": 1}
    echo_times = [0.01, 0.02, 0.03]
    out_fn_true = "sub-X_ses-Y_task-Z_run-01_echo-1_bold"
    out_fn_test = update_multiecho_name(metadata, base_fn, echo_times)
    assert out_fn_test == out_fn_true

    # EchoNumber field is missing from metadata, so use echo_times
    metadata = {"EchoTime": 0.01}
    out_fn_test = update_multiecho_name(metadata, base_fn, echo_times)
    assert out_fn_test == out_fn_true

    # Catch an unsupported type and *do not* update
    base_fn = "sub-X_ses-Y_task-Z_run-01_phasediff"
    out_fn_test = update_multiecho_name(metadata, base_fn, echo_times)
    assert out_fn_test == base_fn

    # EchoTime is missing, but use EchoNumber (which is the first thing it checks)
    base_fn = "sub-X_ses-Y_task-Z_run-01_bold"
    out_fn_true = "sub-X_ses-Y_task-Z_run-01_echo-1_bold"
    metadata = {"EchoNumber": 1}
    echo_times = [False, 0.02, 0.03]
    out_fn_test = update_multiecho_name(metadata, base_fn, echo_times)
    assert out_fn_test == out_fn_true

    # Both EchoTime and EchoNumber are missing, which raises a KeyError
    base_fn = "sub-X_ses-Y_task-Z_run-01_bold"
    metadata = {}
    echo_times = [False, 0.02, 0.03]
    with pytest.raises(KeyError):
        update_multiecho_name(metadata, base_fn, echo_times)

    # Providing echo times as something other than a list should raise a TypeError
    base_fn = "sub-X_ses-Y_task-Z_run-01_bold"
    with pytest.raises(TypeError):
        update_multiecho_name(metadata, base_fn, set(echo_times))  # type: ignore[arg-type]


def test_update_uncombined_name() -> None:
    """Unit testing for heudiconv.convert.update_uncombined_name(), which updates
    filenames with the ch field if appropriate.
    """
    # Standard name update
    base_fn = "sub-X_ses-Y_task-Z_run-01_bold"
    metadata = {"CoilString": "H1"}
    channel_names = ["H1", "H2", "H3", "HEA;HEP"]
    out_fn_true = "sub-X_ses-Y_task-Z_run-01_ch-01_bold"
    out_fn_test = update_uncombined_name(metadata, base_fn, channel_names)
    assert out_fn_test == out_fn_true

    # CoilString field has no number in it, so we index the channel_names list
    metadata = {"CoilString": "HEA;HEP"}
    out_fn_true = "sub-X_ses-Y_task-Z_run-01_ch-04_bold"
    out_fn_test = update_uncombined_name(metadata, base_fn, channel_names)
    assert out_fn_test == out_fn_true

    # Extract the number from the CoilString and use that
    channel_names = ["H1", "B1", "H3", "HEA;HEP"]
    metadata = {"CoilString": "H1"}
    out_fn_true = "sub-X_ses-Y_task-Z_run-01_ch-01_bold"
    out_fn_test = update_uncombined_name(metadata, base_fn, channel_names)
    assert out_fn_test == out_fn_true

    # NOTE: Extracting the number does not protect against multiple coils with the same number
    # (but, say, different letters)
    # Note that this is still "ch-01"
    metadata = {"CoilString": "B1"}
    out_fn_true = "sub-X_ses-Y_task-Z_run-01_ch-01_bold"
    out_fn_test = update_uncombined_name(metadata, base_fn, channel_names)
    assert out_fn_test == out_fn_true

    # Providing echo times as something other than a list should raise a TypeError
    base_fn = "sub-X_ses-Y_task-Z_run-01_bold"
    with pytest.raises(TypeError):
        update_uncombined_name(metadata, base_fn, set(channel_names))  # type: ignore[arg-type]


def test_b0dwi_for_fmap(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Make sure we raise a warning when .bvec and .bval files
    are present but the modality is not dwi.
    We check it by extracting a few DICOMs from a series with
    bvals: 5 5 1500
    """
    import logging

    caplog.set_level(logging.WARNING)
    subID = "b0dwiForFmap"
    args = [
        "-c",
        "dcm2niix",
        "-o",
        str(tmp_path),
        "-b",
        "-f",
        "test_b0dwi_for_fmap",
        "--files",
        op.join(TESTS_DATA_PATH, "b0dwiForFmap"),
        "-s",
        subID,
    ]
    runner(args)

    # assert that it raised a warning that the fmap directory will contain
    # bvec and bval files.
    expected_msg = DW_IMAGE_IN_FMAP_FOLDER_WARNING.format(
        folder=op.join(tmp_path, f"sub-{subID}", "fmap")
    )
    assert any(expected_msg in c.message for c in caplog.records)

    # check that both 'fmap' and 'dwi' directories have been extracted and they contain
    # *.bvec and a *.bval files
    for mod in ["fmap", "dwi"]:
        assert op.isdir(op.join(tmp_path, f"sub-{subID}", mod))
        for ext in ["bval", "bvec"]:
            assert glob(op.join(tmp_path, f"sub-{subID}", mod, f"sub-{subID}_*.{ext}"))


# Test two scenarios for each case:
# -study without sessions
# -study with sessions
@pytest.mark.parametrize(
    "subjects, sesID, _expected_session_folder",
    [
        (["Jason", "Bourne"], None, "sub-{sID}"),
        (["Bourne"], "Treadstone", op.join("sub-{{sID}}", "ses-{{ses}}")),
    ],
)
# Two possibilities: with or without heuristics:
@pytest.mark.parametrize(
    "heuristic",
    ["example", "reproin", None],  # heuristics/example.py, heuristics/reproin.py
)
def test_populate_intended_for(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    subjects: list[str],
    sesID: Optional[str],
    _expected_session_folder: str,
    heuristic: Optional[str],
) -> None:
    """
    Test convert

    For now, I'm just going to test that the call to populate_intended_for is
    done with the correct argument.
    More tests can be added here.
    """

    def mock_populate_intended_for(
        session: str,
        matching_parameters: str | list[str] = "Shims",
        criterion: str = "Closest",
    ) -> None:
        """
        Pretend we run populate_intended_for, but just print out the arguments.
        """
        print("session: {}".format(session))
        print("matching_parameters: {}".format(matching_parameters))
        print("criterion: {}".format(criterion))

    # mock the "populate_intended_for":
    monkeypatch.setattr(
        heudiconv.convert, "populate_intended_for", mock_populate_intended_for
    )

    outdir = op.join(tmp_path, "foo")
    outfolder = (
        op.join(outdir, "sub-{sID}", "ses-{ses}")
        if sesID
        else op.join(outdir, "sub-{sID}")
    )
    sub_ses = "sub-{sID}" + ("_ses-{ses}" if sesID else "")

    # items are a list of tuples, with each tuple having three elements:
    #   prefix, outtypes, item_dicoms
    items: list[tuple[str, tuple[str, ...], list[str]]] = [
        (
            op.join(outfolder, "anat", sub_ses + "_T1w").format(sID=s, ses=sesID),
            ("",),
            [],
        )
        for s in subjects
    ]

    heuristic_mod = load_heuristic(heuristic) if heuristic else None
    heudiconv.convert.convert(
        items,
        converter="",
        scaninfo_suffix=".json",
        custom_callable=None,
        populate_intended_for_opts=getattr(
            heuristic_mod, "POPULATE_INTENDED_FOR_OPTS", None
        ),
        with_prov=False,
        bids_options="",
        outdir=outdir,
        min_meta=True,
        overwrite=False,
    )
    output = capfd.readouterr()
    # if the heuristic module has a 'POPULATE_INTENDED_FOR_OPTS' field, we expect
    # to get the output of the mock_populate_intended_for, otherwise, no output:
    pif_cfg = getattr(heuristic_mod, "POPULATE_INTENDED_FOR_OPTS", None)
    if pif_cfg:
        assert all(
            [
                "\n".join(
                    [
                        "session: " + outfolder.format(sID=s, ses=sesID),
                        # "ImagingVolume" is defined in heuristic file; "Shims" is the default
                        f"matching_parameters: {pif_cfg['matching_parameters']}",
                        f"criterion: {pif_cfg['criterion']}",
                    ]
                )
                in output.out
                for s in subjects
            ]
        )
    else:
        # If there was no heuristic, make sure populate_intended_for was not called
        assert not output.out


def test_bvals_are_zero() -> None:
    """Unit testing for heudiconv.convert.bvals_are_zero(),
    which checks if non-dwi bvals are all zeros and can be removed
    """
    zero_bvals = op.join(TESTS_DATA_PATH, "zeros.bval")
    non_zero_bvals = op.join(TESTS_DATA_PATH, "non_zeros.bval")

    assert bvals_are_zero(zero_bvals)
    assert not bvals_are_zero(non_zero_bvals)
    assert bvals_are_zero([zero_bvals, zero_bvals])
    assert not bvals_are_zero([non_zero_bvals, zero_bvals])
