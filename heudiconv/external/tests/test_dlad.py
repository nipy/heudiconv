from ..dlad import mark_sensitive
from datalad.api import Dataset
from ...utils import create_tree


def test_mark_sensitive(tmpdir):
    ds = Dataset(str(tmpdir)).create(force=True)
    create_tree(
        str(tmpdir),
        {
            'f1': 'd1',
            'f2': 'd2',
            'g1': 'd3',
            'g2': 'd1',
         }
    )
    ds.add('.')
    mark_sensitive(ds, 'f*')
    all_meta = dict(ds.repo.get_metadata('.'))
    target_rec = {'distribution-restrictions': ['sensitive']}
    # g2 since the same content
    assert not all_meta.pop('g1', None)  # nothing or empty record
    assert all_meta == {'f1': target_rec, 'f2': target_rec, 'g2': target_rec}
