import os
import os.path as op
import logging
import shutil
import sys

from .utils import (
    read_config,
    load_json,
    save_json,
    write_config,
    TempDirs,
    safe_copyfile,
    treat_infofile,
    set_readonly,
    clear_temp_dicoms,
    seqinfo_fields,
    assure_no_file_exists,
    file_md5sum
)
from .bids import (
    convert_sid_bids,
    populate_bids_templates,
    save_scans_key,
    tuneup_bids_json_files,
    add_participant_record,
)
from .dicoms import (
    group_dicoms_into_seqinfos,
    embed_metadata_from_dicoms,
    compress_dicoms
)

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
                    PY3 = sys.version_info[0] >= 3
                    files = filegroup[(str if PY3 else unicode)(item)]
                outprefix = template.format(**parameters)
                convert_info.append((op.join(outpath, outprefix),
                                    outtype, files))
    return convert_info


def prep_conversion(sid, dicoms, outdir, heuristic, converter, anon_sid,
                   anon_outdir, with_prov, ses, bids, seqinfo, min_meta,
                   overwrite):
    if dicoms:
        lgr.info("Processing %d dicoms", len(dicoms))
    elif seqinfo:
        lgr.info("Processing %d pre-sorted seqinfo entries", len(seqinfo))
    else:
        raise ValueError("neither dicoms nor seqinfo dict was provided")

    if bids:
        if not sid:
            raise ValueError(
                "BIDS requires alphanumeric subject ID. Got an empty value")
        if not sid.isalnum():  # alphanumeric only
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

    ses_suffix = "_ses-%s" % ses if ses is not None else ""
    info_file = op.join(idir, '%s%s.auto.txt' % (sid, ses_suffix))
    edit_file = op.join(idir, '%s%s.edit.txt' % (sid, ses_suffix))
    filegroup_file = op.join(idir, 'filegroup%s.json' % ses_suffix)

    # if conversion table(s) do not exist -- we need to prepare them
    # (the *prepare* stage in https://github.com/nipy/heudiconv/issues/134)
    # if overwrite - recalculate this anyways
    reuse_conversion_table = op.exists(edit_file)
    # We also might need to redo it if changes in the heuristic file
    # detected
    # ref: https://github.com/nipy/heudiconv/issues/84#issuecomment-330048609
    # for more automagical wishes
    target_heuristic_filename = op.join(idir, op.basename(heuristic.filename))
    # TODO:
    #  1. add a test
    #  2. possibly extract into a dedicated function for easier logic flow here
    #     and a dedicated unittest
    if (op.exists(target_heuristic_filename) and
        file_md5sum(target_heuristic_filename) != file_md5sum(heuristic.filename)):
        # remake conversion table
        reuse_conversion_table = False
        lgr.info(
            "Will not reuse existing conversion table files because heuristic "
            "has changed"
        )

    if reuse_conversion_table:
        lgr.info("Reloading existing filegroup.json "
                 "because %s exists", edit_file)
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
        assure_no_file_exists(target_heuristic_filename)
        safe_copyfile(heuristic.filename, idir)
        if dicoms:
            seqinfo = group_dicoms_into_seqinfos(
                dicoms,
                file_filter=getattr(heuristic, 'filter_files', None),
                dcmfilter=getattr(heuristic, 'filter_dicom', None),
                grouping=None)
        seqinfo_list = list(seqinfo.keys())
        filegroup = {si.series_id: x for si, x in seqinfo.items()}
        dicominfo_file = op.join(idir, 'dicominfo%s.tsv' % ses_suffix)
        # allow to overwrite even if was present under git-annex already
        assure_no_file_exists(dicominfo_file)
        with open(dicominfo_file, 'wt') as fp:
            fp.write('\t'.join([val for val in seqinfo_fields]) + '\n')
            for seq in seqinfo_list:
                fp.write('\t'.join([str(val) for val in seq]) + '\n')
        lgr.debug("Calling out to %s.infodict", heuristic)
        info = heuristic.infotodict(seqinfo_list)
        lgr.debug("Writing to {}, {}, {}".format(info_file, edit_file,
                                                 filegroup_file))
        assure_no_file_exists(info_file)
        write_config(info_file, info)
        assure_no_file_exists(edit_file)
        write_config(edit_file, info)
        save_json(filegroup_file, filegroup)

    if bids:
        # the other portion of the path would mimic BIDS layout
        # so we don't need to worry here about sub, ses at all
        tdir = anon_outdir
    else:
        tdir = op.join(anon_outdir, anon_sid)

    if converter.lower() != 'none':
        lgr.info("Doing conversion using %s", converter)
        cinfo = conversion_info(anon_sid, tdir, info, filegroup, ses)
        convert(cinfo,
                converter=converter,
                scaninfo_suffix=getattr(heuristic, 'scaninfo_suffix', '.json'),
                custom_callable=getattr(heuristic, 'custom_callable', None),
                with_prov=with_prov,
                bids=bids,
                outdir=tdir,
                min_meta=min_meta,
                overwrite=overwrite,)

    for item_dicoms in filegroup.values():
        clear_temp_dicoms(item_dicoms)

    if bids:
        if seqinfo:
            keys = list(seqinfo)
            add_participant_record(anon_outdir,
                                   anon_sid,
                                   keys[0].patient_age,
                                   keys[0].patient_sex)
        populate_bids_templates(anon_outdir,
                                getattr(heuristic, 'DEFAULT_FIELDS', {}))


