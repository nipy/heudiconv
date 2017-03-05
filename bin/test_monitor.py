from collections import namedtuple
import pytest
from mock import patch
from monitor import monitor, process, run_heudiconv, MASK_NEWDIR
from os.path import exists
from tinydb import TinyDB, Query
from subprocess import CalledProcessError


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


Header = namedtuple('header', ['wd', 'mask', 'cookie', 'len'])
header = Header(5, MASK_NEWDIR, 5, 5)
watch_path = b'WATCHME'
filename = b'FILE'
type_names = b'TYPE'

path2 = watch_path + b'/' + filename + b'/subpath'

my_events = [(header, type_names, watch_path, filename), 
             (header, type_names, path2, b'')]

@patch('inotify.adapters.InotifyTree', MockInotifyTree(my_events))
@patch('time.time', MockTime(42))
def test_monitor(capsys):
    monitor(watch_path.decode(), check_ptrn='')
    out, err = capsys.readouterr()
    desired_output = '{0}/{1} {2}\n'.format(watch_path.decode(), filename.decode(), 42) 
    desired_output += 'Updating {0}/{1}: {2}\n'.format(watch_path.decode(), filename.decode(), 42)
    assert out == desired_output


@patch('time.time', MockTime(42))
@pytest.mark.parametrize("side_effect,success", [
    (None, 1),
    (CalledProcessError('mycmd', 1), 0)
])
def test_process(tmpdir, capsys, side_effect, success):
    db_fn = tmpdir.join('database.json')
    db = TinyDB(db_fn.strpath)
    paths2process = {'/my/path': 42} 
    with patch('subprocess.Popen') as mocked_popen:
        mocked_popen_instance = mocked_popen.return_value
        mocked_popen_instance.side_effect = side_effect
        mocked_popen_instance.communicate.return_value = (b"INFO: PROCESSING STARTS: {'just': 'a test'}", )
        # set return value for wait
        mocked_popen_instance.wait.return_value = 1 - success
        # mock also communicate to get the supposed stdout
        # mocked_popen.communicate = lambda: (b"INFO: PROCESSING STARTS: {'just': 'a test'}", )
        process(paths2process, db, wait=-30)
        out, err = capsys.readouterr()

        mocked_popen.assert_called_once()
        assert db_fn.check()
        # dictionary should be empty
        assert not paths2process
        assert out == 'Time to process /my/path\n' 

        # check what we have in the database
        Path = Query()
        query = db.get(Path.input_path == '/my/path')
        assert len(db) == 1
        assert query
        assert query['success'] == success


def test_run_heudiconv():
    # echo should succeed always
    mydict = {'key1': 'value1', 'key2': 'value2', 'success': 1}
    cmd = "echo INFO: PROCESSING STARTS: {0}".format(str(mydict))
    out = run_heudiconv(cmd)
    assert out == mydict
