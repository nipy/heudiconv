"""Utility objects and functions"""
from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping as MappingABC
import copy
import datetime
from glob import glob
import hashlib
import json
from json.decoder import JSONDecodeError
import logging
import os
import os.path as op
from pathlib import Path
import re
import shutil
import stat
from subprocess import check_output
import sys
import tempfile
from time import sleep
from types import ModuleType
from typing import (
    Any,
    AnyStr,
    Hashable,
    Mapping,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)
import warnings

import pydicom as dcm
from pydicom.tag import TagType

lgr = logging.getLogger(__name__)

T = TypeVar("T")
V = TypeVar("V")


class SeqInfo(NamedTuple):
    total_files_till_now: int  # 0
    example_dcm_file: str  # 1
    series_id: str  # 2
    dcm_dir_name: str  # 3
    series_files: int  # 4
    unspecified: str  # 5
    dim1: int  # 6
    dim2: int  # 7
    dim3: int  # 8
    dim4: int  # 9
    TR: float  # 10
    TE: float  # 11
    protocol_name: str  # 12
    is_motion_corrected: bool  # 13
    is_derived: bool  # 14
    patient_id: Optional[str]  # 15
    study_description: str  # 16
    referring_physician_name: str  # 17
    series_description: str  # 18
    sequence_name: str  # 19
    image_type: tuple[str, ...]  # 20
    accession_number: str  # 21
    patient_age: Optional[str]  # 22
    patient_sex: Optional[str]  # 23
    date: Optional[str]  # 24
    series_uid: Optional[str]  # 25
    time: Optional[str]  # 26
    custom: Optional[Hashable]  # 27


class StudySessionInfo(NamedTuple):
    # possible prefix identifying the study, e.g.  PI/dataset or just a dataset
    # or empty (default) Note that ATM there should be no multiple DICOMs with
    # the same StudyInstanceUID which would collide, i.e point to the same
    # subject/session. So 'locator' is pretty much an assignment from
    # StudyInstanceUID into some place within hierarchy
    locator: Optional[str]

    session: Optional[str]

    # should be some ID defined either in cmdline or deduced
    subject: Optional[str]


class TempDirs:
    """A helper to centralize handling and cleanup of dirs"""

    def __init__(self) -> None:
        self.dirs: list[str] = []
        self.lgr: logging.Logger = logging.getLogger("tempdirs")

    def __call__(self, prefix: Optional[str] = None) -> str:
        tmpdir = tempfile.mkdtemp(prefix=prefix)
        self.dirs.append(tmpdir)
        return tmpdir

    def __del__(self) -> None:
        try:
            self.cleanup()
        except AttributeError:
            pass

    def exists(self, path: str) -> bool:
        return op.exists(path)

    def cleanup(self) -> None:
        self.lgr.debug("Removing %d temporary directories", len(self.dirs))
        for t in self.dirs[:]:
            self.lgr.debug("Removing %s", t)
            if self:
                self.rmtree(t)
        self.dirs = []

    def rmtree(self, tmpdir: str) -> None:
        if self.exists(tmpdir):
            shutil.rmtree(tmpdir)
        if tmpdir in self.dirs:
            self.dirs.remove(tmpdir)


def docstring_parameter(*sub: str) -> Callable[[T], T]:
    """Borrowed from https://stackoverflow.com/a/10308363/6145776"""

    def dec(obj: T) -> T:
        assert obj.__doc__ is not None
        obj.__doc__ = obj.__doc__.format(*sub)
        return obj

    return dec


def anonymize_sid(sid: AnyStr, anon_sid_cmd: str) -> AnyStr:
    """
    Raises
    ------
    ValueError
      if script returned an empty string (after whitespace stripping),
      or output with multiple words/lines.
    """
    cmd: list[str | bytes] = [anon_sid_cmd, sid]
    shell_return = check_output(cmd)

    if isinstance(shell_return, bytes) and isinstance(sid, str):
        anon_sid = shell_return.decode()
    else:
        anon_sid = shell_return

    anon_sid = anon_sid.strip()
    if not anon_sid:
        raise ValueError(f"{anon_sid_cmd!r} {sid!r} returned empty sid")
    # rudimentary check for sanity: no multiple lines or words (in general
    # ok, but not ok for BIDS) in the output
    if len(anon_sid.split()) > 1:
        raise ValueError(f"{anon_sid_cmd!r} {sid!r} returned multiline output")
    return anon_sid


