from collections import namedtuple
import os
import os.path as op
import pytest
from mock import patch
try:
    from tinydb import TinyDB, Query
except ImportError:
    pytest.importorskip("tinydb")
from subprocess import CalledProcessError

try:
    from heudiconv.cli.monitor import (monitor, process, run_heudiconv,
                                       MASK_NEWDIR)

    Header = namedtuple('header', ['wd', 'mask', 'cookie', 'len'])
    header = Header(5, MASK_NEWDIR, 5, 5)
    watch_path = b'WATCHME'
    filename = b'FILE'
    type_names = b'TYPE'

    path2 = watch_path + b'/' + filename + b'/subpath'

    my_events = [(header, type_names, watch_path, filename),
                 (header, type_names, path2, b'')]
except AttributeError:
    # Import of inotify fails on mac os x with error
    # lsym(0x11fbeb780, inotify_init): symbol not found
    # because inotify doesn't seem to exist on Mac OS X
    my_events = []
    pytestmark = pytest.mark.skip(reason='Unable to import inotify')


class MockInotifyTree(object):
    def __init__(self, events):
        self.events = iter(events)
    def event_gen(self):
        for e in self.events:
            yield e
    def __call__(self, topdir):
        return self


class MockTime(object):
    def __init__(self, time):
        self.time = time
    def __call__(self):
        return self.time



@pytest.mark.skip(reason="TODO")
@patch('inotify.adapters.InotifyTree', MockInotifyTree(my_events))
@patch('time.time', MockTime(42))
def test_monitor(capsys):
    monitor(watch_path.decode(), check_ptrn='')
    out, err = capsys.readouterr()
    desired_output = '{0}/{1} {2}\n'.format(watch_path.decode(),
                                            filename.decode(),
                                            42)
    desired_output += 'Updating {0}/{1}: {2}\n'.format(watch_path.decode(),
                                                       filename.decode(),
                                                       42)
    assert out == desired_output


@pytest.mark.skip(reason="TODO")
@patch('time.time', MockTime(42))
@pytest.mark.parametrize("side_effect,success", [
    (None, 1),
    (CalledProcessError('mycmd', 1), 0)
])
def test_process(tmpdir, capsys, side_effect, success):
    db_fn = tmpdir.join('database.json')
    log_dir = tmpdir.mkdir('log')
    db = TinyDB(db_fn.strpath)
    process_me = '/my/path/A12345'
    accession_number = op.basename(process_me)
    paths2process = {process_me: 42}
    with patch('subprocess.Popen') as mocked_popen:
        stdout = b"INFO: PROCESSING STARTS: {'just': 'a test'}"
        mocked_popen_instance = mocked_popen.return_value
        mocked_popen_instance.side_effect = side_effect
        mocked_popen_instance.communicate.return_value = (stdout, )
        # set return value for wait
        mocked_popen_instance.wait.return_value = 1 - success
        # mock also communicate to get the supposed stdout
        process(paths2process, db, wait=-30, logdir=log_dir.strpath)
        out, err = capsys.readouterr()
        log_fn = log_dir.join(accession_number + '.log')

        mocked_popen.assert_called_once()
        assert log_fn.check()
        assert log_fn.read() == stdout.decode('utf-8')
        assert db_fn.check()
        # dictionary should be empty
        assert not paths2process
        assert out == 'Time to process {0}\n'.format(process_me)

        # check what we have in the database
        Path = Query()
        query = db.get(Path.input_path == process_me)
        assert len(db) == 1
        assert query
        assert query['success'] == success
        assert query['accession_number'] == op.basename(process_me)
        assert query['just'] == 'a test'

@pytest.mark.skip(reason="TODO")
def test_run_heudiconv():
    # echo should succeed always
    mydict = {'key1': 'value1', 'key2': 'value2', 'success': 1}
    cmd = "echo INFO: PROCESSING STARTS: {0}".format(str(mydict))
    stdout, info_dict = run_heudiconv(cmd)
    assert info_dict == mydict
    assert "echo " + stdout.strip() == cmd