def convert(items, converter, scaninfo_suffix, custom_callable, with_prov,
            bids, outdir, min_meta, overwrite, symlink=True, prov_file=None):
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
            outtypes = (outtypes,)

        prefix_dirname = op.dirname(prefix + '.ext')
        outname_bids = prefix + '.json'
        bids_outfiles = []
        lgr.info('Converting %s (%d DICOMs) -> %s . '
                 'Converter: %s . Output types: %s',
                 prefix, len(item_dicoms), prefix_dirname, converter, outtypes)
        # We want to create this dir only if we are converting it to nifti,
        # or if we're using BIDS
        dicom_only = outtypes == ('dicom',)
        if not(dicom_only and bids) and not op.exists(prefix_dirname):
            os.makedirs(prefix_dirname)

        for outtype in outtypes:
            lgr.debug("Processing %d dicoms for output type %s. Overwrite=%s",
                     len(item_dicoms), outtype, overwrite)
            lgr.debug("Includes the following dicoms: %s", item_dicoms)

            seqtype = op.basename(op.dirname(prefix)) if bids else None

            # set empty outname and scaninfo in case we only want dicoms
            outname = ''
            scaninfo = ''
            if outtype == 'dicom':
                convert_dicom(item_dicoms, bids, prefix,
                              outdir, tempdirs, symlink, overwrite)
            elif outtype in ['nii', 'nii.gz']:
                assert converter == 'dcm2niix', ('Invalid converter '
                                                 '{}'.format(converter))

                outname, scaninfo = (prefix + '.' + outtype,
                                     prefix + scaninfo_suffix)

                if not op.exists(outname) or overwrite:
                    tmpdir = tempdirs('dcm2niix')

                    # run conversion through nipype
                    res, prov_file = nipype_convert(item_dicoms, prefix, with_prov,
                                                    bids, tmpdir)

                    bids_outfiles = save_converted_files(res, item_dicoms, bids,
                                                         outtype, prefix,
                                                         outname_bids,
                                                         overwrite=overwrite)

                    # save acquisition time information if it's BIDS
                    # at this point we still have acquisition date
                    if bids:
                        save_scans_key(item, bids_outfiles)
                    # Fix up and unify BIDS files
                    tuneup_bids_json_files(bids_outfiles)

                    if prov_file:
                        prov_files.append(prov_file)

                    tempdirs.rmtree(tmpdir)
                else:
                    raise RuntimeError(
                        "was asked to convert into %s but destination already exists"
                        % (outname)
                    )

        if len(bids_outfiles) > 1:
            lgr.warning("For now not embedding BIDS and info generated "
                        ".nii.gz itself since sequence produced "
                        "multiple files")
        elif not bids_outfiles:
            lgr.debug("No BIDS files were produced, nothing to embed to then")
        elif outname:
            embed_metadata_from_dicoms(bids, item_dicoms, outname, outname_bids,
                                       prov_file, scaninfo, tempdirs, with_prov,
                                       min_meta)
        if scaninfo and op.exists(scaninfo):
            lgr.info("Post-treating %s file", scaninfo)
            treat_infofile(scaninfo)

        # this may not always be the case: ex. fieldmap1, fieldmap2
        # will address after refactor
        if outname and op.exists(outname):
            set_readonly(outname)

        if custom_callable is not None:
            custom_callable(*item)


