import csv
from pathlib import Path
import shutil

import pytest

from heudiconv.cli.run import main
from heudiconv.tests.utils import TESTS_DATA_PATH


@pytest.mark.ai_generated
@pytest.mark.skipif(shutil.which("dcm2niix") is None, reason="requires dcm2niix")
@pytest.mark.parametrize(
    "anonymous,bids,expected",
    [
        ("SAX_OA_34", True, "SAXOA34"),
        ("SAXOA34", True, "SAXOA34"),
        ("SAX_OA_34", False, "SAX_OA_34"),
        ("_-", True, None),
    ],
)
def test_anonymous_subject_label(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    anonymous: str,
    bids: bool,
    expected: str | None,
) -> None:
    heuristic = tmp_path / "custom.py"
    heuristic.write_text(
        "def infotodict(seqinfo):\n"
        "    return {('sub-{subject}/anat/sub-{subject}_T1w', ('nii.gz',), None):\n"
        "            [s.series_id for s in seqinfo]}\n",
        encoding="utf-8",
    )

    def lookup(subject: str, command: str) -> str:
        # The lookup must receive the original ID, before BIDS normalization.
        assert subject == "SAX_EIB_034"
        assert command == "lookup-subject"
        return anonymous

    monkeypatch.setattr("heudiconv.main.anonymize_sid", lookup)
    output = tmp_path / "output"
    args = [
        "--files",
        str(Path(TESTS_DATA_PATH) / "axasc35.dcm"),
        "-f",
        str(heuristic),
        "-s",
        "SAX_EIB_034",
        "-o",
        str(output),
        "--anon-cmd",
        "lookup-subject",
        "-c",
        "dcm2niix",
        "--minmeta",
    ]
    if bids:
        args.append("-b")
    if expected is None:
        with pytest.raises(ValueError, match="Label became empty"):
            main(args)
        assert not output.exists()
        return

    main(args)
    root = output if bids else output / expected
    subject_dir = root / f"sub-{expected}"
    image = subject_dir / "anat" / f"sub-{expected}_T1w.nii.gz"
    assert image.is_file()
    assert not list(output.rglob("*SAXEIB034*T1w*"))
    assert (output / ".heudiconv" / expected).is_dir()
    if bids:
        with (output / "participants.tsv").open() as stream:
            participants = list(csv.DictReader(stream, delimiter="\t"))
        assert [row["participant_id"] for row in participants] == [f"sub-{expected}"]
        scans = list(subject_dir.glob("*_scans.tsv"))
        assert [path.name for path in scans] == [f"sub-{expected}_scans.tsv"]
        with scans[0].open() as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        assert [row["filename"] for row in rows] == [f"anat/sub-{expected}_T1w.nii.gz"]
