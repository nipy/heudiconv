import os
import os.path as op
import logging
import shutil

from .utils import read_config, load_json, save_json, write_config, TempDirs
from .bids import convert_sid_bids
from .dicoms import compress_dicoms

lgr = logging.getLogger(__name__)


def conversion_info(subject, outdir, info, filegroup, ses):
    convert_info = []
    for key, items in info.items():
        if not items:
            continue
        template, outtype = key[0], key[1]
        # So no annotation_classes of any kind!  so if not used -- what was the
        # intension???? XXX
        outpath = outdir
        for idx, itemgroup in enumerate(items):
            if not isinstance(itemgroup, list):
                itemgroup = [itemgroup]
            for subindex, item in enumerate(itemgroup):
                parameters = {}
                if isinstance(item, dict):
                    parameters = {k: v for k, v in item.items()}
                    item = parameters['item']
                    del parameters['item']
                # some helper meta-varaibles
                parameters.update(dict(
                    item=idx + 1,
                    subject=subject,
                    seqitem=item,
                    subindex=subindex + 1,
                    session='ses-' + str(ses),
                    bids_subject_session_prefix=
                        'sub-%s' % subject + (('_ses-%s' % ses) if ses else ''),
                    bids_subject_session_dir=
                        'sub-%s' % subject + (('/ses-%s' % ses) if ses else ''),
                    # referring_physician_name
                    # study_description
                    ))
                try:
                    files = filegroup[item]
                except KeyError:
                    files = filegroup[(str if PY3 else unicode)(item)]
                outprefix = template.format(**parameters)
                convert_info.append((op.join(outpath, outprefix),
                                    outtype, files))
    return convert_info


def prep_conversion(sid, dicoms, outdir, heuristic, converter, anon_sid,
                   anon_outdir, with_prov, ses, bids, seqinfo, min_meta):
    if dicoms:
        lgr.info("Processing %d dicoms", len(dicoms))
    elif seqinfo:
        lgr.info("Processing %d pre-sorted seqinfo entries", len(seqinfo))
    else:
        raise ValueError("neither dicoms nor seqinfo dict was provided")

    if bids and not sid.isalnum(): # alphanumeric only
        sid, old_sid = convert_sid_bids(sid)

    if not anon_sid:
        anon_sid = sid
    if not anon_outdir:
        anon_outdir = outdir

    # Generate heudiconv info folder
    idir = op.join(outdir, '.heudiconv', sid)
    if bids and ses:
        idir = op.join(idir, 'ses-%s' % str(ses))
    if anon_outdir == outdir:
        idir = op.join(idir, 'info')
    if not op.exists(idir):
        os.makedirs(idir)

    shutil.copy(heuristic.filename, idir)
    ses_suffix = "_ses-%s" % ses if ses is not None else ""
    info_file = op.join(idir, '%s%s.auto.txt' % (sid, ses_suffix))
    edit_file = op.join(idir, '%s%s.edit.txt' % (sid, ses_suffix))
    filegroup_file = op.join(idir, 'filegroup%s.json' % ses_suffix)

    # MG - maybe add an option to force rerun?
    # related issue : https://github.com/nipy/heudiconv/issues/84
    if op.exists(edit_file):  # XXX may be condition on seqinfo is None
        lgr.info("Reloading existing filegroup.json because %s exists", edit_file)
        info = read_config(edit_file)
        filegroup = load_json(filegroup_file)
        # XXX Yarik finally understood why basedir was dragged along!
        # So we could reuse the same PATHs definitions possibly consistent
        # across re-runs... BUT that wouldn't work anyways if e.g.
        # DICOMs dumped with SOP UUIDs thus differing across runs etc
        # So either it would need to be brought back or reconsidered altogether
        # (since no sample data to test on etc)
    else:
        # TODO -- might have been done outside already!
        # MG -- will have to try with both dicom template, files
        if dicoms:
            seqinfo = group_dicoms_into_seqinfos(
                dicoms,
                file_filter=getattr(heuristic, 'filter_files', None),
                dcmfilter=getattr(heuristic, 'filter_dicom', None),
                grouping=None)
        seqinfo_list = list(seqinfo.keys())
        filegroup = {si.series_id: x for si, x in seqinfo.items()}
        dicominfo_file = op.join(idir, 'dicominfo%s.tsv' % ses_suffix)
        with open(dicominfo_file, 'wt') as fp:
            for seq in seqinfo_list:
                fp.write('\t'.join([str(val) for val in seq]) + '\n')
        lgr.debug("Calling out to %s.infodict", heuristic)
        info = heuristic.infotodict(seqinfo_list)
        lgr.debug("Writing to {}, {}, {}".format(info_file, edit_file,
                                                 filegroup_file))
        write_config(info_file, info)
        write_config(edit_file, info)
        save_json(filegroup_file, filegroup)

    if bids:
        # the other portion of the path would mimic BIDS layout
        # so we don't need to worry here about sub, ses at all
        tdir = anon_outdir
    else:
        tdir = op.join(anon_outdir, anon_sid)

    if converter != 'none':
        lgr.info("Doing conversion using %s", converter)
        cinfo = conversion_info(anon_sid, tdir, info, filegroup, ses)
        convert(cinfo,
                converter=converter,
                scaninfo_suffix=getattr(heuristic, 'scaninfo_suffix', '.json'),
                custom_callable=getattr(heuristic, 'custom_callable', None),
                with_prov=with_prov,
                bids=bids,
                outdir=tdir,
                min_meta=min_meta)
    if bids:
        if seqinfo:
            keys = list(seqinfo)
            add_participant_record(anon_outdir, anon_sid,
                                   keys[0].patient_age,
                                   keys[0].patient_sex)
        populate_bids_templates(anon_outdir,
                                getattr(heuristic, 'DEFAULT_FIELDS', {}))


