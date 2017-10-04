# dicom operations
import os
import os.path as op
import logging
from collections import OrderedDict

import dicom as dcm
import dcmstack as ds

from .utils import SeqInfo

lgr = logging.getLogger(__name__)

def group_dicoms_into_seqinfos(files, file_filter, dcmfilter, grouping):
    """Process list of dicoms and return seqinfo and file group
    `seqinfo` contains per-sequence extract of fields from DICOMs which
    will be later provided into heuristics to decide on filenames
    Parameters
    ----------
    files : list of str
      List of files to consider
    file_filter : callable, optional
      Applied to each item of filenames. Should return True if file needs to be
      kept, False otherwise.
    dcmfilter : callable, optional
      If called on dcm_data and returns True, it is used to set series_id
    grouping : {'studyUID', 'accession_number', None}, optional
        what to group by: studyUID or accession_number
    Returns
    -------
    seqinfo : list of list
      `seqinfo` is a list of info entries per each sequence (some entry
      there defines a key for `filegrp`)
    filegrp : dict
      `filegrp` is a dictionary with files groupped per each sequence
    """
    allowed_groupings = ['studyUID', 'accession_number', None]
    if grouping not in allowed_groupings:
        raise ValueError('I do not know how to group by {0}'.format(grouping))
    per_studyUID = grouping == 'studyUID'
    per_accession_number = grouping == 'accession_number'
    lgr.info("Analyzing %d dicoms", len(files))
    import dcmstack as ds
    import dicom as dcm

    groups = [[], []]
    mwgroup = []

    studyUID = None
    # for sanity check that all DICOMs came from the same
    # "study".  If not -- what is the use-case? (interrupted acquisition?)
    # and how would then we deal with series numbers
    # which would differ already
    if file_filter:
        nfl_before = len(files)
        files = list(filter(file_filter, files))
        nfl_after = len(files)
        lgr.info('Filtering out {0} dicoms based on their filename'.format(
            nfl_before-nfl_after))
    for fidx, filename in enumerate(files):
        # TODO after getting a regression test check if the same behavior
        #      with stop_before_pixels=True
        mw = ds.wrapper_from_data(dcm.read_file(filename, force=True))

        for sig in ('iop', 'ICE_Dims', 'SequenceName'):
            try:
                del mw.series_signature[sig]
            except:
                pass

        try:
            file_studyUID = mw.dcm_data.StudyInstanceUID
        except AttributeError:
            lgr.info("File {} is missing any StudyInstanceUID".format(filename))
            file_studyUID = None

        try:
            series_id = (int(mw.dcm_data.SeriesNumber),
                         mw.dcm_data.ProtocolName)
            file_studyUID = mw.dcm_data.StudyInstanceUID

            if not per_studyUID:
                # verify that we are working with a single study
                if studyUID is None:
                    studyUID = file_studyUID
                elif not per_accession_number:
                    assert studyUID == file_studyUID
        except AttributeError as exc:
            lgr.warning('Ignoring %s since not quite a "normal" DICOM: %s',
                        filename, exc)
            series_id = (-1, 'none')
            file_studyUID = None

        if not series_id[0] < 0:
            if dcmfilter is not None and dcmfilter(mw.dcm_data):
                series_id = (-1, mw.dcm_data.ProtocolName)

        # MG: This will always be false??
        # if not groups:
        #     raise RuntimeError("Yarik really thinks this is never ran!")
        #     # if I was wrong -- then per_studyUID might need to go above
        #     # yoh: I don't think this would ever be executed!
        #     mwgroup.append(mw)
        #     groups[0].append(series_id)
        #     groups[1].append(len(mwgroup) - 1)
        #     continue

        # filter out unwanted non-image-data DICOMs by assigning
        # a series number < 0 (see test below)
        if not series_id[0] < 0 and mw.dcm_data[0x0008, 0x0016].repval in (
                'Raw Data Storage',
                'GrayscaleSoftcopyPresentationStateStorage'):
            series_id = (-1, mw.dcm_data.ProtocolName)

        if per_studyUID:
            series_id = series_id + (file_studyUID,)


        ingrp = False
        for idx in range(len(mwgroup)):
            # same = mw.is_same_series(mwgroup[idx])
            if mw.is_same_series(mwgroup[idx]):
                # the same series should have the same study uuid
                assert (mwgroup[idx].dcm_data.get('StudyInstanceUID', None)
                        == file_studyUID)
                ingrp = True
                if series_id[0] >= 0:
                    series_id = (mwgroup[idx].dcm_data.SeriesNumber,
                                 mwgroup[idx].dcm_data.ProtocolName)
                    if per_studyUID:
                        series_id = series_id + (file_studyUID,)
                groups[0].append(series_id)
                groups[1].append(idx)

        if not ingrp:
            mwgroup.append(mw)
            groups[0].append(series_id)
            groups[1].append(len(mwgroup) - 1)

    group_map = dict(zip(groups[0], groups[1]))

    total = 0
    seqinfo = OrderedDict()

    # for the next line to make any sense the series_id needs to
    # be sortable in a way that preserves the series order
    for series_id, mwidx in sorted(group_map.items()):
        if series_id[0] < 0:
            # skip our fake series with unwanted files
            continue
        mw = mwgroup[mwidx]
        if mw.image_shape is None:
            # this whole thing has now image data (maybe just PSg DICOMs)
            # nothing to see here, just move on
            continue
        dcminfo = mw.dcm_data
        series_files = [files[i] for i, s in enumerate(groups[0])
                        if s == series_id]
        # turn the series_id into a human-readable string -- string is needed
        # for JSON storage later on
        if per_studyUID:
            studyUID = series_id[2]
            series_id = series_id[:2]
        accession_number = dcminfo.get('AccessionNumber')

        series_id = '-'.join(map(str, series_id))

        size = list(mw.image_shape) + [len(series_files)]
        total += size[-1]
        if len(size) < 4:
            size.append(1)
        try:
            TR = float(dcminfo.RepetitionTime) / 1000.
        except (AttributeError, ValueError):
            TR = -1
        try:
            TE = float(dcminfo.EchoTime)
        except (AttributeError, ValueError):
            TE = -1
        try:
            refphys = str(dcminfo.ReferringPhysicianName)
        except AttributeError:
            refphys = '-'

        image_type = tuple(dcminfo.ImageType)
        motion_corrected = ('MoCo' in dcminfo.SeriesDescription
                           or 'MOCO' in image_type)

        if dcminfo.get([0x18,0x24], None):
            # GE and Philips scanners
            sequence_name = dcminfo[0x18,0x24].value
        elif dcminfo.get([0x19, 0x109c], None):
            # Siemens scanners
            sequence_name = dcminfo[0x19, 0x109c].value
        else:
            sequence_name = 'Not found'

        info = SeqInfo(
            total,
            op.split(series_files[0])[1],
            series_id,
            op.basename(op.dirname(series_files[0])),
            '-', '-',
            size[0], size[1], size[2], size[3],
            TR, TE,
            dcminfo.ProtocolName,
            motion_corrected,
            'derived' in [x.lower() for x in dcminfo.get('ImageType', [])],
            dcminfo.get('PatientID'),
            dcminfo.get('StudyDescription'),
            refphys,
            dcminfo.get('SeriesDescription'),
            sequence_name,
            image_type,
            accession_number,
            # For demographics to populate BIDS participants.tsv
            dcminfo.get('PatientAge'),
            dcminfo.get('PatientSex'),
            dcminfo.get('AcquisitionDate'),
        )
        # candidates
        # dcminfo.AccessionNumber
        #   len(dcminfo.ReferencedImageSequence)
        #   len(dcminfo.SourceImageSequence)
        # FOR demographics
        if per_studyUID:
            key = studyUID.split('.')[-1]
        elif per_accession_number:
            key = accession_number
        else:
            key = ''
        lgr.debug("%30s %30s %27s %27s %5s nref=%-2d nsrc=%-2d %s" % (
            key,
            info.series_id,
            dcminfo.SeriesDescription,
            dcminfo.ProtocolName,
            info.is_derived,
            len(dcminfo.get('ReferencedImageSequence', '')),
            len(dcminfo.get('SourceImageSequence', '')),
            info.image_type
        ))
        if per_studyUID:
            if studyUID not in seqinfo:
                seqinfo[studyUID] = OrderedDict()
            seqinfo[studyUID][info] = series_files
        elif per_accession_number:
            if accession_number not in seqinfo:
                seqinfo[accession_number] = OrderedDict()
            seqinfo[accession_number][info] = series_files
        else:
            seqinfo[info] = series_files

    if per_studyUID:
        lgr.info("Generated sequence info for %d studies with %d entries total",
                 len(seqinfo), sum(map(len, seqinfo.values())))
    elif per_accession_number:
        lgr.info("Generated sequence info for %d accession numbers with %d "
                 "entries total", len(seqinfo), sum(map(len, seqinfo.values())))
    else:
        lgr.info("Generated sequence info with %d entries", len(seqinfo))
    return seqinfo


