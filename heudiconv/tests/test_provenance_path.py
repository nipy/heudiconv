from collections.abc import Iterator
from pathlib import Path
import shutil

from nipype import config
import pytest
from rdflib import Graph

from heudiconv.cli.run import main
from heudiconv.convert import nipype_convert
from heudiconv.tests.utils import TESTS_DATA_PATH


@pytest.fixture(autouse=True)
def restore_provenance_config() -> Iterator[None]:
    """Keep Nipype's global provenance configuration local to each test."""
    old_config = config.get("execution", "write_provenance")
    old_hash = config.get("execution", "hash_method")
    config.set("execution", "write_provenance", "false")
    try:
        yield
    finally:
        config.set("execution", "write_provenance", old_config)
        config.set("execution", "hash_method", old_hash)


@pytest.mark.ai_generated
@pytest.mark.skipif(shutil.which("dcm2niix") is None, reason="requires dcm2niix")
@pytest.mark.filterwarnings(
    "ignore:Dataset.default_context is deprecated:DeprecationWarning"
)
@pytest.mark.parametrize("with_prov", [False, True])
@pytest.mark.parametrize("relative_paths", [False, True])
def test_provenance_is_written_beside_conversion_not_in_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    with_prov: bool,
    relative_paths: bool,
) -> None:
    cwd = tmp_path / "caller"
    output = tmp_path / "output"
    work = tmp_path / "work"
    for directory in (cwd, output):
        directory.mkdir()
    monkeypatch.chdir(cwd)
    prefix = "../output/sub-01_T1w" if relative_paths else str(output / "sub-01_T1w")
    result, provenance = nipype_convert(
        [str(Path(TESTS_DATA_PATH) / "axasc35.dcm")],
        prefix,
        with_prov,
        "",
        "../work" if relative_paths else str(work),
    )
    assert Path(result.outputs.converted_files).is_file()
    assert Path.cwd() == cwd
    assert not list(cwd.iterdir())
    if with_prov:
        assert provenance == prefix + "_prov.ttl"
        assert "dcm2niix" in Path(provenance).read_text()
    else:
        assert provenance is None
        assert not list(output.glob("*_prov.*"))


@pytest.mark.ai_generated
@pytest.mark.skipif(shutil.which("dcm2niix") is None, reason="requires dcm2niix")
@pytest.mark.filterwarnings(
    "ignore:Dataset.default_context is deprecated:DeprecationWarning"
)
@pytest.mark.parametrize("minmeta", [False, True])
def test_cli_provenance_includes_requested_conversion_steps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    minmeta: bool,
) -> None:
    caller = tmp_path / "caller"
    caller.mkdir()
    monkeypatch.chdir(caller)
    heuristic = tmp_path / "custom.py"
    heuristic.write_text(
        "def infotodict(seqinfo):\n"
        "    return {('sub-{subject}/anat/sub-{subject}_T1w', ('nii.gz',), None):\n"
        "            [s.series_id for s in seqinfo]}\n"
    )
    args = [
        "--files",
        str(Path(TESTS_DATA_PATH) / "axasc35.dcm"),
        "-s",
        "01",
        "-f",
        str(heuristic),
        "-o",
        str(tmp_path / "bids"),
        "-b",
        "notop",
        "--with-prov",
    ]
    main(args + (["--minmeta"] if minmeta else []))

    output = tmp_path / "bids" / "sub-01" / "anat"
    assert (output / "sub-01_T1w.nii.gz").is_file()
    assert (output / "sub-01_T1w.json").is_file()
    graph = Graph().parse(output / "sub-01_T1w_prov.ttl", format="turtle")
    values = "\n".join(str(value) for value in graph.objects())
    assert "dcm2niix" in values
    assert ("embed_dicom_and_nifti_metadata" in values) == (not minmeta)
    assert "Embedding failed" not in caplog.text
    assert Path.cwd() == caller
    assert not list(caller.iterdir())
