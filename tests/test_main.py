import sys

from mock import patch
from six.moves import StringIO
import pytest
from . import heudiconv


@patch('sys.stdout', new_callable=StringIO)
def test_main_help(stdout):
    with pytest.raises(SystemExit):
        heudiconv.main(['--help'])
    assert stdout.getvalue().startswith("usage: ")


@patch('sys.stderr' if sys.version_info[:2] <= (3, 3) else 'sys.stdout', new_callable=StringIO)
def test_main_version(std):
    with pytest.raises(SystemExit):
        heudiconv.main(['--version'])
    assert std.getvalue().rstrip() == heudiconv.__version__
