from collections import OrderedDict
from random import shuffle

import pytest

from heudiconv.bids import BIDSFile


def test_BIDSFile_known_entries():
    assert BIDSFile._known_entities[:2] == ['sub', 'ses']
    assert len(BIDSFile._known_entities) > 10  # we do have many
    assert 'run' in BIDSFile._known_entities


def test_BIDSFile():
    """ Tests for the BIDSFile class """

    # define entities in the correct order:
    sorted_entities = [
        ('sub', 'Jason'),
        ('acq', 'Treadstone'),
        ('run', '2'),
        ('echo', '1'),
    ]
    # 'sub-Jason_acq-Treadstone_run-2_echo-1':
    expected_sorted_str = '_'.join(['-'.join(e) for e in sorted_entities])
    # expected BIDSFile:
    suffix = 'T1w'
    extension = 'nii.gz'
    expected_bids_file = BIDSFile(OrderedDict(sorted_entities), suffix, extension)

    # entities in random order:
    idcs = list(range(len(sorted_entities)))
    shuffle(idcs)
    shuffled_entities = [sorted_entities[i] for i in idcs]
    shuffled_str = '_'.join(['-'.join(e) for e in shuffled_entities])

    # Test __eq__ method.
    # It should consider equal BIDSFiles with the same entities even in different order:
    assert BIDSFile(OrderedDict(shuffled_entities), suffix, extension) == expected_bids_file

    # Test __getitem__:
    assert all([expected_bids_file[k] == v for k, v in shuffled_entities])

    # Test filename parser and  __str__ method:
    # Note: the __str__ method should return entities in the correct order
    ending = '_T1w.nii.gz'            # suffix + extension
    my_bids_file = BIDSFile.parse(shuffled_str + ending)
    assert my_bids_file == expected_bids_file
    assert str(my_bids_file) == expected_sorted_str + ending

    ending = '.json'                  # just extension
    my_bids_file = BIDSFile.parse(shuffled_str + ending)
    assert my_bids_file.suffix == ''
    assert str(my_bids_file) == expected_sorted_str + ending

    ending = '_T1w'                   # just suffix
    my_bids_file = BIDSFile.parse(shuffled_str + ending)
    assert my_bids_file.extension is None
    assert str(my_bids_file) == expected_sorted_str + ending

    # Complain if entity 'sub' is not set:
    with pytest.raises(ValueError) as e_info:
        assert str(BIDSFile.parse('dir-reversed.json'))
        assert 'sub-' in e_info.value

    # Test set method:
    # -for a new entity, just set it without a complaint:
    my_bids_file['dir'] = 'AP'
    assert my_bids_file['dir'] == 'AP'
    # -for an existing entity, don't change it by default:
    my_bids_file['echo'] = '2'
    assert my_bids_file['echo'] == expected_bids_file['echo']  # still the original value
    # -for an existing entity, you can overwrite it with "set":
    my_bids_file.set('echo', '2')
    assert my_bids_file['echo'] == '2'