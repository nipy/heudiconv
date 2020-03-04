#
# Tests for reproin.py
#
from collections import OrderedDict
from mock import patch
import re

from . import reproin
from .reproin import (
    filter_files,
    fix_canceled_runs,
    fix_dbic_protocol,
    fixup_subjectid,
    get_dups_marked,
    md5sum,
    parse_series_spec,
    sanitize_str,
)


def test_get_dups_marked():
    no_dups = {('some',): [1]}
    assert get_dups_marked(no_dups) == no_dups

    info = OrderedDict(
        [
            (('bu', 'du'), [1, 2]),
            (('smth',), [3]),
            (('smth2',), ['a', 'b', 'c'])
         ]
    )

    assert get_dups_marked(info) == get_dups_marked(info, True) == \
        {
            ('bu__dup-01', 'du'): [1],
            ('bu', 'du'): [2],
            ('smth',): [3],
            ('smth2__dup-01',): ['a'],
            ('smth2__dup-02',): ['b'],
            ('smth2',): ['c']
        }

    assert get_dups_marked(info, per_series=False) == \
        {
            ('bu__dup-01', 'du'): [1],
            ('bu', 'du'): [2],
            ('smth',): [3],
            ('smth2__dup-02',): ['a'],
            ('smth2__dup-03',): ['b'],
            ('smth2',): ['c']
        }



def test_filter_files():
    # Filtering is currently disabled -- any sequence directory is Ok
    assert(filter_files('/home/mvdoc/dbic/09-run_func_meh/0123432432.dcm'))
    assert(filter_files('/home/mvdoc/dbic/run_func_meh/012343143.dcm'))


def test_md5sum():
    assert md5sum('cryptonomicon') == '1cd52edfa41af887e14ae71d1db96ad1'
    assert md5sum('mysecretmessage') == '07989808231a0c6f522f9d8e34695794'


def test_fix_canceled_runs():
    from collections import namedtuple
    FakeSeqInfo = namedtuple('FakeSeqInfo',
                             ['accession_number', 'series_id',
                              'protocol_name', 'series_description'])

    seqinfo = []
    runname = 'func_run+'
    for i in range(1, 6):
        seqinfo.append(
            FakeSeqInfo('accession1',
                        '{0:02d}-'.format(i) + runname,
                        runname, runname)
        )

    fake_accession2run = {
        'accession1': ['^01-', '^03-']
    }

    with patch.object(reproin, 'fix_accession2run', fake_accession2run):
        seqinfo_ = fix_canceled_runs(seqinfo)

    for i, s in enumerate(seqinfo_, 1):
        output = runname
        if i == 1 or i == 3:
            output = 'cancelme_' + output
        for key in ['series_description', 'protocol_name']:
            value = getattr(s, key)
            assert(value == output)
        # check we didn't touch series_id
        assert(s.series_id == '{0:02d}-'.format(i) + runname)


def test_fix_dbic_protocol():
    from collections import namedtuple
    FakeSeqInfo = namedtuple('FakeSeqInfo',
                             ['accession_number', 'study_description',
                              'field1', 'field2'])
    accession_number = 'A003'
    seq1 = FakeSeqInfo(accession_number,
                       'mystudy',
                       '02-anat-scout_run+_MPR_sag',
                       '11-func_run-life2_acq-2mm692')
    seq2 = FakeSeqInfo(accession_number,
                       'mystudy',
                       'nochangeplease',
                       'nochangeeither')

    seqinfos = [seq1, seq2]
    protocols2fix = {
        md5sum('mystudy'):
            [('scout_run\+', 'THESCOUT-runX'),
             ('run-life[0-9]', 'run+_task-life')],
        re.compile('^my.*'):
            [('THESCOUT-runX', 'THESCOUT')],
        # rely on 'catch-all' to fix up above scout
        '': [('THESCOUT', 'scout')]
    }

    with patch.object(reproin, 'protocols2fix', protocols2fix), \
            patch.object(reproin, 'series_spec_fields', ['field1']):
        seqinfos_ = fix_dbic_protocol(seqinfos)
    assert(seqinfos[1] == seqinfos_[1])
    # field2 shouldn't have changed since I didn't pass it
    assert(seqinfos_[0] == FakeSeqInfo(accession_number,
                                       'mystudy',
                                       '02-anat-scout_MPR_sag',
                                       seq1.field2))

    # change also field2 please
    with patch.object(reproin, 'protocols2fix', protocols2fix), \
            patch.object(reproin, 'series_spec_fields', ['field1', 'field2']):
        seqinfos_ = fix_dbic_protocol(seqinfos)
    assert(seqinfos[1] == seqinfos_[1])
    # now everything should have changed
    assert(seqinfos_[0] == FakeSeqInfo(accession_number,
                                       'mystudy',
                                       '02-anat-scout_MPR_sag',
                                       '11-func_run+_task-life_acq-2mm692'))