def create_file_if_missing(filename: str, content: str) -> bool:
    """Create file if missing, so we do not
    override any possibly introduced changes"""
    if op.lexists(filename):
        return False
    dirname = op.dirname(filename)
    if not op.exists(dirname):
        os.makedirs(dirname)
    with open(filename, "w") as f:
        f.write(content)
    return True


def read_config(infile: str) -> dict:
    with open(infile, "r") as fp:
        info = cast(dict, eval(fp.read()))
    return info


def write_config(outfile: str, info: dict) -> None:
    from pprint import PrettyPrinter

    with open(outfile, "w") as fp:
        fp.writelines(PrettyPrinter().pformat(info))


def load_json(filename: str | Path, retry: int = 0) -> Any:
    """Load data from a json file

    Parameters
    ----------
    filename : str or Path
        Filename to load data from.
    retry: int, optional
        Number of times to retry opening/loading the file in case of
        failure.  Code will sleep for 0.1 seconds between retries.
        Could be used in code which is not sensitive to order effects
        (e.g. like populating bids templates where the last one to
        do it, would make sure it would be the correct/final state).

    Returns
    -------
    data : dict
    """
    assert retry >= 0
    for i in range(retry + 1):  # >= 10 sec wait
        try:
            try:
                with open(filename, "r") as fp:
                    data = json.load(fp)
                    break
            except JSONDecodeError:
                lgr.error("{fname} is not a valid json file".format(fname=filename))
                raise
        except (JSONDecodeError, FileNotFoundError) as exc:
            if i >= retry:
                raise
            lgr.warning("Caught %s. Will retry again", exc)
            sleep(0.1)
            continue

    return data


def assure_no_file_exists(path: str | Path) -> None:
    """Check if file or symlink (git-annex?) exists, and if so -- remove"""
    if os.path.lexists(path):
        os.unlink(path)


def save_json(
    filename: str | Path,
    data: Any,
    indent: int = 2,
    sort_keys: bool = True,
    pretty: bool = False,
) -> None:
    """Save data to a json file

    Parameters
    ----------
    filename : str or Path
        Filename to save data in.
    data : dict
        Dictionary to save in json file.
    indent : int, optional
    sort_keys : bool, optional
    pretty : bool, optional

    """
    assure_no_file_exists(filename)
    j: Optional[str] = None
    if pretty:
        try:
            j = json_dumps_pretty(data, sort_keys=sort_keys, indent=indent)
        except AssertionError as exc:
            pretty = False
            lgr.warning(
                "Prettyfication of .json failed (%s).  "
                "Original .json will be kept as is.  Please share (if you "
                "could) "
                "that file (%s) with HeuDiConv developers" % (str(exc), filename)
            )
    if not pretty:
        j = json_dumps(data, sort_keys=sort_keys, indent=indent)
    assert j is not None  # one way or another it should have been set to a str
    with open(filename, "w") as fp:
        fp.write(j)


def json_dumps(json_obj: Any, indent: int = 2, sort_keys: bool = True) -> str:
    """Unified (default indent and sort_keys) invocation of json.dumps"""
    return json.dumps(json_obj, indent=indent, sort_keys=sort_keys)


