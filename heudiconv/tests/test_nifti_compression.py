"""The requested NIfTI extension must describe the file's actual encoding."""

from __future__ import annotations

import gzip
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from heudiconv.convert import _safe_move_nifti, convert
from heudiconv.utils import save_json

from .utils import TESTS_DATA_PATH


@pytest.mark.ai_generated
@pytest.mark.parametrize("outtype", ["nii", "nii.gz"])
@pytest.mark.parametrize("compress", [None, "n", "y"])
def test_conversion_nifti_encoding(
    tmp_path: Path, outtype: str, compress: str | None
) -> None:
    config = tmp_path / "dcmconfig.json"
    if compress is not None:
        save_json(config, {"compress": compress})
    prefix = tmp_path / "sub-01" / "anat" / "sub-01_T1w"
    convert(
        [(str(prefix), (outtype,), [str(Path(TESTS_DATA_PATH) / "axasc35.dcm")])],
        converter="dcm2niix",
        scaninfo_suffix=".json",
        custom_callable=None,
        with_prov=False,
        bids_options="",
        outdir=str(tmp_path),
        min_meta=True,
        overwrite=False,
        dcmconfig=str(config) if compress is not None else None,
    )
    output = prefix.with_suffix("." + outtype)
    with output.open("rb") as stream:
        assert (stream.read(2) == b"\x1f\x8b") == (outtype == "nii.gz")
    image = nib.load(output)
    assert isinstance(image, nib.Nifti1Image)
    assert image.shape == (64, 64, 35)
    assert np.isfinite(image.get_fdata()).all()
    assert np.any(image.get_fdata())
    assert not list(output.parent.glob("*heudiconv*"))


@pytest.mark.ai_generated
@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize("overwrite", [False, True])
def test_nifti_reencoding_preserves_bytes_and_overwrite_policy(
    tmp_path: Path, compressed: bool, overwrite: bool
) -> None:
    payload = gzip.decompress(
        (Path(TESTS_DATA_PATH) / "sample_nifti.nii.gz").read_bytes()
    )
    source = tmp_path / ("source.nii.gz" if compressed else "source.nii")
    target = tmp_path / ("target.nii" if compressed else "target.nii.gz")
    source.write_bytes(gzip.compress(payload) if compressed else payload)
    target.write_bytes(b"existing destination")
    if overwrite:
        _safe_move_nifti(str(source), str(target), overwrite=True)
        encoded = target.read_bytes()
        assert (encoded if compressed else gzip.decompress(encoded)) == payload
        assert not source.exists()
    else:
        with pytest.raises(RuntimeError, match="destination already exists"):
            _safe_move_nifti(str(source), str(target))
        assert source.exists()
        assert target.read_bytes() == b"existing destination"
    assert not list(tmp_path.glob(".heudiconv-nifti-*"))


@pytest.mark.ai_generated
def test_nifti_reencoding_rejects_truncated_data(tmp_path: Path) -> None:
    payload = gzip.decompress(
        (Path(TESTS_DATA_PATH) / "sample_nifti.nii.gz").read_bytes()
    )
    source = tmp_path / "truncated.nii"
    target = tmp_path / "target.nii.gz"
    source.write_bytes(payload[:-100])
    with pytest.raises((ValueError, OSError)):
        _safe_move_nifti(str(source), str(target))
    assert source.read_bytes() == payload[:-100]
    assert not target.exists()
    assert not list(tmp_path.glob(".heudiconv-nifti-*"))
