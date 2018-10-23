"""Utility objects and functions"""
import hashlib
import os
import tempfile
import json
import re
import sys
import shutil
import copy
import stat
import os.path as op
from pathlib import Path
from collections import namedtuple
from glob import glob

import logging
lgr = logging.getLogger(__name__)


seqinfo_fields = [
    'total_files_till_now',  # 0
    'example_dcm_file',      # 1
    'series_id',             # 2
    'dcm_dir_name',          # 3
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
    'date',                  # 24
    'series_uid'             # 25
 ]

SeqInfo = namedtuple('SeqInfo', seqinfo_fields)

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


class TempDirs(object):
    """A helper to centralize handling and cleanup of dirs"""

    def __init__(self):
        self.dirs = []
        self.exists = op.exists
        self.lgr = logging.getLogger('tempdirs')

    def __call__(self, prefix=None):
        tmpdir = tempfile.mkdtemp(prefix=prefix)
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


def anonymize_sid(sid, anon_sid_cmd):
    from subprocess import check_output
    cmd = [anon_sid_cmd, sid]
    return check_output(cmd).strip()


def create_file_if_missing(filename, content):
    """Create file if missing, so we do not
    override any possibly introduced changes"""
    if op.lexists(filename):
        return False
    dirname = op.dirname(filename)
    if not op.exists(dirname):
        os.makedirs(dirname)
    with open(filename, 'w') as f:
        f.write(content)
    return True


def read_config(infile):
    with open(infile, 'rt') as fp:
        info = eval(fp.read())
    return info


def write_config(outfile, info):
    from pprint import PrettyPrinter
    with open(outfile, 'wt') as fp:
        fp.writelines(PrettyPrinter().pformat(info))


def _canonical_dumps(json_obj, **kwargs):
    """ Dump `json_obj` to string, allowing for Python newline bug

    Runs ``json.dumps(json_obj, \*\*kwargs), then removes trailing whitespaces
    added when doing indent in some Python versions. See
    https://bugs.python.org/issue16333. Bug seems to be fixed in 3.4, for now
    fixing manually not only for aestetics but also to guarantee the same
    result across versions of Python.
    """
    out = json.dumps(json_obj, **kwargs)
    if 'indent' in kwargs:
        out = out.replace(' \n', '\n')
    return out


def load_json(filename):
    """Load data from a json file

    Parameters
    ----------
    filename : str
        Filename to load data from.

    Returns
    -------
    data : dict
    """
    with open(filename, 'r') as fp:
        data = json.load(fp)
    return data


def assure_no_file_exists(path):
    """Check if file or symlink (git-annex?) exists, and if so -- remove"""
    if os.path.lexists(path):
        os.unlink(path)


def save_json(filename, data, indent=4):
    """Save data to a json file

    Parameters
    ----------
    filename : str
        Filename to save data in.
    data : dict
        Dictionary to save in json file.

    """
    assure_no_file_exists(filename)
    with open(filename, 'w') as fp:
        fp.write(_canonical_dumps(data, sort_keys=True, indent=indent))


def json_dumps_pretty(j, indent=2, sort_keys=True):
    """Given a json structure, pretty print it by colliding numeric arrays
    into a line.

    If resultant structure differs from original -- throws exception
    """
    js = _canonical_dumps(j, indent=indent, sort_keys=sort_keys)
    # trim away \n and spaces between entries of numbers
    js_ = re.sub(
        '[\n ]+("?[-+.0-9e]+"?,?) *\n(?= *"?[-+.0-9e]+"?)', r' \1',
        js, flags=re.MULTILINE)
    # uniform no spaces before ]
    js_ = re.sub(" *\]", "]", js_)
    # uniform spacing before numbers
    js_ = re.sub('  *("?[-+.0-9e]+"?)(?P<space> ?)[ \n]*',
                 r' \1\g<space>', js_)
    # no spaces after [
    js_ = re.sub('\[ ', '[', js_)
    # the load from the original dump and reload from tuned up
    # version should result in identical values since no value
    # must be changed, just formatting.
    j_just_reloaded = json.loads(js)
    j_tuned = json.loads(js_)

    assert j_just_reloaded == j_tuned, \
       "Values differed when they should have not. "\
       "Report to the heudiconv developers"

    return js_


def treat_infofile(filename):
    """Tune up generated .json file (slim down, pretty-print for humans).
    """
    with open(filename) as f:
        j = json.load(f)

    j_slim = slim_down_info(j)
    j_pretty = json_dumps_pretty(j_slim, indent=2, sort_keys=True)

    set_readonly(filename, False)
    with open(filename, 'wt') as fp:
        fp.write(j_pretty)
    set_readonly(filename)


def slim_down_info(j):
    """Given an aggregated info structure, removes excessive details

    Such as CSA fields, and SourceImageSequence which on Siemens files could be
    huge and not providing any additional immediately usable information.
    If needed, could be recovered from stored DICOMs
    """
    j = copy.deepcopy(j)  # we will do in-place modification on a copy
    dicts = []
    # poor man programming for now
    if 'const' in j.get('global', {}):
        dicts.append(j['global']['const'])
    if 'samples' in j.get('time', {}):
        dicts.append(j['time']['samples'])
    for d in dicts:
        for k in list(d.keys()):
            if k.startswith('Csa') or k.lower() in {'sourceimagesequence'}:
                del d[k]
    return j