def convert(items, converter, scaninfo_suffix, custom_callable, with_prov,
            bids, outdir, min_meta, symlink=True):
    """Perform actual conversion (calls to converter etc) given info from
    heuristic's `infotodict`

    Parameters
    ----------
    items
    symlink
    converter
    scaninfo_suffix
    custom_callable
    with_prov
    is_bids
    sourcedir
    outdir
    min_meta

    Returns
    -------
    None
    """
    prov_files = []
    tempdirs = TempDirs()

    for item_idx, item in enumerate(items):

        prefix, outtypes, item_dicoms = item[:3]
        if not isinstance(outtypes, (list, tuple)):
            outtypes = [outtypes]
        prefix_dirname = op.dirname(prefix + '.ext')
        prov_file = None
        outname_bids = prefix + '.json'
        outname_bids_files = []
        lgr.info('Converting %s (%d DICOMs) -> %s . '
                 'Converter: %s . Output types: %s',
                 prefix, len(item_dicoms), prefix_dirname, converter, outtypes)
        if not op.exists(prefix_dirname):
            os.makedirs(prefix_dirname)
        for outtype in outtypes:
            lgr.debug("Processing %d dicoms for output type %s",
                     len(item_dicoms), outtype)
            lgr.debug("Includes the following dicoms: %s", item_dicoms)

            seqtype = op.basename(op.dirname(prefix)) if bids else None

            if outtype == 'dicom':
                convert_dicom(item_dicoms, bids, prefix,
                              outdir, tempdirs, symlink)
            elif outtype in ['nii', 'nii.gz']:
                res = nipype_convert(item_dicoms, prefix, outtype,
                                     scaninfo_suffix, with_prov,
                                     bids, tempdirs):

                if isdefined(res.outputs.bvecs):
                    outname_bvecs = prefix + '.bvec'
                    outname_bvals = prefix + '.bval'
                    safe_copyfile(res.outputs.bvecs, outname_bvecs)
                    safe_copyfile(res.outputs.bvals, outname_bvals)

                res_files = res.outputs.converted_files
                if isinstance(res_files, list):
                    # TODO: move into a function
                    # by default just suffix them up
                    suffixes = None
                    # we should provide specific handling for fmap,
                    # dwi etc which might spit out multiple files
                    if is_bids:
                        if seqtype == 'fmap':
                            # expected!
                            suffixes = ["%d" % (i+1) for i in range(len(res_files))]
                    if not suffixes:
                        lgr.warning(
                            "Following series files likely have "
                            "multiple (%d) volumes (orientations?) "
                            "generated: %s ...",
                            len(res_files), item_dicoms[0]
                        )
                        suffixes = ['-%d' % (i+1) for i in range(len(res_files))]

                    # Also copy BIDS files although they might need to
                    # be merged/postprocessed later
                    if (converter == 'dcm2niix') and (
                      isdefined(res.outputs.bids)):
                        assert(len(res.outputs.bids) == len(res_files))
                        bids_files = res.outputs.bids
                    else:
                        bids_files = [None] * len(res_files)

                    for fl, suffix, bids_file in zip(res_files, suffixes, bids_files):
                        outname = "%s%s.%s" % (prefix, suffix, outtype)
                        safe_copyfile(fl, outname)
                        if bids_file:
                            outname_bids_file = "%s%s.json" % (prefix, suffix)
                            safe_copyfile(bids_file, outname_bids_file)
                            outname_bids_files.append(outname_bids_file)

                else:
                    safe_copyfile(res_files, outname)
                    if converter == 'dcm2niix' and isdefined(res.outputs.bids):
                        try:
                            safe_copyfile(res.outputs.bids, outname_bids)
                            outname_bids_files.append(outname_bids)
                        except TypeError as exc:  ##catch lists
                            lgr.warning(
                                "There was someone catching lists!: %s", exc
                            )
                            continue

                # save acquisition time information if it's BIDS
                # at this point we still have acquisition date
                if is_bids:
                    save_scans_key(item, outname_bids_files)
                # Fix up and unify BIDS files
                tuneup_bids_json_files(outname_bids_files)
                # we should provide specific handling for fmap,
                # dwi etc .json of which should get merged to satisfy
                # BIDS.  BUT wer might be somewhat not in time for a
                # party here since we sorted into multiple seqinfo
                # (e.g. magnitude, phase for fmap so we might want
                # to sort them into a single one)

            if with_prov:
                prov_file = prefix + '_prov.ttl'
                safe_copyfile(os.path.join(convertnode.base_dir,
                                             convertnode.name,
                                            'provenance.ttl'),
                                prov_file)
                prov_files.append(prov_file)

                if len(outname_bids_files) > 1:
                    lgr.warning(
                        "For now not embedding BIDS and info generated .nii.gz itself since sequence produced multiple files")
                else:
                    embed_metadata_from_dicoms(converter, is_bids, item_dicoms,
                                               outname, outname_bids, prov_file,
                                               scaninfo, tmpdir, with_prov,
                                               min_meta)
                if exists(scaninfo):
                    lgr.info("Post-treating %s file", scaninfo)
                    treat_infofile(scaninfo)
                os.chmod(outname, 0o0440)

        if custom_callable is not None:
            custom_callable(*item)
    shutil.rmtree(tmpdir)

