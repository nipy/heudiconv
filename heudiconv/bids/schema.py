from pathlib import Path
import yaml


def _load_entities_order():
    # we carry the copy of the schema
    schema_p = Path(__file__).parent / "data" / "schema"
    with (schema_p / "objects" / "entities.yaml").open() as f:
        entities = yaml.load(f)

    with (schema_p / "rules" / "entities.yaml").open() as f:
        entities_full_order = yaml.load(f)

    # map from full name to short "entity"
    return [entities[e]["entity"] for e in entities_full_order]


class BIDSFile:
    """ as defined in https://bids-specification.readthedocs.io/en/stable/99-appendices/04-entity-table.html
    which might soon become machine readable
    order matters
    """

    _known_entities = _load_entities_order()


# TEMP: just for now, could be moved/removed
def test_BIDSFile():
    assert BIDSFile._known_entities[:2] == ['sub', 'ses']
    print(BIDSFile._known_entities)