def get_known_heuristic_names():
    """Return a list of heuristic names present under heudiconv/heuristics"""
    import heudiconv.heuristics
    candidates = {
        op.splitext(op.basename(x))[0]
        for hp in heudiconv.heuristics.__path__
        for x in glob(op.join(hp, '*.py')) + glob(op.join(hp, '*.py[co]'))
    }
    return sorted(
        filter(
            lambda c: not (c.startswith('test_') or c.startswith('_')),
            candidates
        )
    )


def load_heuristic(heuristic):
    """Load heuristic from the file, return the module
    """
    if os.path.sep in heuristic or os.path.lexists(heuristic):
        heuristic_file = op.realpath(heuristic)
        path, fname = op.split(heuristic_file)
        try:
            old_syspath = sys.path[:]
            sys.path.append(path)
            mod = __import__(fname.split('.')[0])
            mod.filename = heuristic_file
        finally:
            sys.path = old_syspath
    else:
        from importlib import import_module
        try:
            mod = import_module('heudiconv.heuristics.%s' % heuristic)
            mod.filename = mod.__file__.rstrip('co')  # remove c or o from pyc/pyo
        except Exception as exc:
            raise ImportError(
                "Failed to import heuristic %s: %s"
                % (heuristic, exc)
            )
    return mod


def get_heuristic_description(name, full=False):
    try:
        mod = load_heuristic(name)
        desc = (getattr(mod, '__doc__', '') or '').strip()
        return desc.split(os.linesep)[0] if not full else desc
    except Exception as exc:
        return "Failed to load: %s" % exc


def get_known_heuristics_with_descriptions():
    from collections import OrderedDict
    heuristics = OrderedDict()
    for name in get_known_heuristic_names():
        heuristics[name] = get_heuristic_description(name, full=False)
    return heuristics


def safe_copyfile(src, dest, overwrite=False):
    """Copy file but blow if destination name already exists
    """
    if op.isdir(dest):
        dest = op.join(dest, op.basename(src))
    if op.lexists(dest):
        if not overwrite:
            raise RuntimeError(
                "was asked to copy %s but destination already exists: %s"
                % (src, dest)
            )
        os.unlink(dest)
    shutil.copyfile(src, dest)


# Globals to check filewriting permissions
ALL_CAN_WRITE = (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
ALL_CAN_READ = (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
assert ALL_CAN_READ >> 1 == ALL_CAN_WRITE  # Assumption in the code

def set_readonly(path, read_only=True):
    """Make file read only or writeable while preserving "access levels"

    So if file was not readable by others, it should remain not readable by
    others.

    Parameters
    ----------
    path : str
    read_only : bool, optional
        If True (default) - would make it read-only. If False, would make it
        writeable for levels where it is readable

    """

    # get current permissions
    perms = stat.S_IMODE(os.lstat(path).st_mode)
    # set new permissions
    if read_only:
        new_perms = perms & (~ALL_CAN_WRITE)
    else:
        # need to set only for those which had read bit set
        # read bit is <<1 away from write bit
        whocanread = perms & ALL_CAN_READ
        thosecanwrite = whocanread >> 1
        new_perms = perms | thosecanwrite
    # apply and return those target permissions
    os.chmod(path, new_perms)
    return new_perms


def is_readonly(path):
    """Return True if it is a fully read-only file (dereferences the symlink)
    """
    # get current permissions
    perms = stat.S_IMODE(os.lstat(os.path.realpath(path)).st_mode)
    # should be true if anyone is allowed to write
    return not bool(perms & ALL_CAN_WRITE)


def clear_temp_dicoms(item_dicoms):
    """Ensures DICOM temporary directories are safely cleared"""
    try:
        tmp = Path(op.commonprefix(item_dicoms)).parents[1]
    except IndexError:
        return
    if (str(tmp.parent) == tempfile.gettempdir()
        and str(tmp.stem).startswith('heudiconvDCM')
        and op.exists(str(tmp))):
        # clean up directory holding dicoms
        shutil.rmtree(str(tmp))


def file_md5sum(filename):
    with open(filename, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


# Borrowed from DataLad (MIT license), with "archives" functionality commented
# out
class File(object):
    """Helper for a file entry in the create_tree/@with_tree

    It allows to define additional settings for entries
    """
    def __init__(self, name, executable=False):
        """

        Parameters
        ----------
        name : str
          Name of the file
        executable: bool, optional
          Make it executable
        """
        self.name = name
        self.executable = executable

    def __str__(self):
        return self.name


def create_tree(path, tree, archives_leading_dir=True):
    """Given a list of tuples (name, load) or a dict create such a tree

    if load is a tuple or a dict itself -- that would create either a subtree
    or an archive with that content and place it into the tree if name ends
    with .tar.gz
    """
    lgr.log(5, "Creating a tree under %s", path)
    if not op.exists(path):
        os.makedirs(path)

    if isinstance(tree, dict):
        tree = tree.items()

    for file_, load in tree:
        if isinstance(file_, File):
            executable = file_.executable
            name = file_.name
        else:
            executable = False
            name = file_
        full_name = op.join(path, name)
        if isinstance(load, (tuple, list, dict)):
            # if name.endswith('.tar.gz') or name.endswith('.tar') or name.endswith('.zip'):
            #     create_tree_archive(path, name, load, archives_leading_dir=archives_leading_dir)
            # else:
            create_tree(full_name, load, archives_leading_dir=archives_leading_dir)
        else:
            with open(full_name, 'w') as f:
                if sys.version_info[0] == 2 and not isinstance(load, str):
                    load = load.encode('utf-8')
                f.write(load)
        if executable:
            os.chmod(full_name, os.stat(full_name).st_mode | stat.S_IEXEC)