def json_dumps_pretty(j: Any, indent: int = 2, sort_keys: bool = True) -> str:
    """Given a json structure, pretty print it by colliding numeric arrays
    into a line.

    If resultant structure differs from original -- throws exception
    """
    js = json_dumps(j, indent=indent, sort_keys=sort_keys)
    # trim away \n and spaces between entries of numbers
    js_ = re.sub(
        '[\n ]+("?[-+.0-9e]+"?,?) *\n(?= *"?[-+.0-9e]+"?)',
        r" \1",
        js,
        flags=re.MULTILINE,
    )
    # uniform no spaces before ]
    js_ = re.sub(r" *\]", "]", js_)
    # uniform spacing before numbers
    # But that thing could screw up dates within strings which would have 2 spaces
    # in a date like Mar  3 2017, so we do negative lookahead to avoid changing
    # in those cases
    # import pdb; pdb.set_trace()
    js_ = re.sub(
        r"(?<!\w{3})"  # negative lookbehind for the month
        r'  *("?[-+.0-9e]+"?)'
        r"(?! [123]\d{3})"  # negative lookahead for a year
        r"(?P<space> ?)[ \n]*",
        r" \1\g<space>",
        js_,
    )
    # no spaces after [
    js_ = re.sub(r"\[ ", "[", js_)
    # the load from the original dump and reload from tuned up
    # version should result in identical values since no value
    # must be changed, just formatting.
    j_just_reloaded = json.loads(js)
    j_tuned = json.loads(js_)

    assert j_just_reloaded == j_tuned, (
        "Values differed when they should have not. "
        "Report to the heudiconv developers"
    )

    return js_


def update_json(
    json_file: str | Path, new_data: dict[str, Any], pretty: bool = False
) -> None:
    """
    Adds a given field (and its value) to a json file

    Parameters
    -----------
    json_file : str or Path
        path for the corresponding json file
    new_data : dict
        pair of "key": "value" to add to the json file
    pretty : bool
        argument to be passed to save_json
    """
    for key, value in new_data.items():
        lgr.debug(
            'File "{f}": Setting {k} to {v}'.format(
                f=json_file,
                k=key,
                v=value,
            )
        )

    with open(json_file) as f:
        data = json.load(f)
    data.update(new_data)
    save_json(json_file, data, pretty=pretty)


def treat_infofile(filename: str) -> None:
    """Tune up generated .json file (slim down, pretty-print for humans)."""
    j = load_json(filename)
    j_slim = slim_down_info(j)
    save_json(filename, j_slim, sort_keys=True, pretty=True)
    set_readonly(filename)


def slim_down_info(j: dict[str, Any]) -> dict[str, Any]:
    """Given an aggregated info structure, removes excessive details

    Such as CSA fields, and SourceImageSequence which on Siemens files could be
    huge and not providing any additional immediately usable information.
    If needed, could be recovered from stored DICOMs
    """
    j = copy.deepcopy(j)  # we will do in-place modification on a copy
    dicts: list[dict[str, Any]] = []
    # poor man programming for now
    if "const" in j.get("global", {}):
        dicts.append(j["global"]["const"])
    if "samples" in j.get("time", {}):
        dicts.append(j["time"]["samples"])
    for d in dicts:
        for k in list(d.keys()):
            if k.startswith("Csa") or k.lower() in {"sourceimagesequence"}:
                del d[k]
    return j


def get_known_heuristic_names() -> list[str]:
    """Return a list of heuristic names present under heudiconv/heuristics"""
    import heudiconv.heuristics

    candidates = {
        op.splitext(op.basename(x))[0]
        for hp in heudiconv.heuristics.__path__
        for x in glob(op.join(hp, "*.py")) + glob(op.join(hp, "*.py[co]"))
    }
    return sorted(
        filter(lambda c: not (c.startswith("test_") or c.startswith("_")), candidates)
    )


def load_heuristic(heuristic: str) -> ModuleType:
    """Load heuristic from the file, return the module"""
    if os.path.sep in heuristic or os.path.lexists(heuristic):
        heuristic_file = op.realpath(heuristic)
        path, fname = op.split(heuristic_file)
        try:
            old_syspath = sys.path[:]
            sys.path.insert(0, path)
            mod = __import__(fname.split(".")[0])
            mod.filename = heuristic_file  # type: ignore[attr-defined]
        finally:
            sys.path = old_syspath
    else:
        from importlib import import_module

        try:
            mod = import_module("heudiconv.heuristics.%s" % heuristic)
            assert mod.__file__ is not None
            # remove c or o from pyc/pyo
            mod.filename = mod.__file__.rstrip("co")  # type: ignore[attr-defined]
        except Exception as exc:
            raise ImportError("Failed to import heuristic %s: %s" % (heuristic, exc))
    return mod


