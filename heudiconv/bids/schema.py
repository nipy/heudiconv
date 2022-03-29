from pathlib import Path
import re
import yaml

from heudiconv.utils import remove_prefix

import logging

lgr = logging.getLogger(__name__)


def _load_entities_order():
    # we carry the copy of the schema
    schema_p = Path(__file__).parent / "data" / "schema"
    with (schema_p / "objects" / "entities.yaml").open() as f:
        entities = yaml.load(f, yaml.SafeLoader)

    with (schema_p / "rules" / "entities.yaml").open() as f:
        entities_full_order = yaml.load(f, yaml.SafeLoader)

    # map from full name to short "entity"
    return [entities[e]["entity"] for e in entities_full_order]


class BIDSFile:
    """ as defined in https://bids-specification.readthedocs.io/en/stable/99-appendices/04-entity-table.html
    which might soon become machine readable
    order matters
    """

    _known_entities = _load_entities_order()

    def __init__(self, entities, suffix, extension):
        self._entities = entities
        self._suffix = suffix
        self._extension = extension

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if (
            all([other[k] == v for k, v in self._entities.items()])
            and self.extension == other.extension
            and self.suffix == other.suffix
        ):
            return True
        else:
            return False

    @classmethod
    def parse(cls, filename):
        """ Parse the filename for BIDS entities, suffix and extension """
        # use re.findall to find all lower-case-letters + '-' + alphanumeric + '_' pairs:
        entities_list = re.findall('([a-z]+)-([a-zA-Z0-9]+)[_]*', filename)
        # keep only those in the _known_entities list:
        entities = {k: v for k, v in entities_list if k in BIDSFile._known_entities}
        # get whatever comes after the last key-value pair, and remove any '_' that
        # might come in front:
        ending = filename.split('-'.join(entities_list[-1]))[-1]
        ending = remove_prefix(ending, '_')
        # the first dot ('.') separates the suffix from the extension:
        if '.' in ending:
            suffix, extension = ending.split('.', 1)
        else:
            suffix, extension = ending, None
        return BIDSFile(entities, suffix, extension)

    def __str__(self):
        """ reconstitute in a legit BIDS filename using the order from entity table """
        if 'sub' not in self._entities:
            raise ValueError('The \'sub-\' entity is mandatory')
        # reconstitute the ending for the filename:
        suffix = '_' + self.suffix if self.suffix else ''
        extension = '.' + self.extension if self.extension else ''
        return '_'.join(
            ['-'.join([e, self._entities[e]]) for e in self._known_entities if e in self._entities]
        ) + suffix + extension

    def __getitem__(self, entity):
        return self._entities[entity] if entity in self._entities else None

    def __setitem__(self, entity, value):  # would puke with some exception if already known
        return self.set(entity, value, overwrite=False)

    def set(self, entity, value, overwrite=True):
        if entity not in self._entities:
            # just set it; no complains here
            self._entities[entity] = value
        elif overwrite:
            lgr.warning("Overwriting the entity %s from %s to %s for file %s",
                        str(entity),
                        str(self[entity]),
                        str(value),
                        self.__str__()
                        )
            self._entities[entity] = value
        else:
            # if it already exists, and overwrite is false:
            lgr.warning("Setting the entity %s to %s for file %s failed",
                        str(entity),
                        str(value),
                        self.__str__()
                        )

    @property  # as needed make them RW
    def suffix(self):
        return self._suffix

    @property
    def extension(self):
        return self._extension
