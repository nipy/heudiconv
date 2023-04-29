from __future__ import annotations

from collections.abc import Iterable, Iterator
import os.path as op
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, Generic, NamedTuple, Optional, TypeVar
from unittest.mock import patch

import pytest

try:
    from tinydb import Query, TinyDB
except ImportError:
    pytest.importorskip("tinydb")
from subprocess import CalledProcessError

try:
    from heudiconv.cli.monitor import MASK_NEWDIR, monitor, process, run_heudiconv

    class Header(NamedTuple):
        wd: int
        mask: int
        cookie: int
        len: int

    header = Header(5, MASK_NEWDIR, 5, 5)
    watch_path = b"WATCHME"
    filename = b"FILE"
    type_names = b"TYPE"

    path2 = watch_path + b"/" + filename + b"/subpath"

    my_events = [
        (header, type_names, watch_path, filename),
        (header, type_names, path2, b""),
    ]
except AttributeError:
    # Import of inotify fails on mac os x with error
    # lsym(0x11fbeb780, inotify_init): symbol not found
    # because inotify doesn't seem to exist on Mac OS X
    my_events = []
    pytestmark = pytest.mark.skip(reason="Unable to import inotify")


if TYPE_CHECKING:
    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self


T = TypeVar("T")


class MockInotifyTree(Generic[T]):
    def __init__(self, events: Iterable[T]) -> None:
        self.events: Iterator[T] = iter(events)

    def event_gen(self) -> Iterator[T]:
        for e in self.events:
            yield e

    def __call__(self, _topdir: Any) -> Self:
        return self


class MockTime:
    def __init__(self, time: float) -> None:
        self.time = time

    def __call__(self) -> float:
        return self.time


@pytest.mark.skip(reason="TODO")
@patch("inotify.adapters.InotifyTree", MockInotifyTree(my_events))
@patch("time.time", MockTime(42))
def test_monitor(capsys: pytest.CaptureFixture[str]) -> None:
    monitor(watch_path.decode(), check_ptrn="")
    out, err = capsys.readouterr()
    desired_output = "{0}/{1} {2}\n".format(watch_path.decode(), filename.decode(), 42)
    desired_output += "Updating {0}/{1}: {2}\n".format(
        watch_path.decode(), filename.decode(), 42
    )
    assert out == desired_output


@pytest.mark.skip(reason="TODO")
@patch("time.time", MockTime(42))
@pytest.mark.parametrize(
    "side_effect,success", [(None, 1), (CalledProcessError(1, "mycmd"), 0)]
)
def test_process(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    side_effect: Optional[BaseException],
    success: int,
) -> None:
    db_fn = tmp_path / "database.json"
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    db = TinyDB(str(db_fn))
    process_me = "/my/path/A12345"
    accession_number = op.basename(process_me)
    paths2process = {process_me: 42.0}
    with patch("subprocess.Popen") as mocked_popen:
        stdout = b"INFO: PROCESSING STARTS: {'just': 'a test'}"
        mocked_popen_instance = mocked_popen.return_value
        mocked_popen_instance.side_effect = side_effect
        mocked_popen_instance.communicate.return_value = (stdout,)
        # set return value for wait
        mocked_popen_instance.wait.return_value = 1 - success
        # mock also communicate to get the supposed stdout
        process(paths2process, db, wait=-30, logdir=str(log_dir))
        out, err = capsys.readouterr()
        log_fn = log_dir / (accession_number + ".log")

        mocked_popen.assert_called_once()
        assert log_fn.exists()
        assert log_fn.read_text() == stdout.decode("utf-8")
        assert db_fn.exists()
        # dictionary should be empty
        assert not paths2process
        assert out == "Time to process {0}\n".format(process_me)

        # check what we have in the database
        path = Query()
        query = db.get(path.input_path == process_me)
        assert len(db) == 1
        assert query
        assert query["success"] == success
        assert query["accession_number"] == op.basename(process_me)
        assert query["just"] == "a test"


@pytest.mark.skip(reason="TODO")
def test_run_heudiconv() -> None:
    # echo should succeed always
    mydict = {"key1": "value1", "key2": "value2", "success": 1}
    args = ["echo", "INFO:", "PROCESSING", "STARTS:", str(mydict)]
    stdout, info_dict = run_heudiconv(args)
    assert info_dict == mydict
    assert stdout.strip() == " ".join(args[1:])
