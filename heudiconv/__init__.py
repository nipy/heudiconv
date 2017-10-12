# set logger handler
import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())

from .info import (__version__, __packagename__)