def get_dicom_series_time(dicom_list):
    """Get time in seconds since epoch from dicom series date and time
    Primarily to be used for reproducible time stamping
    """
    import time
    import calendar

    dcm = dcm.read_file(dicom_list[0], stop_before_pixels=True, force=True)
    dcm_date = dcm.SeriesDate  # YYYYMMDD
    dcm_time = dcm.SeriesTime  # HHMMSS.MICROSEC
    dicom_time_str = dcm_date + dcm_time.split('.', 1)[0]  # YYYYMMDDHHMMSS
    # convert to epoch
    return calendar.timegm(time.strptime(dicom_time_str, '%Y%m%d%H%M%S'))


def compress_dicoms(dicom_list, out_prefix, tempdirs):
    """Archives DICOMs into a tarball

    Also tries to do it reproducibly, so takes the date for files
    and target tarball based on the series time (within the first file)

    Parameters
    ----------
    dicom_list : list of str
      list of dicom files
    out_prefix : str
      output path prefix, including the portion of the output file name
      before .dicom.tgz suffix
    tempdirs : object
      TempDirs object to handle multiple tmpdirs

    Returns
    -------
    filename : str
      Result tarball
    """
    # if tempdirs:
    tmpdir = tempdirs(prefix='dicomtar')
    # else:
    #     tmpdir = mkdtemp(prefix='dicomtar')
    outtar = out_prefix + '.dicom.tgz'
    if op.exists(outtar): # and not global_options['overwrite']:
        raise RuntimeError("File %s already exists, will not override, ensure "
                           "unique scan names" % outtar)
    # tarfile encodes current time.time inside making those non-reproducible
    # so we should choose which date to use.
    # Solution from DataLad although ugly enough:

    dicom_list = sorted(dicom_list)
    dcm_time = get_dicom_series_time(dicom_list)

    def _assign_dicom_time(ti):
        # Reset the date to match the one of the last commit, not from the
        # filesystem since git doesn't track those at all
        ti.mtime = dcm_time
        return ti

    # poor man mocking since can't rely on having mock
    try:
        import time
        _old_time = time.time
        time.time = lambda: dcm_time
        if op.lexists(outtar):
            os.unlink(outtar)
        with tarfile.open(outtar, 'w:gz', dereference=True) as tar:
            for filename in dicom_list:
                outfile = op.join(tmpdir, op.basename(filename))
                if not op.islink(outfile):
                    os.symlink(op.realpath(filename), outfile)
                # place into archive stripping any lead directories and
                # adding the one corresponding to prefix
                tar.add(outfile,
                        arcname=op.join(op.basename(out_prefix),
                                        op.basename(outfile)),
                        recursive=False,
                        filter=_assign_dicom_time)
    finally:
        time.time = _old_time
        tempdirs.rmtree(tmpdir)

    return outtar