def get_heuristic_description(name: str, full: bool = False) -> str:
    try:
        mod = load_heuristic(name)
        desc = (getattr(mod, "__doc__", "") or "").strip()
        return desc.split(os.linesep)[0] if not full else desc
    except Exception as exc:
        return "Failed to load: %s" % exc


def get_known_heuristics_with_descriptions() -> dict[str, str]:
    from collections import OrderedDict

    heuristics = OrderedDict()
    for name in get_known_heuristic_names():
        heuristics[name] = get_heuristic_description(name, full=False)
    return heuristics


def safe_copyfile(src: str, dest: str, overwrite: bool = False) -> None:
    """Copy file but blow if destination name already exists"""
    _safe_op_file(src, dest, "copyfile", overwrite=overwrite)


def safe_movefile(src: str, dest: str, overwrite: bool = False) -> None:
    """Move file but blow if destination name already exists"""
    _safe_op_file(src, dest, "move", overwrite=overwrite)


def _safe_op_file(src: str, dest: str, operation: str, overwrite: bool = False) -> None:
    """Copy or move file but blow if destination name already exists

    Parameters
    ----------
    operation: str, {copyfile, move}
    """
    if op.isdir(dest):
        dest = op.join(dest, op.basename(src))
    if op.realpath(src) == op.realpath(dest):
        lgr.debug("Source %s = destination %s", src, dest)
        return
    if op.lexists(dest):
        if not overwrite:
            raise RuntimeError(
                "was asked to %s %s but destination already exists: %s"
                % (operation, src, dest)
            )
        os.unlink(dest)
    getattr(shutil, operation)(src, dest)


# Globals to check filewriting permissions
ALL_CAN_WRITE = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
ALL_CAN_READ = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
assert ALL_CAN_READ >> 1 == ALL_CAN_WRITE  # Assumption in the code


def set_readonly(path: str, read_only: bool = True) -> int:
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


def is_readonly(path: str) -> bool:
    """Return True if it is a fully read-only file (dereferences the symlink)"""
    # get current permissions
    perms = stat.S_IMODE(os.lstat(os.path.realpath(path)).st_mode)
    # should be true if anyone is allowed to write
    return not bool(perms & ALL_CAN_WRITE)


def clear_temp_dicoms(item_dicoms: list[str]) -> None:
    """Ensures DICOM temporary directories are safely cleared"""
    try:
        tmp = Path(op.commonprefix(item_dicoms)).parents[1]
    except IndexError:
        return
    if (
        str(tmp.parent) == tempfile.gettempdir()
        and str(tmp.stem).startswith("heudiconvDCM")
        and op.exists(tmp)
    ):
        # clean up directory holding dicoms
        shutil.rmtree(tmp)