def test_sanitize_str():
    assert sanitize_str('super@duper.faster') == 'superduperfaster'
    assert sanitize_str('perfect') == 'perfect'
    assert sanitize_str('never:use:colon:!') == 'neverusecolon'


def test_fixupsubjectid():
    assert fixup_subjectid("abra") == "abra"
    assert fixup_subjectid("sub") == "sub"
    assert fixup_subjectid("sid") == "sid"
    assert fixup_subjectid("sid000030") == "sid000030"
    assert fixup_subjectid("sid0000030") == "sid000030"
    assert fixup_subjectid("sid00030") == "sid000030"
    assert fixup_subjectid("sid30") == "sid000030"
    assert fixup_subjectid("SID30") == "sid000030"


def test_parse_series_spec():
    pdpn = parse_series_spec

    assert pdpn("nondbic_func-bold") == {}
    assert pdpn("cancelme_func-bold") == {}

    assert pdpn("bids_func-bold") == \
           pdpn("func-bold") == \
           {'seqtype': 'func', 'seqtype_label': 'bold'}

    # pdpn("bids_func_ses+_task-boo_run+") == \
    # order and PREFIX: should not matter, as well as trailing spaces
    assert \
        pdpn(" PREFIX:bids_func_ses+_task-boo_run+  ") == \
        pdpn("PREFIX:bids_func_ses+_task-boo_run+") == \
        pdpn("WIP func_ses+_task-boo_run+") == \
        pdpn("bids_func_ses+_run+_task-boo") == \
           {
               'seqtype': 'func',
               # 'seqtype_label': 'bold',
               'session': '+',
               'run': '+',
               'task': 'boo',
            }

    # TODO: fix for that
    assert pdpn("bids_func-pace_ses-1_task-boo_acq-bu_bids-please_run-2__therest") == \
           pdpn("bids_func-pace_ses-1_run-2_task-boo_acq-bu_bids-please__therest") == \
           pdpn("func-pace_ses-1_task-boo_acq-bu_bids-please_run-2") == \
           {
               'seqtype': 'func', 'seqtype_label': 'pace',
               'session': '1',
               'run': '2',
               'task': 'boo',
               'acq': 'bu',
               'bids': 'bids-please'
           }

    assert pdpn("bids_anat-scout_ses+") == \
           {
               'seqtype': 'anat',
               'seqtype_label': 'scout',
               'session': '+',
           }

    assert pdpn("anat_T1w_acq-MPRAGE_run+") == \
           {
                'seqtype': 'anat',
                'run': '+',
                'acq': 'MPRAGE',
                'seqtype_label': 'T1w'
           }

    # Check for currently used {date}, which should also should get adjusted
    # from (date) since Philips does not allow for {}
    assert pdpn("func_ses-{date}") == \
           pdpn("func_ses-(date)") == \
           {'seqtype': 'func', 'session': '{date}'}

    assert pdpn("fmap_dir-AP_ses-01") == \
           {'seqtype': 'fmap', 'session': '01', 'dir': 'AP'}