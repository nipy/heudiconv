from pathlib import Path
import tarfile

import pydicom
import pytest

from heudiconv.cli.run import main
from heudiconv.tests.utils import TESTS_DATA_PATH


@pytest.mark.ai_generated
@pytest.mark.parametrize("input_kind", ["file", "directory", "archive"])
def test_ls_without_heuristic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], input_kind: str
) -> None:
    source = Path(TESTS_DATA_PATH) / "axasc35.dcm"
    if input_kind == "directory":
        inputs = tmp_path / "dicoms"
        inputs.mkdir()
        (inputs / "sample.dcm").write_bytes(source.read_bytes())
        source = inputs
    elif input_kind == "archive":
        archive = tmp_path / "dicoms.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(source, arcname="sample.dcm")
        source = archive
    output = tmp_path / "output"
    args = ["--command", "ls", "--files", str(source), "-o", str(output)]
    main(args + ["-f", "convertall", "-s", "test"])
    explicit = capsys.readouterr().out
    assert "1 sequences" in explicit
    main(args)
    listed = capsys.readouterr().out
    assert "1 sequences" in listed
    assert listed.splitlines()[0] == explicit.splitlines()[0]
    assert not output.exists()


@pytest.mark.ai_generated
@pytest.mark.parametrize("grouping", ["studyUID", "accession_number"])
def test_ls_keeps_separate_studies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], grouping: str
) -> None:
    dicoms = tmp_path / "dicoms"
    dicoms.mkdir()
    study_ids = ["1.2.826.0.1.3680043.8.498.101", "1.2.826.0.1.3680043.8.498.102"]
    accessions = ["first", "second"]
    for index, study_id in enumerate(study_ids):
        sample = pydicom.dcmread(Path(TESTS_DATA_PATH) / "axasc35.dcm")
        # Deliberately give the copies distinct study and series identities.
        sample.StudyInstanceUID = study_id
        sample.SeriesInstanceUID = study_id + ".1"
        sample.SeriesNumber = index + 1
        sample.AccessionNumber = accessions[index]
        sample.save_as(dicoms / f"{index}.dcm")
    main(["--command", "ls", "--files", str(dicoms), "-g", grouping])
    lines = capsys.readouterr().out.splitlines()
    identifiers = study_ids if grouping == "studyUID" else accessions
    assert lines[0] == str(dicoms)
    assert set(lines[1:]) == {f"\t{value} 1 sequences" for value in identifiers}


@pytest.mark.ai_generated
def test_ls_preserves_explicit_heuristic_customization(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    heuristic = tmp_path / "custom_listing.py"
    heuristic.write_text(
        "def ls(study_session, sequences):\n    return ' custom listing'\n",
        encoding="utf-8",
    )
    main(
        [
            "--command",
            "ls",
            "--files",
            str(Path(TESTS_DATA_PATH) / "axasc35.dcm"),
            "-f",
            str(heuristic),
            "-s",
            "test",
            "-o",
            str(tmp_path / "output"),
        ]
    )
    assert "1 sequences custom listing" in capsys.readouterr().out
