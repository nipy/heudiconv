import logging

from ._version import __version__
from .info import __packagename__

__all__ = ["__packagename__", "__version__"]

lgr = logging.getLogger(__name__)
lgr.debug("Starting the abomination")  # just to "run-test" logging
