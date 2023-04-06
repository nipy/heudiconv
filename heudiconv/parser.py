import atexit
import logging
import os
import os.path as op
from glob import glob
import re

from collections import defaultdict

import shutil
from typing import DefaultDict, ItemsView, Iterable, List, Optional

from .dicoms import group_dicoms_into_seqinfos
from .utils import (
    docstring_parameter,
    StudySessionInfo,
    TempDirs,
)

lgr = logging.getLogger(__name__)
tempdirs = TempDirs()
# Ensure they are cleaned up upon exit
atexit.register(tempdirs.cleanup)

_VCS_REGEX = r'%s\.(?:git|gitattributes|svn|bzr|hg)(?:%s|$)' % (op.sep, op.sep)

_UNPACK_FORMATS = tuple(sum((x[1] for x in shutil.get_unpack_formats()), []))

@docstring_parameter(_VCS_REGEX)
def find_files(regex, topdir=op.curdir, exclude=None,
               exclude_vcs=True, dirs=False):
    """Generator to find files matching regex

    Parameters
    ----------
    regex: basestring
    exclude: basestring, optional
      Matches to exclude
    exclude_vcs:
      If True, excludes commonly known VCS subdirectories.  If string, used
      as regex to exclude those files (regex: `{}`)
    topdir: basestring or list, optional
      Directory where to search
    dirs: bool, optional
      Either to match directories as well as files
    """
    if isinstance(topdir, (list, tuple)):
        for topdir_ in topdir:
            yield from find_files(
                regex, topdir=topdir_, exclude=exclude, exclude_vcs=exclude_vcs, dirs=dirs)
        return
    for dirpath, dirnames, filenames in os.walk(topdir):
        names = (dirnames + filenames) if dirs else filenames
        paths = (op.join(dirpath, name) for name in names)
        for path in filter(re.compile(regex).search, paths):
            path = path.rstrip(op.sep)
            if exclude and re.search(exclude, path):
                continue
            if exclude_vcs and re.search(_VCS_REGEX, path):
                continue
            yield path


def get_extracted_dicoms(
        fl: Iterable[str]
    ) -> ItemsView[Optional[int], List[str]]:
    """Given a collection of files and/or directories, list out and possibly 
    extract the contents from archives.

    Parameters
    ----------
    fl
        Files (possibly archived) to process.

    Returns
    -------
    ItemsView[int | None, list[str]]
        The absolute paths of (possibly newly extracted) files. 

    Notes
    -----
    For 'classical' heudiconv, if multiple archives are provided, they 
    correspond to different sessions, so here we would group into sessions 
    and return pairs `sessionid`, `files`  with `sessionid` being None if no 
    "sessions" detected for that file or there was just a single tarball in the
    list.

    When contents of fl appear to be an unpackable archive, the contents are
    extracted into utils.TempDirs(f'heudiconvDCM') and the mode of all 
    extracted files is set to 700.

    When contents of fl are a list of unarchived files, they are treated as
    a single session.

    When contents of fl are a list of unarchived and archived files, the 
    unarchived files are grouped into a single session (key: None). If there is
    only one archived file, the contents of that file are grouped with
    the unarchived file. If there are multiple archived files, they are grouped
    into separate sessions.
    """
    sessions: DefaultDict[Optional[int], List[str]] = defaultdict(list)
    
    # keep track of session manually to ensure that the variable is bound
    # when it is used after the loop (e.g., consider situation with
    # fl being empty)
    session = 0
    # needs sorting to keep the generated "session" label deterministic
    for _, t in enumerate(sorted(fl)):

        if not t.endswith(_UNPACK_FORMATS):
            sessions[None].append(t)
            continue

        # Each file extracted must be associated with the proper session,
        # but the high-level shutil does not have a way to list the files
        # contained within each archive. So, files are temporarily
        # extracted into unique tempdirs
        # cannot use TempDirs since will trigger cleanup with __del__
        tmpdir = tempdirs(prefix="heudiconvDCM")
        
        # check content and sanitize permission bits before extraction
        os.chmod(tmpdir, mode=0o700)
        shutil.unpack_archive(t, extract_dir=tmpdir)

        archive_content = list(find_files(regex=".*", topdir=tmpdir))

        # may be too cautious (tmpdir is already 700). 
        for f in archive_content:
            os.chmod(f, mode=0o700)
        # store full paths to each file, so we don't need to drag along
        # tmpdir as some basedir
        sessions[session] = archive_content
        session += 1

    if session == 1:
        # we had only 1 session (and at least 1), so not really multiple
        # sessions according to classical 'heudiconv' assumptions, thus 
        # just move them all into None
        sessions[None] += sessions.pop(0)

    return sessions.items()


