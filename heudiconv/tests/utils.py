from functools import wraps
import os
import os.path as op
import sys

import heudiconv.heuristics


HEURISTICS_PATH = op.join(heudiconv.heuristics.__path__[0])
TESTS_DATA_PATH = op.join(op.dirname(__file__), 'data')

import logging
lgr = logging.getLogger(__name__)


def gen_heudiconv_args(datadir, outdir, subject, heuristic_file,
                       anon_cmd=None, template=None, xargs=None):
    heuristic = op.realpath(op.join(HEURISTICS_PATH, heuristic_file))

    if template:
        # use --dicom_dir_template
        args = ["-d", op.join(datadir, template)]
    else:
        args = ["--files", datadir]

    args.extend([
            "-c", "dcm2niix",
            "-o", outdir,
            "-s", subject,
            "-f", heuristic,
            "--bids",
            "--minmeta",]
            )
    if anon_cmd:
        args += ["--anon-cmd", op.join(op.dirname(__file__), anon_cmd), "-a", outdir]
    if xargs:
        args += xargs

    return args


def fetch_data(tmpdir, dataset, getpath=None):
    """
    Utility function to interface with datalad database.
    Performs datalad `install` and datalad `get` operations.

    Parameters
    ----------
    tmpdir : str
        directory to temporarily store data
    dataset : str
        dataset path from `http://datasets-tests.datalad.org`
    getpath : str [optional]
        exclusive path to get

    Returns
    -------
    targetdir : str
        directory with installed dataset
    """
    from datalad import api
    targetdir = op.join(tmpdir, op.basename(dataset))
    ds = api.install(path=targetdir,
                source='http://datasets-tests.datalad.org/{}'.format(dataset))

    getdir = targetdir + (op.sep + getpath if getpath is not None else '')
    ds.get(getdir)
    return targetdir


def assert_cwd_unchanged(ok_to_chdir=False):
    """Decorator to test whether the current working directory remains unchanged

    Provenance: based on the one in datalad, but simplified.

    Parameters
    ----------
    ok_to_chdir: bool, optional
      If True, allow to chdir, so this decorator would not then raise exception
      if chdir'ed but only return to original directory
    """

    def decorator(func=None):  # =None to avoid pytest treating it as a fixture
        @wraps(func)
        def newfunc(*args, **kwargs):
            cwd_before = os.getcwd()
            exc = None
            try:
                return func(*args, **kwargs)
            except Exception as exc_:
                exc = exc_
            finally:
                try:
                    cwd_after = os.getcwd()
                except OSError as e:
                    lgr.warning("Failed to getcwd: %s" % e)
                    cwd_after = None

                if cwd_after != cwd_before:
                    os.chdir(cwd_before)
                    if not ok_to_chdir:
                        lgr.warning(
                            "%s changed cwd to %s. Mitigating and changing back to %s"
                            % (func, cwd_after, cwd_before))
                        # If there was already exception raised, we better reraise
                        # that one since it must be more important, so not masking it
                        # here with our assertion
                        if exc is None:
                            assert cwd_before == cwd_after, \
                                     "CWD changed from %s to %s" % (cwd_before, cwd_after)

                if exc is not None:
                    raise exc
        return newfunc

    return decorator
