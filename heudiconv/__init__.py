# set logger handler
import logging
import os
from .info import (__version__, __packagename__)

# Rudimentary logging support.
lgr = logging.getLogger(__name__)
logging.basicConfig(
    format='%(levelname)s: %(message)s',
    level=getattr(logging, os.environ.get('HEUDICONV_LOG_LEVEL', 'INFO'))
)
lgr.debug("Starting the abomination")  # just to "run-test" logging

try:
    tmpdirs
except NameError:
    import atexit
    tmpdirs = set()

    def _clean_tmpdirs():
        """Cleanup tracked temporary directories"""
    import shutil

    for tmpdir in tmpdirs:
        try:
            shutil.rmtree(tmpdir)
        except FileNotFoundError:
            pass
    atexit.register(_clean_tmpdirs)