def embed_metadata_from_dicoms(bids, item_dicoms, outname, outname_bids,
                               prov_file, scaninfo, tempdirs, with_prov,
                               min_meta):
    """
    Enhance sidecar information file with more information from DICOMs

    Parameters
    ----------
    bids
    item_dicoms
    outname
    outname_bids
    prov_file
    scaninfo
    tempdirs
    with_prov
    min_meta

    Returns
    -------

    """
    from nipype import Node, Function
    tmpdir = tempdirs(prefix='embedmeta')

    embedfunc = Node(Function(input_names=['dcmfiles', 'niftifile', 'infofile',
                                           'bids_info', 'force', 'min_meta'],
                              output_names=['outfile', 'meta'],
                              function=embed_nifti),
                     name='embedder')
    embedfunc.inputs.dcmfiles = item_dicoms
    embedfunc.inputs.niftifile = op.abspath(outname)
    embedfunc.inputs.infofile = op.abspath(scaninfo)
    embedfunc.inputs.min_meta = min_meta
    if bids:
        embedfunc.inputs.bids_info = load_json(op.abspath(outname_bids))
    else:
        embedfunc.inputs.bids_info = None
    embedfunc.inputs.force = True
    embedfunc.base_dir = tmpdir
    cwd = os.getcwd()
    try:
        # MG - still a bug?
        """
        Ran into
INFO: Executing node embedder in dir: /tmp/heudiconvdcm2W3UQ7/embedder
ERROR: Embedding failed: [Errno 13] Permission denied: '/inbox/BIDS/tmp/test2-jessie/Wheatley/Beau/1007_personality/sub-sid000138/fmap/sub-sid000138_3mm_run-01_phasediff.json'
while
HEUDICONV_LOGLEVEL=WARNING time bin/heudiconv -f heuristics/dbic_bids.py -c dcm2niix -o /inbox/BIDS/tmp/test2-jessie --bids --datalad /inbox/DICOM/2017/01/28/A000203

so it seems that there is a filename collision so it tries to save into the same file name
and there was a screw up for that A

/mnt/btrfs/dbic/inbox/DICOM/2017/01/28/A000203
        StudySessionInfo(locator='Wheatley/Beau/1007_personality', session=None, subject='sid000138') 16 sequences
        StudySessionInfo(locator='Wheatley/Beau/1007_personality', session=None, subject='a000203') 2 sequences


in that one though
        """
        # if global_options['overwrite'] and op.lexists(scaninfo):
        if op.lexists(scaninfo):
            # TODO: handle annexed file case
            if not op.islink(scaninfo):
                os.chmod(scaninfo, 0o0660)
        res = embedfunc.run()
        os.chmod(scaninfo, 0o0444)
        if with_prov:
            g = res.provenance.rdf()
            g.parse(prov_file,
                    format='turtle')
            g.serialize(prov_file, format='turtle')
            os.chmod(prov_file, 0o0440)
    except Exception as exc:
        lgr.error("Embedding failed: %s", str(exc))
        os.chdir(cwd)
