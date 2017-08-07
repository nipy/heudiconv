import csv
import os
import pytest
import sys

from mock import patch
from os.path import join as opj
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
    heudiconv.populate_bids_templates(
        str(tmpdir),
        defaults={'Acknowledgements': 'something'})
    for f in "README", "dataset_description.json", "CHANGES":
        # Just test that we have created them and they all have stuff TODO
        assert "TODO" in tmpdir.join(f).read()
    assert "something" in tmpdir.join('dataset_description.json').read()


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


def test_prepare_for_datalad(tmpdir):
    pytest.importorskip("datalad")
    studydir = tmpdir.join("PI").join("study")
    studydir_ = str(studydir)
    os.makedirs(studydir_)
    heudiconv.populate_bids_templates(studydir_)

    heudiconv.add_to_datalad(str(tmpdir), studydir_)

    from datalad.api import Dataset
    superds = Dataset(str(tmpdir))

    assert superds.is_installed()
    assert not superds.repo.dirty
    subdss = superds.get_subdatasets(recursive=True)
    for ds_path in sorted(subdss):
        ds = Dataset(opj(superds.path, ds_path))
        assert ds.is_installed()
        assert not ds.repo.dirty

    # the last one should have been the study
    target_files = {
        '.gitattributes',
        '.datalad/config', '.datalad/.gitattributes',
        'dataset_description.json',
        'CHANGES', 'README'}
    assert set(ds.repo.get_indexed_files()) == target_files
    # and all are under git
    for f in target_files:
        assert not ds.repo.is_under_annex(f)
    assert not ds.repo.is_under_annex('.gitattributes')


def test_json_dumps_pretty():
    pretty = heudiconv.json_dumps_pretty
    assert pretty({}) == "{}"
    assert pretty({"a": -1, "b": "123", "c": [1, 2, 3], "d": ["1.0", "2.0"]}) \
        == '{\n  "a": -1,\n  "b": "123",\n  "c": [1, 2, 3],\n  "d": ["1.0", "2.0"]\n}'
    assert pretty({'a': ["0.3", "-1.9128906358217845e-12", "0.2"]}) \
        == '{\n  "a": ["0.3", "-1.9128906358217845e-12", "0.2"]\n}'


def test_get_formatted_scans_key_row():
    item = [
        ('tests/data/01-fmap_acq-3mm/1.3.12.2.1107.5.2.43.66112.2016101409263663466202201.dcm',
         ('nii.gz', 'dicom'),
         ['tests/data/01-fmap_acq-3mm/1.3.12.2.1107.5.2.43.66112.2016101409263663466202201.dcm'])
    ]
    outname_bids_file = '/a/path/Halchenko/Yarik/950_bids_test4/sub-phantom1sid1/fmap/sub-phantom1sid1_acq-3mm_phasediff.json'

    row = heudiconv.get_formatted_scans_key_row(item)
    assert(len(row) == 3)
    assert(row[0] == '2016-10-14T09:26:34')
    assert(row[1] == '')
    randstr1 = row[2]
    row = heudiconv.get_formatted_scans_key_row(item)
    randstr2 = row[2]
    assert(randstr1 != randstr2)


# TODO: finish this
def test_add_rows_to_scans_keys_file(tmpdir):
    fn = opj(tmpdir.strpath, 'file.tsv')
    rows = {
        'my_file.nii.gz': ['2016adsfasd', '', 'fasadfasdf'],
        'another_file.nii.gz': ['2018xxxxx', '', 'fasadfasdf']
    }
    heudiconv.add_rows_to_scans_keys_file(fn, rows)

    def _check_rows(fn, rows):
        with open(fn, 'r') as csvfile:
            reader = csv.reader(csvfile, delimiter='\t')
            rows_loaded = []
            for row in reader:
                rows_loaded.append(row)
        for i, row_ in enumerate(rows_loaded):
            if i == 0:
                assert(row_ == ['filename', 'acq_time', 'operator', 'randstr'])
            else:
                assert(rows[row_[0]] == row_[1:])

    _check_rows(fn, rows)
    # add a new one
    extra_rows = {
        'a_new_file.nii.gz': ['2016adsfasd23', '', 'fasadfasdf'],
        'my_file.nii.gz': ['2016adsfasd', '', 'fasadfasdf'],
        'another_file.nii.gz': ['2018xxxxx', '', 'fasadfasdf']
    }
    heudiconv.add_rows_to_scans_keys_file(fn, extra_rows)
    _check_rows(fn, extra_rows)

