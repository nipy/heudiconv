import inspect
import os

import os.path as op
import logging
from glob import glob
from os import path as op

from ..utils import create_file_if_missing

lgr = logging.getLogger(__name__)

MIN_VERSION = '0.7'


def prepare_datalad(studydir, outdir, sid, session, seqinfo, dicoms, bids):
    """ Prepare data for datalad """
    from datalad.api import Dataset
    datalad_msg_suf = ' %s' % sid
    if session:
        datalad_msg_suf += ", session %s" % session
    if seqinfo:
        datalad_msg_suf += ", %d sequences" % len(seqinfo)
    datalad_msg_suf += ", %d dicoms" % (len(sum(seqinfo.values(), []))
                                        if seqinfo else len(dicoms))
    ds = Dataset(studydir)
    if not op.exists(outdir) or not ds.is_installed():
        add_to_datalad(outdir, studydir,
                       msg="Preparing for %s" % datalad_msg_suf,
                       bids=bids)
    return datalad_msg_suf


def add_to_datalad(topdir, studydir, msg, bids):
    """Do all necessary preparations (if were not done before) and save
    """
    from datalad.api import create
    from datalad.api import Dataset
    from datalad.support.annexrepo import AnnexRepo
    from datalad.support.external_versions import external_versions
    assert external_versions['datalad'] >= MIN_VERSION, (
      "Need datalad >= {}".format(MIN_VERSION))  # add to reqs

    studyrelpath = op.relpath(studydir, topdir)
    assert not studyrelpath.startswith(op.pardir)  # so we are under
    # now we need to test and initiate a DataLad dataset all along the path
    curdir_ = topdir
    superds = None
    subdirs = [''] + studyrelpath.split(op.sep)
    for isubdir, subdir in enumerate(subdirs):
        curdir_ = op.join(curdir_, subdir)
        ds = Dataset(curdir_)
        if not ds.is_installed():
            lgr.info("Initiating %s", ds)
            # would require annex > 20161018 for correct operation on annex v6
            # need to add .gitattributes first anyways
            ds_ = create(curdir_, dataset=superds,
                         force=True,
                         no_annex=True,
                         # shared_access='all',
                         annex_version=6)
            assert ds == ds_
        assert ds.is_installed()
        superds = ds

    # TODO: we need a helper (in DataLad ideally) to ease adding such
    # specifications
    gitattributes_path = op.join(studydir, '.gitattributes')
    # We will just make sure that all our desired rules are present in it
    desired_attrs = """\
* annex.largefiles=(largerthan=100kb)
*.json annex.largefiles=nothing
*.txt annex.largefiles=nothing
*.tsv annex.largefiles=nothing
*.nii.gz annex.largefiles=anything
*.tgz annex.largefiles=anything
*_scans.tsv annex.largefiles=anything
"""
    if op.exists(gitattributes_path):
        with open(gitattributes_path, 'rb') as f:
            known_attrs = [line.decode('utf-8').rstrip() for line in f.readlines()]
    else:
        known_attrs = []
    for attr in desired_attrs.split('\n'):
        if attr not in known_attrs:
            known_attrs.append(attr)
    with open(gitattributes_path, 'wb') as f:
        f.write('\n'.join(known_attrs).encode('utf-8'))

    # so for mortals it just looks like a regular directory!
    if not ds.config.get('annex.thin'):
        ds.config.add('annex.thin', 'true', where='local')
    # initialize annex there if not yet initialized
    AnnexRepo(ds.path, init=True)
    # ds might have memories of having ds.repo GitRepo
    superds = None
    del ds
    ds = Dataset(studydir)
    # Add doesn't have all the options of save such as msg and supers
    ds.add('.gitattributes', to_git=True, save=False)
    dsh = dsh_path = None
    if op.lexists(op.join(ds.path, '.heudiconv')):
        dsh_path = op.join(ds.path, '.heudiconv')
        dsh = Dataset(dsh_path)
        if not dsh.is_installed():
            # Previously we did not have it as a submodule, and since no
            # automagic migration is implemented, we just need to check first
            # if any path under .heudiconv is already under git control
            if any(x[0].startswith('.heudiconv/') for x in
                   ds.repo.repo.index.entries.keys()):
                lgr.warning("%s has .heudiconv not as a submodule from previous"
                            " versions of heudiconv. No automagic migration is "
                            "yet provided", ds)
            else:
                dsh = ds.create(path='.heudiconv',
                                force=True
                                # shared_access='all'
                                )
        # Since .heudiconv could contain sensitive information
        # we place all files under annex and then add
        if create_file_if_missing(op.join(dsh_path, '.gitattributes'),
                                  """* annex.largefiles=anything"""):
            ds.add('.heudiconv/.gitattributes',
                   to_git=True,
                   message="Added gitattributes to place all .heudiconv content"
                           " under annex")
    ds.add('.', recursive=True, save=False,
           # not in effect! ?
           #annex_add_opts=['--include-dotfiles']
           )

    # TODO: filter for only changed files?
    # Provide metadata for sensitive information
    mark_sensitive(ds, 'sourcedata')
    mark_sensitive(ds, '*_scans.tsv')  # top level
    mark_sensitive(ds, '*/*_scans.tsv')  # within subj
    mark_sensitive(ds, '*/*/*_scans.tsv')  # within sess/subj
    mark_sensitive(ds, '*/anat')  # within subj
    mark_sensitive(ds, '*/*/anat')  # within ses/subj
    if dsh_path:
        mark_sensitive(ds, '.heudiconv')  # entire .heudiconv!
    ds.save(message=msg, recursive=True, super_datasets=True)

    assert not ds.repo.dirty
    # TODO:  they are still appearing as native annex symlinked beasts
    """
    TODOs:
    it needs
    - unlock  (thin will be in effect)
    - save/commit (does modechange 120000 => 100644
    - could potentially somehow automate that all:
      http://git-annex.branchable.com/tips/automatically_adding_metadata/
    - possibly even make separate sub-datasets for originaldata, derivatives ?
    """


def mark_sensitive(ds, path_glob):
    """

    Parameters
    ----------
    ds : Dataset to operate on
    path_glob : str
      glob of the paths within dataset to work on

    Returns
    -------
    None
    """
    paths = glob(op.join(ds.path, path_glob))
    if not paths:
        return
    lgr.debug("Marking %d files with distribution-restrictions field",
              len(paths))
    # set_metadata can be a bloody generator
    res = ds.repo.set_metadata(
        paths,
        init=dict([('distribution-restrictions', 'sensitive')]),
        recursive=True)
    if inspect.isgenerator(res):
        res = list(res)