def convert_dicom(item_dicoms, bids, prefix,
                  outdir, tempdirs, symlink, overwrite):
    """Save DICOMs as output (default is by symbolic link)

    Parameters
    ----------
    item_dicoms : list of filenames
        DICOMs to save
    bids : bool
        Save to BIDS format
    prefix : string
        Conversion outname
    outdir : string
        Output directory
    tempdirs : TempDirs instance
        Object to handle temporary directories created
        TODO: remove
    symlink : bool
        Create softlink to DICOMs - if False, create hardlink instead.
    overwrite : bool
        If True, allows overwriting of previous conversion

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
                        op.join(sourcedir_, op.basename(prefix)),
                        tempdirs,
                        overwrite)
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
#                if symlink:
#                    os.symlink(filename, outfile)
#                else:
#                    os.link(filename, outfile)
                shutil.copyfile(filename, outfile)


def nipype_convert(item_dicoms, prefix, with_prov, bids, tmpdir):
    """ """
    import nipype
    if with_prov:
        from nipype import config
        config.enable_provenance()
    from nipype import Node
    from nipype.interfaces.dcm2nii import Dcm2niix

    item_dicoms = list(map(op.abspath, item_dicoms)) # absolute paths

    dicom_dir = op.dirname(item_dicoms[0]) if item_dicoms else None

    convertnode = Node(Dcm2niix(), name='convert')
    convertnode.base_dir = tmpdir
    convertnode.inputs.source_names = item_dicoms
    convertnode.inputs.out_filename = op.basename(op.dirname(prefix))

    if nipype.__version__.split('.')[0] == '0':
        # deprecated since 1.0, might be needed(?) before
        convertnode.inputs.terminal_output = 'allatonce'
    else:
        convertnode.terminal_output = 'allatonce'
    convertnode.inputs.bids_format = bids
    eg = convertnode.run()

    # prov information
    prov_file = prefix + '_prov.ttl' if with_prov else None
    if prov_file:
        safe_copyfile(op.join(convertnode.base_dir,
                              convertnode.name,
                              'provenance.ttl'),
                      prov_file)

    return eg, prov_file


def save_converted_files(res, item_dicoms, bids, outtype, prefix, outname_bids, overwrite):
    """Copy converted files from tempdir to output directory.
    Will rename files if necessary.

    Parameters
    ----------
    res : Node
        Nipype conversion Node with results
    item_dicoms: list of filenames
        DICOMs converted
    bids : bool
        Option to save to BIDS
    prefix : string

    Returns
    -------
    bids_outfiles
        Converted BIDS files

    """
    from nipype.interfaces.base import isdefined

    bids_outfiles = []
    res_files = res.outputs.converted_files

    if not len(res_files):
        lgr.debug("DICOMs {} were not converted".format(item_dicoms))
        return

    if isdefined(res.outputs.bvecs) and isdefined(res.outputs.bvals):
        outname_bvecs, outname_bvals = prefix + '.bvec', prefix + '.bval'
        safe_copyfile(res.outputs.bvecs, outname_bvecs, overwrite)
        safe_copyfile(res.outputs.bvals, outname_bvals, overwrite)

    if isinstance(res_files, list):
        # we should provide specific handling for fmap,
        # dwi etc which might spit out multiple files

        suffixes = ([str(i+1) for i in range(len(res_files))]
                     if bids else None)

        if not suffixes:
            lgr.warning("Following series files likely have "
                        "multiple (%d) volumes (orientations?) "
                        "generated: %s ...",
                        len(res_files), item_dicoms[0])
            suffixes = [str(-i-1) for i in range(len(res_files))]

        # Also copy BIDS files although they might need to
        # be merged/postprocessed later
        bids_files = (res.outputs.bids
                      if len(res.outputs.bids) == len(res_files)
                      else [None] * len(res_files))

        for fl, suffix, bids_file in zip(res_files, suffixes, bids_files):
            outname = "%s%s.%s" % (prefix, suffix, outtype)
            safe_copyfile(fl, outname, overwrite)
            if bids_file:
                outname_bids_file = "%s%s.json" % (prefix, suffix)
                safe_copyfile(bids_file, outname_bids_file, overwrite)
                bids_outfiles.append(outname_bids_file)
    # res_files is not a list
    else:
        outname = "{}.{}".format(prefix, outtype)
        safe_copyfile(res_files, outname, overwrite)
        if isdefined(res.outputs.bids):
            try:
                safe_copyfile(res.outputs.bids, outname_bids, overwrite)
                bids_outfiles.append(outname_bids)
            except TypeError as exc:  ##catch lists
                raise TypeError("Multiple BIDS sidecars detected.")
    return bids_outfiles
