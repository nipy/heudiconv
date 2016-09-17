# may be there is a more kosher way but didn't want to do evals etc
# import sys
# from os.path import dirname
# from os.path import join as opj
# from os.path import pardir
#
# import logging
# lgr = logging.getLogger('heudiconv')
#
# bin_dir = opj(dirname(__file__), pardir, 'bin')
# # with open(opj(bin_dir, 'heudiconv')) as f:
# #     heudiconv = eval(f.read())
# try:
#     sys.path.insert(0, bin_dir)
#     mod = __import__('heudiconv', level=0)
# except Exception as e:
#     raise RuntimeError("Failed to import heudiconv: %s" % e)
# finally:
#     if bin_dir in sys.path:
#         path = sys.path.pop(0)
#         if path != bin_dir:
#             lgr.warning(
#                 "Popped %s when expected %s. Restoring!!!" % (path, bin_dir))
#             sys.path.insert(0, path)

# symlinks rule!
from . import heudiconv