def file_md5sum(filename: str) -> str:
    with open(filename, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# Borrowed from DataLad (MIT license), with "archives" functionality commented
# out
class File:
    """Helper for a file entry in the create_tree/@with_tree

    It allows to define additional settings for entries
    """

    def __init__(self, name: str, executable: bool = False) -> None:
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

    def __str__(self) -> str:
        return self.name


TreeSpec = Union[
    Sequence[Tuple[Union[str, File], "Load"]],
    Mapping[str, "Load"],
]

Load = Union[str, "TreeSpec", dict]


def create_tree(path: str, tree: TreeSpec, archives_leading_dir: bool = True) -> None:
    """Given a list of tuples (name, load) or a dict create such a tree

    if load is a tuple or a dict itself -- that would create either a subtree
    or an archive with that content and place it into the tree if name ends
    with .tar.gz
    """
    lgr.log(5, "Creating a tree under %s", path)
    if not op.exists(path):
        os.makedirs(path)

    if isinstance(tree, MappingABC):
        tree = list(tree.items())

    for file_, load in tree:
        if isinstance(file_, File):
            executable = file_.executable
            name = file_.name
        else:
            executable = False
            name = file_
        full_name = op.join(path, name)
        if name.endswith(".json") and isinstance(load, dict):
            # (For a json file, we expect the content to be a dictionary, so
            #  don't continue creating a tree, but just write dict to file)
            save_json(full_name, load)
        elif isinstance(load, (tuple, list, dict)):
            # if name.endswith('.tar.gz') or name.endswith('.tar') or name.endswith('.zip'):
            #     create_tree_archive(path, name, load, archives_leading_dir=archives_leading_dir)
            # else:
            create_tree(full_name, load, archives_leading_dir=archives_leading_dir)
        else:
            assert isinstance(load, str)
            with open(full_name, "w") as f:
                f.write(load)
        if executable:
            os.chmod(full_name, os.stat(full_name).st_mode | stat.S_IEXEC)


@overload
def get_typed_attr(obj: Any, attr: str, _type: type[T], default: V) -> T | V:
    ...


@overload
def get_typed_attr(
    obj: Any, attr: str, _type: type[T], default: None = None
) -> T | None:
    ...


def get_typed_attr(
    obj: Any, attr: str, _type: type[T], default: Optional[V] = None
) -> T | V | None:
    """
    Typecasts an object's named attribute. If the attribute cannot be
    converted, the default value is returned instead.

    Parameters
    ----------
    obj: Object
    attr: Attribute
    _type: Type
    default: value, optional
    """
    try:
        val = _type(getattr(obj, attr, default))  # type: ignore[call-arg]
    except (TypeError, ValueError):
        return default
    return val


def get_datetime(date: str, time: str, *, microseconds: bool = True) -> str:
    """
    Combine date and time from dicom to isoformat.

    Parameters
    ----------
    date : str
        Date in YYYYMMDD format.
    time : str
        Time in either HHMMSS.ffffff format or HHMMSS format.
    microseconds: bool, optional
        Either to include microseconds in the output

    Returns
    -------
    datetime_str : str
        Combined date and time in ISO format, with microseconds as
        if fraction was provided in 'time', and 'microseconds' was
        True.
    """
    if "." not in time:
        # add dummy microseconds if not available for strptime to parse
        time += ".000000"
    td = time + ":" + date
    datetime_str = datetime.datetime.strptime(td, "%H%M%S.%f:%Y%m%d").isoformat()
    if not microseconds:
        datetime_str = datetime_str.split(".", 1)[0]
    return datetime_str


def strptime_micr(date_string: str, fmt: str) -> datetime.datetime:
    r"""
    Decorate strptime while supporting optional [.%f] in the format at the end

    Parameters
    ----------
    date_string: str
      Date string to parse
    fmt: str
      Format string. If it ends with [.%f], we keep it if date_string ends with
      '.\d+' regex and not if it does not.
    """

    warnings.warn(
        "strptime_micr() is deprecated, please use strptime() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    optional_micr = "[.%f]"
    if fmt.endswith(optional_micr):
        fmt = fmt[: -len(optional_micr)]
        if re.search(r"\.\d+$", date_string):
            fmt += ".%f"
    return datetime.datetime.strptime(date_string, fmt)


def datetime_utc_offset(
    datetime_obj: datetime.datetime, utc_offset: str
) -> datetime.datetime:
    """set the datetime's tzinfo by parsing an utc offset string"""
    # https://dicom.innolitics.com/ciods/electromyogram/sop-common/00080201
    extract_offset = re.match(r"([+\-]?)(\d{2})(\d{2})", utc_offset)
    if extract_offset is None:
        raise ValueError(f"utc offset {utc_offset} is not valid")
    sign, hours, minutes = extract_offset.groups()
    sign = -1 if sign == "-" else 1
    hours, minutes = int(hours), int(minutes)
    tzinfo = datetime.timezone(sign * datetime.timedelta(hours=hours, minutes=minutes))
    return datetime_obj.replace(tzinfo=tzinfo)


def strptime(datetime_string: str, fmts: list[str]) -> datetime.datetime:
    """
    Try datetime.strptime on a list of formats returning the first successful attempt.

    Parameters
    ----------
    datetime_string: str
      Datetime string to parse
    fmts: list[str]
      List of format strings
    """
    datetime_str = datetime_string
    for fmt in fmts:
        try:
            return datetime.datetime.strptime(datetime_str, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unable to parse datetime string: {datetime_str}")


def strptime_bids(datetime_string: str) -> datetime.datetime:
    """
    Create a datetime object from a bids datetime string.

    Parameters
    ----------
    date_string: str
      Datetime string to parse
    """
    # https://bids-specification.readthedocs.io/en/stable/common-principles.html#units
    fmts = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]
    datetime_obj = strptime(datetime_string, fmts)
    return datetime_obj


def strptime_dcm_da_tm(
    dcm_data: dcm.Dataset, da_tag: TagType, tm_tag: TagType
) -> datetime.datetime:
    """
    Create a datetime object from a dicom DA tag and TM tag.

    Parameters
    ----------
    dcm_data : dcm.Dataset
        DICOM with header, e.g., as read by pydicom.dcmread.
    da_tag: str
      Dicom tag with DA value representation
    tm_tag: str
      Dicom tag with TM value representation
    """
    # https://dicom.nema.org/medical/dicom/current/output/chtml/part05/sect_6.2.html
    date_str = dcm_data[da_tag].value
    fmts = [
        "%Y%m%d",
    ]
    date = strptime(date_str, fmts)

    time_str = dcm_data[tm_tag].value
    fmts = ["%H", "%H%M", "%H%M%S", "%H%M%S.%f"]
    time = strptime(time_str, fmts)

    datetime_obj = datetime.datetime.combine(date.date(), time.time())

    if utc_offset_dcm := dcm_data.get((0x0008, 0x0201)):
        utc_offset = utc_offset_dcm.value
        datetime_obj = (
            datetime_utc_offset(datetime_obj, utc_offset)
            if utc_offset
            else datetime_obj
        )
    return datetime_obj


def strptime_dcm_dt(dcm_data: dcm.Dataset, dt_tag: TagType) -> datetime.datetime:
    """
    Create a datetime object from a dicom DT tag.

    Parameters
    ----------
    dcm_data : dcm.FileDataset
        DICOM with header, e.g., as read by pydicom.dcmread.
        Objects with __getitem__ and have those keys with values properly formatted may also work
    da_tag: str
      Dicom tag with DT value representation
    """
    # https://dicom.nema.org/medical/dicom/current/output/chtml/part05/sect_6.2.html
    datetime_str = dcm_data[dt_tag].value
    fmts = [
        "%Y%z",
        "%Y%m%z",
        "%Y%m%d%z",
        "%Y%m%d%H%z",
        "%Y%m%d%H%M%z",
        "%Y%m%d%H%M%S%z",
        "%Y%m%d%H%M%S.%f%z",
        "%Y",
        "%Y%m",
        "%Y%m%d",
        "%Y%m%d%H",
        "%Y%m%d%H%M",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M%S.%f",
    ]
    datetime_obj = strptime(datetime_str, fmts)

    if utc_offset_dcm := dcm_data.get((0x0008, 0x0201)):
        if utc_offset := utc_offset_dcm.value:
            datetime_obj2 = datetime_utc_offset(datetime_obj, utc_offset)
            if datetime_obj.tzinfo and datetime_obj2 != datetime_obj:
                lgr.warning(
                    "Unexpectedly previously parsed datetime %s contains zoneinfo which is different from the one obtained from DICOMs UTFOffset field: %s",
                    datetime_obj,
                    datetime_obj2,
                )
            else:
                datetime_obj = datetime_obj2
    return datetime_obj


def remove_suffix(s: str, suf: str) -> str:
    """
    Remove suffix from the end of the string

    Parameters
    ----------
    s : str
    suf : str

    Returns
    -------
    s : str
        string with "suf" removed from the end (if present)
    """
    if suf and s.endswith(suf):
        return s[: -len(suf)]
    return s


def remove_prefix(s: str, pre: str) -> str:
    """
    Remove prefix from the beginning of the string

    Parameters
    ----------
    s : str
    pre : str

    Returns
    -------
    s : str
        string with "pre" removed from the beginning (if present)
    """
    if pre and s.startswith(pre):
        return s[len(pre) :]
    return s
