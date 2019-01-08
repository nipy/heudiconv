import os.path as op
import heudiconv.heuristics

HEURISTICS_PATH = op.join(heudiconv.heuristics.__path__[0])
TESTS_DATA_PATH = op.join(op.dirname(__file__), 'data')


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
    api.install(path=targetdir,
                source='http://datasets-tests.datalad.org/{}'.format(dataset))

    getdir = targetdir + (op.sep + getpath if getpath is not None else '')
    api.get(getdir)
    return targetdir
