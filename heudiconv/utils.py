import os
import os.path as op
from tempfile import mkdtemp
from glob import glob

from collections import namedtuple

class TempDirs(object):
    """A helper to centralize handling and cleanup of dirs"""

    def __init__(self):
        self.dirs = []
        self.exists = op.exists
        self.lgr = logging.getLogger('tempdirs')

    def __call__(self, prefix=None):
        tmpdir = mkdtemp(prefix=prefix)
        self.dirs.append(tmpdir)
        return tmpdir

    def __del__(self):
        try:
            self.cleanup()
        except AttributeError:
            pass

    def cleanup(self):
        self.lgr.debug("Removing %d temporary directories", len(self.dirs))
        for t in self.dirs[:]:
            self.lgr.debug("Removing %s", t)
            if self:
                self.rmtree(t)
        self.dirs = []

    def rmtree(self, tmpdir):
        if self.exists(tmpdir):
            shutil.rmtree(tmpdir)
        if tmpdir in self.dirs:
            self.dirs.remove(tmpdir)

def docstring_parameter(*sub):
    """ Borrowed from https://stackoverflow.com/a/10308363/6145776 """
    def dec(obj):
        obj.__doc__ = obj.__doc__.format(*sub)
        return obj
    return dec

SeqInfo = namedtuple(
    'SeqInfo',
    ['total_files_till_now',  # 0
     'example_dcm_file',      # 1
     'series_id',             # 2
     'unspecified1',          # 3
     'unspecified2',          # 4
     'unspecified3',          # 5
     'dim1', 'dim2', 'dim3', 'dim4', # 6, 7, 8, 9
     'TR', 'TE',              # 10, 11
     'protocol_name',         # 12
     'is_motion_corrected',   # 13
     'is_derived',            # 14
     'patient_id',            # 15
     'study_description',     # 16
     'referring_physician_name', # 17
     'series_description',    # 18
     'sequence_name',         # 19
     'image_type',            # 20
     'accession_number',      # 21
     'patient_age',           # 22
     'patient_sex',           # 23
     'date'                   # 24
     ]
)

StudySessionInfo = namedtuple(
    'StudySessionInfo',
    [
        'locator',  # possible prefix identifying the study, e.g.
                    # PI/dataset or just a dataset or empty (default)
                    # Note that ATM there should be no multiple DICOMs with the
                    # same StudyInstanceUID which would collide, i.e point to
                    # the same subject/session. So 'locator' is pretty much an
                    # assignment from StudyInstanceUID into some place within
                    # hierarchy
        'session',  # could be None
        'subject',  # should be some ID defined either in cmdline or deduced
    ]
)

def get_anonymized_sid(sid, anon_sid_cmd):
    anon_sid = sid
    if anon_sid_cmd is not None:
        from subprocess import check_output
        anon_sid = check_output([anon_sid_cmd, sid]).strip()
        lgr.info("Annonimized sid %s into %s", sid, anon_sid)
    return anon_sid

def create_file_if_missing(filename, content):
    """Create file if missing, so we do not
    override any possibly introduced changes"""
    if exists(filename):
        return False
    with open(filename, 'w') as f:
        f.write(content)
    return True

def mark_sensitive(ds, path_glob=None):
    """

    Parameters
    ----------
    ds : Dataset to operate on
    path_glob : str, optional
      glob of the paths within dataset to work on
    Returns
    -------
    None
    """
    sens_kwargs = dict(
        init=[('distribution-restrictions', 'sensitive')]
    )
    if path_glob:
        paths = glob(op.join(ds.path, path_glob))
        if not paths:
            return
        sens_kwargs['path'] = paths
    ds.metadata(**sens_kwargs)
