# set logger handler
import logging
import os
from .info import __packagename__

try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version

__version__ = version(__name__)

# Rudimentary logging support.
lgr = logging.getLogger(__name__)
logging.basicConfig(
    format='%(levelname)s: %(message)s',
    level=getattr(logging, os.environ.get('HEUDICONV_LOG_LEVEL', 'INFO'))
)
lgr.debug("Starting the abomination")  # just to "run-test" logging
