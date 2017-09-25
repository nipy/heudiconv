import os
import os.path as op
import logging

from ..utils import (create_file_if_missing, mark_sensitive)

lgr = lgr.getLogger(__name__)

def prepare_datalad(studydir, outdir, sid, session, seqinfo, dicoms, bids):
    """ Prepare data for datalad """
    datalad_msg_suf = ' %s' % sid
    if session:
        datalad_msg_suf += ", session %s" % session
    if seqinfo:
        datalad_msg_suf += ", %d sequences" % len(seqinfo)
    datalad_msg_suf += ", %d dicoms" % (len(sum(seqinfo.values(), []))
                                        if seqinfo else len(dicoms))
    from datalad.api import Dataset
    ds = Dataset(studydir)
    if not op.exists(outdir) or not ds.is_installed():
        add_to_datalad(outdir, studydir,
                       msg="Preparing for %s" % datalad_msg_suf,
                       bids=bids)


def add_to_datalad(topdir, studydir, msg, bids):
    """Do all necessary preparations (if were not done before) and save
    """
    from datalad.api import create
    from datalad.api import Dataset
    from datalad.support.annexrepo import AnnexRepo
    from datalad.support.external_versions import external_versions
    assert external_versions['datalad'] >= '0.5.1', "Need datalad >= 0.5.1"

    studyrelpath = os.path.relpath(studydir, topdir)
    assert not studyrelpath.startswith(os.path.pardir)  # so we are under
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
                         shared_access='all',
                         annex_version=6)
            assert ds == ds_
        assert ds.is_installed()
        superds = ds

    create_file_if_missing(
        op.join(studydir, '.gitattributes'),
        """\
* annex.largefiles=(largerthan=100kb)
*.json annex.largefiles=nothing
*.txt annex.largefiles=nothing
*.tsv annex.largefiles=nothing
*.nii.gz annex.largefiles=anything
*.tgz annex.largefiles=anything
*_scans.tsv annex.largefiles=anything
""")
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
    dsh = None
    if op.lexists(op.join(ds.path, '.heudiconv')):
        dsh = Dataset(op.join(ds.path, '.heudiconv'))
        if not dsh.is_installed():
            # we need to create it first
            dsh = ds.create(path='.heudiconv',
                            force=True,
                            shared_access='all')
        # Since .heudiconv could contain sensitive information
        # we place all files under annex and then add
        if create_file_if_missing(op.join(dsh.path, '.gitattributes'),
                                  """* annex.largefiles=anything"""):
            dsh.add('.gitattributes',
              message="Added gitattributes to place all content under annex")
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
    if dsh:
        mark_sensitive(dsh)  # entire .heudiconv!
        dsh.save(message=msg)
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
