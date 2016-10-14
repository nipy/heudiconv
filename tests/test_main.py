import pytest
import sys

from mock import patch
from os.path import exists
from six.moves import StringIO


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


def test_create_file_if_missing(tmpdir):
    tf = tmpdir.join("README.txt")
    assert not tf.exists()
    heudiconv.create_file_if_missing(str(tf), "content")
    assert tf.exists()
    assert tf.read() == "content"
    heudiconv.create_file_if_missing(str(tf), "content2")
    # nothing gets changed
    assert tf.read() == "content"


def test_populate_bids_templates(tmpdir):
    heudiconv.populate_bids_templates(str(tmpdir))
    for f in "README", "dataset_description.json", "CHANGES":
        # Just test that we have created them and they all have stuff TODO
        assert "TODO" in tmpdir.join(f).read()


def test_add_participant_record(tmpdir):
    tf = tmpdir.join('participants.tsv')
    assert not tf.exists()
    heudiconv.add_participant_record(str(tmpdir), "sub01", "023Y", "M")
    # should create the file and place corrected record
    sub01 = tf.read()
    assert sub01 == """\
participant_id	age	sex	group
sub-sub01	23	M	control
"""
    heudiconv.add_participant_record(str(tmpdir), "sub01", "023Y", "F")
    assert tf.read() == sub01  # nothing was added even though differs in values
    heudiconv.add_participant_record(str(tmpdir), "sub02", "2", "F")
    assert tf.read() == """\
participant_id	age	sex	group
sub-sub01	23	M	control
sub-sub02	2	F	control
"""
