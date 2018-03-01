import logging
import os
import os.path as op
from glob import glob
import re

from collections import defaultdict, OrderedDict

import tarfile
from tempfile import mkdtemp

from .dicoms import group_dicoms_into_seqinfos
from .utils import (
    docstring_parameter,
    StudySessionInfo,
    load_json,
    save_json,
    create_file_if_missing,
    json_dumps_pretty,
)

lgr = logging.getLogger(__name__)

_VCS_REGEX = '%s\.(?:git|gitattributes|svn|bzr|hg)(?:%s|$)' % (op.sep, op.sep)

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
    topdir: basestring, optional
      Directory where to search
    dirs: bool, optional
      Either to match directories as well as files
    """

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


def get_extracted_dicoms(fl):
    """Given a list of files, possibly extract some from tarballs
    For 'classical' heudiconv, if multiple tarballs are provided, they correspond
    to different sessions, so here we would group into sessions and return
    pairs  `sessionid`, `files`  with `sessionid` being None if no "sessions"
    detected for that file or there was just a single tarball in the list
    """
    # TODO: bring check back?
    # if any(not tarfile.is_tarfile(i) for i in fl):
    #     raise ValueError("some but not all input files are tar files")

    # tarfiles already know what they contain, and often the filenames
    # are unique, or at least in a unqiue subdir per session
    # strategy: extract everything in a temp dir and assemble a list
    # of all files in all tarballs

    # cannot use TempDirs since will trigger cleanup with __del__
    tmpdir = mkdtemp(prefix='heudiconvDCM')

    sessions = defaultdict(list)
    session = 0
    if not isinstance(fl, (list, tuple)):
        fl = list(fl)

    # needs sorting to keep the generated "session" label deterministic
    for i, t in enumerate(sorted(fl)):
        # "classical" heudiconv has that heuristic to handle multiple
        # tarballs as providing different sessions per each tarball
        if not tarfile.is_tarfile(t):
            sessions[None].append(t)
            continue

        tf = tarfile.open(t)
        # check content and sanitize permission bits
        tmembers = tf.getmembers()
        for tm in tmembers:
            tm.mode = 0o700
        # get all files, assemble full path in tmp dir
        tf_content = [m.name for m in tmembers if m.isfile()]
        # store full paths to each file, so we don't need to drag along
        # tmpdir as some basedir
        sessions[session] = [op.join(tmpdir, f) for f in tf_content]
        session += 1
        # extract into tmp dir
        tf.extractall(path=tmpdir, members=tmembers)

    if session == 1:
        # we had only 1 session, so no really multiple sessions according
        # to classical 'heudiconv' assumptions, thus just move them all into
        # None
        sessions[None] += sessions.pop(0)

    return sessions.items()


def get_study_sessions(dicom_dir_template, files_opt, heuristic, outdir,
                       session, sids, grouping='studyUID'):
    """Given options from cmdline sort files or dicom seqinfos into
    study_sessions which put together files for a single session of a subject
    in a study
    Two major possible workflows:
    - if dicom_dir_template provided -- doesn't pre-load DICOMs and just
      loads files pointed by each subject and possibly sessions as corresponding
      to different tarballs
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
                    '.*', topdir=f, exclude_vcs=True, exclude="/\.datalad/"))
            else:
                files.append(f)

        # in this scenario we don't care about sessions obtained this way
        files_ = []
        for _, files_ex in get_extracted_dicoms(files):
            files_ += files_ex

        # sort all DICOMS using heuristic
        # TODO:  this one is not grouping by StudyUID but may be we should!
        seqinfo_dict = group_dicoms_into_seqinfos(files_,
            file_filter=getattr(heuristic, 'filter_files', None),
            dcmfilter=getattr(heuristic, 'filter_dicom', None),
            grouping=grouping)

        if not getattr(heuristic, 'infotoids', None):
            raise NotImplementedError(
                "For now, if no subj template is provided, requiring "
                "heuristic to have infotoids")

        if sids:
            if not (len(sids) == 1 and len(seqinfo_dict) == 1):
                raise RuntimeError(
                    "We were provided some subjects (%s) but "
                    "we can deal only "
                    "with overriding only 1 subject id. Got %d subjects and "
                    "found %d sequences" % (sids, len(sids), len(seqinfo_dict))
                )
            sid = sids[0]
        else:
            sid = None

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
            lgr.info("Study session for %s" % str(ids))
            study_session_info = StudySessionInfo(
                ids.get('locator'),
                ids.get('session', session) or session,
                sid or ids.get('subject', None)
            )
            if study_session_info in study_sessions:
                #raise ValueError(
                lgr.warning(
                    "We already have a study session with the same value %s"
                    % repr(study_session_info))
                continue # skip for now
            study_sessions[study_session_info] = seqinfo
    return study_sessions