def convert_dicom(item_dicoms, bids, sourcedir, prefix,
                  outdir, tempdirs, symlink):
    """Save DICOMs as output (default is by symbolic link)

    Parameters
    ----------
    item_dicoms : list of filenames
        DICOMs to save
    bids : bool
        Save to BIDS format
    sourcedir : string
        Path to BIDS output

    Returns
    -------
    None
    """
    if bids:
        # mimic the same hierarchy location as the prefix
        # although it could all have been done probably
        # within heuristic really
        sourcedir = op.join(outdir, 'sourcedata')
        sourcedir_ = op.join(sourcedir, op.dirname(op.relpath(prefix, outdir)))
        if not op.exists(sourcedir_):
            os.makedirs(sourcedir_)

        compress_dicoms(item_dicoms,
                        op.join(sourcedir_, op.basename(prefix),
                        tempdirs)) # MG - ensure tempdirs works
    else:
        dicomdir = prefix + '_dicom'
        if op.exists(dicomdir):
            lgr.info('Found existing DICOM directory {}, '
                     'removing...'.format(dicomdir))
            shutil.rmtree(dicomdir)
        os.mkdir(dicomdir)
        for filename in item_dicoms:
            outfile = op.join(dicomdir, op.basename(filename))
            if not op.islink(outfile):
                # TODO: add option to enable hardlink?
                if symlink:
                    os.symlink(filename, outfile)
                else:
                    os.link(filename, outfile)

def nipype_convert(item_dicoms, prefix, outtype, scaninfo_suffix, with_prov,
                   bids, tempdirs):
    """ """
    outname, scaninfo = prefix + '.' + outtype, prefix + scaninfo_suffix
    tmpdir = tempdirs(prefix='heudiconv')
    # MG - add option to force these to rerun
    if not op.exists(outname):
        if with_prov:
            from nipype import config
            config.enable_provenance()
        from nipype import Node
        # if converter == 'dcm2niix': ## MG - we only support this now..
        from nipype.interfaces.dcm2nii import Dcm2niix

        item_dicoms = list(map(os.path.abspath, item_dicoms))
        convertnode = Node(Dcm2niix(), name='convert')
        convertnode.base_dir = tmpdir
        convertnode.inputs.source_names = item_dicoms

        convertnode.inputs.out_filename = op.basename(prefix_dirname)
        convertnode.inputs.terminal_output = 'allatonce'
        convertnode.inputs.bids_format = bids
        return convertnode.run()
