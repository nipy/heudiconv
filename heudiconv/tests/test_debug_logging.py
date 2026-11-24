import logging
from pathlib import Path

import pytest

from heudiconv.cli.run import main


@pytest.mark.ai_generated
@pytest.mark.parametrize("debug", [False, True])
def test_debug_enables_heuristic_and_package_logs(
    debug: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    heuristic = tmp_path / f"debug_heuristic_{debug}.py"
    heuristic.write_text(
        '"""A heuristic with diagnostics on import."""\n'
        "import logging\n"
        "logging.getLogger('heudiconv').debug('heuristic diagnostic')\n"
        "logging.getLogger('heudiconv.dicoms').debug('dicom diagnostic')\n"
    )
    monkeypatch.setenv("NO_ET", "1")
    monkeypatch.setattr("heudiconv.main.setup_exceptionhook", lambda: None)
    with caplog.at_level(logging.INFO, logger="heudiconv"):
        with caplog.at_level(logging.NOTSET, logger="heudiconv.main"):
            caplog.handler.setLevel(logging.DEBUG)
            args = ["--command", "heuristic-info", "-f", str(heuristic)]
            if debug:
                args.append("--dbg")
            main(args)
    assert ("heuristic diagnostic" in caplog.messages) is debug
    assert ("dicom diagnostic" in caplog.messages) is debug
