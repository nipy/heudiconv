# dicom operations

import logging

lgr = logging.getLogger(__name__)

def group_dicoms_into_seqinfos(files, file_filter=None, dcmfilter=None,
                               grouping='studyUID'):
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

        if not groups:
            raise RuntimeError("Yarik really thinks this is never ran!")
            # if I was wrong -- then per_studyUID might need to go above
            # yoh: I don't think this would ever be executed!
            mwgroup.append(mw)
            groups[0].append(series_id)
            groups[1].append(len(mwgroup) - 1)
            continue

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
            same = mw.is_same_series(mwgroup[idx])
            if same:
                # the same series should have the same study uuid
                assert mwgroup[idx].dcm_data.get('StudyInstanceUID', None) == file_studyUID
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
    seqinfo = ordereddict()

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
        series_files = [files[i] for i, s in enumerate(groups[0]) if s == series_id]
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
        except AttributeError:
            TR = -1
        try:
            TE = float(dcminfo.EchoTime)
        except AttributeError:
            TE = -1
        try:
            refphys = str(dcminfo.ReferringPhysicianName)
        except AttributeError:
            refphys = '-'

        image_type = tuple(dcminfo.ImageType)
        motion_corrected = 'MoCo' in dcminfo.SeriesDescription \
                           or 'MOCO' in image_type

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
            os.path.split(series_files[0])[1],
            series_id,
            os.path.basename(os.path.dirname(series_files[0])),
            '-', '-',
            size[0], size[1], size[2], size[3],
            TR, TE,
            dcminfo.ProtocolName,
            motion_corrected,
            # New ones by us
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
                seqinfo[studyUID] = ordereddict()
            seqinfo[studyUID][info] = series_files
        elif per_accession_number:
            if accession_number not in seqinfo:
                seqinfo[accession_number] = ordereddict()
            seqinfo[accession_number][info] = series_files
        else:
            seqinfo[info] = series_files

    if per_studyUID:
        lgr.info("Generated sequence info for %d studies with %d entries total",
                 len(seqinfo), sum(map(len, seqinfo.values())))
    elif per_accession_number:
        lgr.info("Generated sequence info for %d accession numbers with %d entries total",
                 len(seqinfo), sum(map(len, seqinfo.values())))
    else:
        lgr.info("Generated sequence info with %d entries", len(seqinfo))
    return seqinfo
