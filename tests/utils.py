import hashlib
import os.path as op
import heudiconv

def md5sum(filename):
    with open(filename, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def gen_heudiconv_args(datadir, outdir, subject, heuristic_file, xargs=None):
    heuristic = op.realpath(op.join(op.dirname(heudiconv.__file__),
                                    '..',
                                    'heuristics',
                                    heuristic_file))
    args = ["-d", op.join(datadir, 'sourcedata/{subject}/*/*/*.tgz'),
            "-c", "dcm2niix",
            "-o", outdir,
            "-s", subject,
            "-f", heuristic,
            "--bids",]
    if xargs:
        args += xargs

    return args


def fetch_data(tmpdir, subject):
    """Fetches some test dicoms using datalad"""
    from datalad import api
    targetdir = op.join(tmpdir, 'QA')
    api.install(path=targetdir, source='http://datasets-tests.datalad.org/dbic/QA')
    api.get('{}/sourcedata/{}'.format(targetdir, subject))
    return targetdir