def get_study_sessions(dicom_dir_template, files_opt, heuristic, outdir,
                       session, sids, grouping='studyUID'):
    """Sort files or dicom seqinfos into study_sessions.

    study_sessions put together files for a single session of a subject
    in a study.  Two major possible workflows:

    - if dicom_dir_template provided -- doesn't pre-load DICOMs and just
      loads files pointed by each subject and possibly sessions as corresponding
      to different tarballs.

    - if files_opt is provided, sorts all DICOMs it can find under those paths
    """
    study_sessions = {}
    if dicom_dir_template:
        dicom_dir_template = op.abspath(dicom_dir_template)

        # MG - should be caught by earlier checks
        # assert not files_opt  # see above TODO
        # assert sids
        # expand the input template

        if '{subject}' not in dicom_dir_template:
            raise ValueError(
                "dicom dir template must have {subject} as a placeholder for a "
                "subject id.  Got %r" % dicom_dir_template)
        for sid in sids:
            sdir = dicom_dir_template.format(subject=sid, session=session)
            files = sorted(glob(sdir))
            for session_, files_ in get_extracted_dicoms(files):
                if session_ is not None and session:
                    lgr.warning(
                        "We had session specified (%s) but while analyzing "
                        "files got a new value %r (using it instead)"
                        % (session, session_))
                # in this setup we do not care about tracking "studies" so
                # locator would be the same None
                study_sessions[StudySessionInfo(None,
                        session_ if session_ is not None else session,
                        sid)] = files_
    else:
        # MG - should be caught on initial run
        # YOH - what if it is the initial run?
        # prep files
        # assert files_opt
        files = []
        for f in files_opt:
            if op.isdir(f):
                files += sorted(find_files(
                    '.*', topdir=f, exclude_vcs=True, exclude=r"/\.datalad/"))
            else:
                files.append(f)

        # in this scenario we don't care about sessions obtained this way
        files_ = []
        for _, files_ex in get_extracted_dicoms(files):
            files_ += files_ex

        # sort all DICOMS using heuristic
        seqinfo_dict = group_dicoms_into_seqinfos(
            files_,
            grouping,
            file_filter=getattr(heuristic, 'filter_files', None),
            dcmfilter=getattr(heuristic, 'filter_dicom', None),
            custom_grouping=getattr(heuristic, 'grouping', None)
        )

        if sids:
            if len(sids) != 1:
                raise RuntimeError(
                    "We were provided some subjects (%s) but "
                    "we can deal only "
                    "with overriding only 1 subject id. Got %d subjects and "
                    "found %d sequences" % (sids, len(sids), len(seqinfo_dict))
                )
            sid = sids[0]
        else:
            sid = None

        if not getattr(heuristic, 'infotoids', None):
            # allow bypass with subject override
            if not sid:
                raise NotImplementedError("Cannot guarantee subject id - add "
                                          "`infotoids` to heuristic file or "
                                          "provide `--subjects` option")
            lgr.warn("Heuristic is missing an `infotoids` method, assigning "
                     "empty method and using provided subject id %s. "
                     "Provide `session` and `locator` fields for best results."
                     , sid)
            def infotoids(seqinfos, outdir):
                return {
                    'locator': None,
                    'session': None,
                    'subject': None
                    }
            heuristic.infotoids = infotoids

        for studyUID, seqinfo in seqinfo_dict.items():
            # so we have a single study, we need to figure out its
            # locator, session, subject
            # TODO: Try except to ignore those we can't handle?
            # actually probably there should be a dedicated exception for
            # heuristics to throw if they detect that the study they are given
            # is not the one they would be willing to work on
            ids = heuristic.infotoids(seqinfo.keys(), outdir=outdir)
            # TODO:  probably infotoids is doomed to do more and possibly
            # split into multiple sessions!!!! but then it should be provided
            # full seqinfo with files which it would place into multiple groups
            study_session_info = StudySessionInfo(
                ids.get('locator'),
                ids.get('session', session) or session,
                sid or ids.get('subject', None)
            )
            lgr.info("Study session for %r", study_session_info)

            if study_session_info in study_sessions:
                if grouping != 'all':
                    # MG - should this blow up to mimic -d invocation?
                    lgr.warning(
                        "Existing study session with the same values (%r)."
                        " Skipping DICOMS %s",
                        study_session_info, *seqinfo.values()
                    )
                    continue
            study_sessions[study_session_info] = seqinfo
    return study_sessions
