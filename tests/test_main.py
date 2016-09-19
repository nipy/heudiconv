import sys

from mock import patch
from six.moves import StringIO
from six import PY2
from nose.tools import assert_raises, assert_equal

from . import heudiconv


@patch('sys.stdout', new_callable=StringIO)
def test_main_help(stdout):
    assert_raises(SystemExit, heudiconv.main, ['--help'])
    assert(stdout.getvalue().startswith("usage: "))


@patch('sys.stderr' if PY2 else 'sys.stdout', new_callable=StringIO)
def test_main_version(stderr):
    assert_raises(SystemExit, heudiconv.main, ['--version'])
    assert_equal(stderr.getvalue().rstrip(), heudiconv.__version__)
