from collections import namedtuple
import pytest
from mock import patch
from monitor import monitor, MASK_NEWDIR


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
    
