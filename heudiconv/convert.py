from __future__ import annotations

__docformat__ = "numpy"

from collections.abc import Callable
import logging
import os
import os.path as op
import random
import re
import shutil
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, List, Optional, cast

import filelock
from nipype import Node
from nipype.interfaces.base import TraitListObject

from .bids import (
    BIDS_VERSION,
    BIDSError,
    add_participant_record,
    populate_bids_templates,
    populate_intended_for,
    sanitize_label,
    save_scans_key,
    tuneup_bids_json_files,
)
from .dicoms import (
    compress_dicoms,
    embed_metadata_from_dicoms,
    group_dicoms_into_seqinfos,
)
from .due import Doi, due
from .utils import (
    SeqInfo,
    TempDirs,
    assure_no_file_exists,
    clear_temp_dicoms,
    file_md5sum,
    load_json,
    read_config,
    safe_copyfile,
    safe_movefile,
    save_json,
    set_readonly,
    treat_infofile,
    write_config,
)

if TYPE_CHECKING:
    if sys.version_info >= (3, 8):
        from typing import TypedDict
    else:
        from typing_extensions import TypedDict

    class PopulateIntendedForOpts(TypedDict, total=False):
        matching_parameters: str | list[str]
        criterion: str


LOCKFILE = "heudiconv.lock"
DW_IMAGE_IN_FMAP_FOLDER_WARNING = (
    "Diffusion-weighted image saved in non dwi folder ({folder})"
)
lgr = logging.getLogger(__name__)


def conversion_info(
    subject: str,
    outdir: str,
    info: dict[tuple[str, tuple[str, ...], None], list],
    filegroup: dict[str, list[str]],
    ses: Optional[str],
) -> list[tuple[str, tuple[str, ...], list[str]]]:
    convert_info: list[tuple[str, tuple[str, ...], list[str]]] = []
    for key, items in info.items():
        if not items:
            continue
        template, outtype = key[0], key[1]
        # So no annotation_classes of any kind!  so if not used -- what was the
        # intention???? XXX
        outpath = outdir
        for idx, itemgroup in enumerate(items):
            if not isinstance(itemgroup, list):
                itemgroup = [itemgroup]
            for subindex, item in enumerate(itemgroup):
                parameters = {}
                if isinstance(item, dict):
                    parameters = {k: v for k, v in item.items()}
                    item = parameters["item"]
                    del parameters["item"]
                # some helper meta-varaibles
                parameters.update(
                    dict(
                        item=idx + 1,
                        subject=subject,
                        seqitem=item,
                        subindex=subindex + 1,
                        session="ses-" + str(ses),
                        bids_subject_session_prefix="sub-%s" % subject
                        + (("_ses-%s" % ses) if ses else ""),
                        bids_subject_session_dir="sub-%s" % subject
                        + (("/ses-%s" % ses) if ses else ""),
                        # referring_physician_name
                        # study_description
                    )
                )
                try:
                    files = filegroup[item]
                except KeyError:
                    files = filegroup[str(item)]
                outprefix = template.format(**parameters)
                convert_info.append((op.join(outpath, outprefix), outtype, files))
    return convert_info


def prep_conversion(
    sid: Optional[str],
    dicoms: Optional[list[str]],
    outdir: str,
    heuristic: ModuleType,
    converter: str,
    anon_sid: Optional[str],
    anon_outdir: Optional[str],
    with_prov: bool,
    ses: Optional[str],
    bids_options: Optional[str],
    seqinfo: Optional[dict[SeqInfo, list[str]]],
    min_meta: bool,
    overwrite: bool,
    dcmconfig: Optional[str],
    grouping: str,
) -> None:
    if dicoms:
        lgr.info("Processing %d dicoms", len(dicoms))
    elif seqinfo:
        lgr.info("Processing %d pre-sorted seqinfo entries", len(seqinfo))
    else:
        raise ValueError("neither dicoms nor seqinfo dict was provided")

    if bids_options is not None:
        if not sid:
            raise ValueError(
                "BIDS requires alphanumeric subject ID. Got an empty value"
            )
        sid = sanitize_label(sid)
        if ses:
            ses = sanitize_label(ses)

    if not anon_sid:
        if sid is None:
            raise ValueError("Neither 'sid' nor 'anon_sid' is true")
        anon_sid = sid
    if not anon_outdir:
        anon_outdir = outdir

    # Generate heudiconv info folder
    idir = op.join(outdir, ".heudiconv", anon_sid)
    if bids_options is not None and ses:
        idir = op.join(idir, "ses-%s" % str(ses))
    if anon_outdir == outdir:
        idir = op.join(idir, "info")
    if not op.exists(idir):
        os.makedirs(idir)

    ses_suffix = "_ses-%s" % ses if ses is not None else ""
    info_file = op.join(idir, "%s%s.auto.txt" % (sid, ses_suffix))
    edit_file = op.join(idir, "%s%s.edit.txt" % (sid, ses_suffix))
    filegroup_file = op.join(idir, "filegroup%s.json" % ses_suffix)

    # if conversion table(s) do not exist -- we need to prepare them
    # (the *prepare* stage in https://github.com/nipy/heudiconv/issues/134)
    # if overwrite - recalculate this anyways
    reuse_conversion_table = op.exists(edit_file)
    # We also might need to redo it if changes in the heuristic file
    # detected
    # ref: https://github.com/nipy/heudiconv/issues/84#issuecomment-330048609
    # for more automagical wishes
    target_heuristic_filename = op.join(idir, "heuristic.py")
    # facilitates change - TODO: remove in 1.0
    old_heuristic_filename = op.join(idir, op.basename(heuristic.filename))
    if op.exists(old_heuristic_filename):
        assure_no_file_exists(target_heuristic_filename)
        safe_copyfile(old_heuristic_filename, target_heuristic_filename)
        assure_no_file_exists(old_heuristic_filename)
    # TODO:
    #  1. add a test
    #  2. possibly extract into a dedicated function for easier logic flow here
    #     and a dedicated unittest
    if op.exists(target_heuristic_filename) and file_md5sum(
        target_heuristic_filename
    ) != file_md5sum(heuristic.filename):
        # remake conversion table
        reuse_conversion_table = False
        lgr.info(
            "Will not reuse existing conversion table files because heuristic "
            "has changed"
        )

    info: dict[tuple[str, tuple[str, ...], None], list]
    if reuse_conversion_table:
        lgr.info("Reloading existing filegroup.json " "because %s exists", edit_file)
        info = read_config(edit_file)
        filegroup = load_json(filegroup_file)
        # XXX Yarik finally understood why basedir was dragged along!
        # So we could reuse the same PATHs definitions possibly consistent
        # across re-runs... BUT that wouldn't work anyways if e.g.
        # DICOMs dumped with SOP UUIDs thus differing across runs etc
        # So either it would need to be brought back or reconsidered altogether
        # (since no sample data to test on etc)
    else:
        assure_no_file_exists(target_heuristic_filename)
        safe_copyfile(heuristic.filename, target_heuristic_filename)
        if dicoms:
            seqinfo = group_dicoms_into_seqinfos(
                dicoms,
                grouping,
                file_filter=getattr(heuristic, "filter_files", None),
                dcmfilter=getattr(heuristic, "filter_dicom", None),
                flatten=True,
                custom_grouping=getattr(heuristic, "grouping", None),
                # callable which will be provided dcminfo and returned
                # structure extend seqinfo
                custom_seqinfo=getattr(heuristic, "custom_seqinfo", None),
            )
        elif seqinfo is None:
            raise ValueError("Neither 'dicoms' nor 'seqinfo' is given")

        seqinfo_list = list(seqinfo.keys())
        filegroup = {si.series_id: x for si, x in seqinfo.items()}
        dicominfo_file = op.join(idir, "dicominfo%s.tsv" % ses_suffix)
        # allow to overwrite even if was present under git-annex already
        assure_no_file_exists(dicominfo_file)
        with open(dicominfo_file, "wt") as fp:
            fp.write("\t".join(SeqInfo._fields) + "\n")
            for seq in seqinfo_list:
                fp.write("\t".join([str(val) for val in seq]) + "\n")
        lgr.debug("Calling out to %s.infodict", heuristic)
        info = heuristic.infotodict(seqinfo_list)
        lgr.debug("Writing to {}, {}, {}".format(info_file, edit_file, filegroup_file))
        assure_no_file_exists(info_file)
        write_config(info_file, info)
        assure_no_file_exists(edit_file)
        write_config(edit_file, info)
        save_json(filegroup_file, filegroup)

    if bids_options is not None:
        # the other portion of the path would mimic BIDS layout
        # so we don't need to worry here about sub, ses at all
        tdir = anon_outdir
    else:
        tdir = op.join(anon_outdir, anon_sid)

    if converter.lower() != "none":
        lgr.info("Doing conversion using %s", converter)
        cinfo = conversion_info(anon_sid, tdir, info, filegroup, ses)
        convert(
            cinfo,
            converter=converter,
            scaninfo_suffix=getattr(heuristic, "scaninfo_suffix", ".json"),
            custom_callable=getattr(heuristic, "custom_callable", None),
            populate_intended_for_opts=getattr(
                heuristic, "POPULATE_INTENDED_FOR_OPTS", None
            ),
            with_prov=with_prov,
            bids_options=bids_options,
            outdir=tdir,
            min_meta=min_meta,
            overwrite=overwrite,
            dcmconfig=dcmconfig,
        )

    for item_dicoms in filegroup.values():
        clear_temp_dicoms(item_dicoms)

    if bids_options is not None and "notop" not in bids_options:
        lockfile = op.join(anon_outdir, LOCKFILE)
        if op.exists(lockfile):
            lgr.warning(
                "Existing lockfile found in {0} - waiting for the "
                "lock to be released. To set a timeout limit, set "
                "the HEUDICONV_FILELOCK_TIMEOUT environmental variable "
                "to a value in seconds. If this process hangs, it may "
                "require a manual deletion of the {0}.".format(lockfile)
            )
        timeout = float(os.getenv("HEUDICONV_LOCKFILE_TIMEOUT", -1))
        with filelock.SoftFileLock(lockfile, timeout=timeout):
            if seqinfo:
                keys = list(seqinfo)
                add_participant_record(
                    anon_outdir, anon_sid, keys[0].patient_age, keys[0].patient_sex
                )
            populate_bids_templates(
                anon_outdir, getattr(heuristic, "DEFAULT_FIELDS", {})
            )


def update_complex_name(metadata: dict[str, Any], filename: str) -> str:
    """
    Insert `_part-<mag|phase>` entity into filename if data are from a
    sequence with magnitude/phase part.

    Parameters
    ----------
    metadata : dict
        Scan metadata dictionary from BIDS sidecar file.
    filename : str
        Incoming filename

    Returns
    -------
    filename : str
        Updated filename with part entity added in appropriate position.
    """
    # Some scans separate magnitude/phase differently
    # A small note: _phase is deprecated, but this may add part-mag to
    # magnitude data while leaving phase data with a separate suffix,
    # depending on how one sets up their heuristic.
    unsupported_types = [
        "_phase",
        "_magnitude",
        "_magnitude1",
        "_magnitude2",
        "_phasediff",
        "_phase1",
        "_phase2",
    ]
    if any(ut in filename for ut in unsupported_types):
        return filename

    # Check to see if it is magnitude or phase part:
    img_type = cast(List[str], metadata.get("ImageType", []))
    if "M" in img_type:
        mag_or_phase = "mag"
    elif "P" in img_type:
        mag_or_phase = "phase"
    else:
        raise RuntimeError("Data type could not be inferred from the metadata.")

    # Determine scan suffix
    filetype = "_" + filename.split("_")[-1]

    # Insert part label
    if not ("_part-%s" % mag_or_phase) in filename:
        # If "_part-" is specified, prepend the 'mag_or_phase' value.
        if "_part-" in filename:
            raise BIDSError(
                "Part label for images will be automatically set, "
                "remove from heuristic"
            )

        # Insert it **before** the following string(s), whichever appears first.
        # https://bids-specification.readthedocs.io/en/stable/99-appendices/09-entities.html
        entities_after_part = [
            "_proc",
            "_hemi",
            "_space",
            "_split",
            "_recording",
            "_chunk",
            "_res",
            "_den",
            "_label",
            "_desc",
            filetype,
        ]
        for label in entities_after_part:
            if (label == filetype) or (label in filename):
                filename = filename.replace(label, "_part-%s%s" % (mag_or_phase, label))
                break

    return filename


def update_multiecho_name(
    metadata: dict[str, Any], filename: str, echo_times: list[float]
) -> str:
    """
    Insert `_echo-<num>` entity into filename if data are from a multi-echo
    sequence.

    Parameters
    ----------
    metadata : dict
        Scan metadata dictionary from BIDS sidecar file.
    filename : str
        Incoming filename
    echo_times : list
        List of all echo times from scan. Used to determine the echo *number*
        (i.e., index) if field is missing from metadata.

    Returns
    -------
    filename : str
        Updated filename with echo entity added, if appropriate.
    """
    # Field maps separate echoes differently, so do not attempt to update any filenames with these
    # suffixes
    unsupported_types = [
        "_magnitude",
        "_magnitude1",
        "_magnitude2",
        "_phasediff",
        "_phase1",
        "_phase2",
        "_fieldmap",
    ]
    if any(ut in filename for ut in unsupported_types):
        return filename

    if not isinstance(echo_times, list):
        raise TypeError(
            f'Argument "echo_times" must be a list, not a {type(echo_times)}'
        )

    # Get the EchoNumber from json file info.  If not present, use EchoTime.
    if "EchoNumber" in metadata.keys():
        echo_number = metadata["EchoNumber"]
        assert isinstance(echo_number, int)
    elif "EchoTime" in metadata.keys():
        echo_number = echo_times.index(metadata["EchoTime"]) + 1
    else:
        raise KeyError(
            'Either "EchoNumber" or "EchoTime" must be in metadata keys. '
            f"Keys detected: {metadata.keys()}"
        )

    # Determine scan suffix
    filetype = "_" + filename.split("_")[-1]

    # Insert it **before** the following string(s), whichever appears first.
    # https://bids-specification.readthedocs.io/en/stable/99-appendices/09-entities.html
    entities_after_echo = [
        "_flip",
        "_inv",
        "_mt",
        "_part",
        "_proc",
        "_hemi",
        "_space",
        "_split",
        "_recording",
        "_chunk",
        "_res",
        "_den",
        "_label",
        "_desc",
        filetype,
    ]
    for label in entities_after_echo:
        if (label == filetype) or (label in filename):
            filename = filename.replace(label, "_echo-%s%s" % (echo_number, label))
            break

    return filename


def update_uncombined_name(
    metadata: dict[str, Any], filename: str, channel_names: list[str]
) -> str:
    """
    Insert `_ch-<num>` entity into filename if data are from a sequence
    with "save uncombined".

    Parameters
    ----------
    metadata : dict
        Scan metadata dictionary from BIDS sidecar file.
    filename : str
        Incoming filename
    channel_names : list
        List of all channel names from scan. Used to determine the channel
        *number* (i.e., index) if field is missing from metadata.

    Returns
    -------
    filename : str
        Updated filename with ch entity added, if appropriate.
    """
    # In case any scan types separate channels differently
    unsupported_types: list[str] = []
    if any(ut in filename for ut in unsupported_types):
        return filename

    if not isinstance(channel_names, list):
        raise TypeError(
            f'Argument "channel_names" must be a list, not a {type(channel_names)}'
        )

    # Determine the channel number
    coil_string = metadata["CoilString"]
    assert isinstance(coil_string, str)
    channel_number = "".join(c for c in coil_string if c.isdigit())
    if not channel_number:
        channel_number = str(channel_names.index(coil_string) + 1)
    channel_number = channel_number.zfill(2)

    # Determine scan suffix
    filetype = "_" + filename.split("_")[-1]

    # Insert it **before** the following string(s), whichever appears first.
    # Choosing to put channel near the end since it's not in the specification yet.
    # See https://bids-specification.readthedocs.io/en/stable/99-appendices/09-entities.html
    entities_after_ch = [
        "_proc",
        "_hemi",
        "_space",
        "_split",
        "_recording",
        "_chunk",
        "_res",
        "_den",
        "_label",
        "_desc",
        filetype,
    ]
    for label in entities_after_ch:
        if (label == filetype) or (label in filename):
            filename = filename.replace(label, "_ch-%s%s" % (channel_number, label))
            break
    return filename


def convert(
    items: list[tuple[str, tuple[str, ...], list[str]]],
    converter: str,
    scaninfo_suffix: str,
    custom_callable: Optional[Callable[[str, tuple[str, ...], list[str]], Any]],
    with_prov: bool,
    bids_options: Optional[str],
    outdir: str,
    min_meta: bool,
    overwrite: bool,
    symlink: bool = True,
    prov_file: Optional[str] = None,
    dcmconfig: Optional[str] = None,
    populate_intended_for_opts: Optional[PopulateIntendedForOpts] = None,
) -> None:
    """Perform actual conversion (calls to converter etc) given info from
    heuristic's `infotodict`
    """
    prov_files: list[str] = []
    tempdirs = TempDirs()

    if bids_options is not None:
        due.cite(
            # doi matches the BIDS_VERSION
            Doi("10.5281/zenodo.4085321"),
            description="Brain Imaging Data Structure (BIDS) Specification",
            path="bids",
            version=BIDS_VERSION,
            tags=["implementation"],
        )
        due.cite(
            Doi("10.1038/sdata.2016.44"),
            description="Brain Imaging Data Structure (BIDS), Original paper",
            path="bids",
            tags=["documentation"],
        )

    for item in items:
        prefix, outtypes, item_dicoms = item
        if isinstance(outtypes, str):  # type: ignore[unreachable]
            lgr.warning(  # type: ignore[unreachable]
                "Provided output types %r of type 'str' instead "
                "of a tuple for prefix %r. Likely need to fix-up your heuristic. "
                "Meanwhile we are 'manually' converting to 'tuple'",
                outtypes,
                prefix,
            )
            outtypes = (outtypes,)
        prefix_dirname = op.dirname(prefix)
        outname_bids = prefix + ".json"
        bids_outfiles = []
        # set empty outname and scaninfo in case we only want dicoms
        outname = ""
        scaninfo = ""
        lgr.info(
            "Converting %s (%d DICOMs) -> %s . Converter: %s . Output types: %s",
            prefix,
            len(item_dicoms),
            prefix_dirname,
            converter,
            outtypes,
        )
        # We want to create this dir only if we are converting it to nifti,
        # or if we're using BIDS
        dicom_only = outtypes == ("dicom",)
        if not (dicom_only and (bids_options is not None)) and not op.exists(
            prefix_dirname
        ):
            os.makedirs(prefix_dirname)

        for outtype in outtypes:
            lgr.debug(
                "Processing %d dicoms for output type %s. Overwrite=%s",
                len(item_dicoms),
                outtype,
                overwrite,
            )
            lgr.debug("Includes the following dicoms: %s", item_dicoms)

            if outtype == "dicom":
                convert_dicom(
                    item_dicoms,
                    bids_options,
                    prefix,
                    outdir,
                    tempdirs,
                    symlink,
                    overwrite,
                )
            elif outtype in ["nii", "nii.gz"]:
                assert converter == "dcm2niix", f"Invalid converter {converter}"
                due.cite(
                    Doi("10.1016/j.jneumeth.2016.03.001"),
                    path="dcm2niix",
                    description="DICOM to NIfTI + .json sidecar conversion utility",
                    tags=["implementation"],
                )
                outname, scaninfo = (prefix + "." + outtype, prefix + scaninfo_suffix)

                if not op.exists(outname) or overwrite:
                    tmpdir = tempdirs("dcm2niix")

                    # run conversion through nipype
                    res, prov_file = nipype_convert(
                        item_dicoms, prefix, with_prov, bids_options, tmpdir, dcmconfig
                    )

                    bids_outfiles = save_converted_files(
                        res,
                        item_dicoms,
                        bids_options,
                        outtype,
                        prefix,
                        outname_bids,
                        overwrite=overwrite,
                    )

                    # save acquisition time information if it's BIDS
                    # at this point we still have acquisition date
                    if bids_options is not None:
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

        # add the taskname field to the json file(s):
        add_taskname_to_infofile(bids_outfiles)

        if len(bids_outfiles) > 1:
            lgr.warning(
                "For now not embedding BIDS and info generated "
                ".nii.gz itself since sequence produced "
                "multiple files"
            )
        elif not bids_outfiles:
            lgr.debug("No BIDS files were produced, nothing to embed to then")
        elif outname and not min_meta:
            embed_metadata_from_dicoms(
                bids_options,
                item_dicoms,
                outname,
                outname_bids,
                prov_file,
                scaninfo,
                tempdirs,
                with_prov,
            )
        if scaninfo and op.exists(scaninfo):
            lgr.info("Post-treating %s file", scaninfo)
            treat_infofile(scaninfo)

        # this may not always be the case: ex. fieldmap1, fieldmap2
        # will address after refactor
        if outname and op.exists(outname):
            set_readonly(outname)

        if custom_callable is not None:
            custom_callable(*item)

    # Populate "IntendedFor" for fmap files if requested in heuristic
    if populate_intended_for_opts is not None:
        # Because fmap files can only be used to correct for distortions in images
        # collected within the same scanning session, find unique subject/session
        # combinations from the outname in each item:
        outnames = [item[0] for item in items]
        # - grab "sub-<sID>[/ses-<ses>]", and keep only unique ones:
        sessions: set[str] = set()
        for oname in outnames:
            m = re.search(
                "sub-(?P<subj>[a-zA-Z0-9]*)([{0}_]ses-(?P<ses>[a-zA-Z0-9]*))?".format(
                    op.sep
                ),
                oname,
            )
            if m:
                sessions.add(m.group(0))
            else:
                # "sub-<sID>[/ses-<ses>]" is not present, so this is not BIDS
                # compliant and it doesn't make sense to add "IntendedFor":
                sessions.clear()
                break

        for ses in sessions:
            session_path = op.join(outdir, ses)
            populate_intended_for(session_path, **populate_intended_for_opts)


def convert_dicom(
    item_dicoms: list[str],
    bids_options: Optional[str],
    prefix: str,
    outdir: str,
    tempdirs: TempDirs,
    _symlink: bool,
    overwrite: bool,
) -> None:
    """Save DICOMs as output (default is by symbolic link)

    Parameters
    ----------
    item_dicoms : list of filenames
        DICOMs to save
    bids_options : str or None
        If not None then save to BIDS format. String may be empty
        or contain bids specific options
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
    """
    if bids_options is not None:
        # mimic the same hierarchy location as the prefix
        # although it could all have been done probably
        # within heuristic really
        sourcedir = op.join(outdir, "sourcedata")
        sourcedir_ = op.join(sourcedir, op.dirname(op.relpath(prefix, outdir)))
        if not op.exists(sourcedir_):
            os.makedirs(sourcedir_)

        compress_dicoms(
            item_dicoms, op.join(sourcedir_, op.basename(prefix)), tempdirs, overwrite
        )
    else:
        dicomdir = prefix + "_dicom"
        if op.exists(dicomdir):
            lgr.info(
                "Found existing DICOM directory {}, " "removing...".format(dicomdir)
            )
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


def nipype_convert(
    item_dicoms: list[str],
    prefix: str,
    with_prov: bool,
    bids_options: Optional[str],
    tmpdir: str,
    dcmconfig: Optional[str] = None,
) -> tuple[Node, Optional[str]]:
    """
    Converts DICOMs grouped from heuristic using Nipype's Dcm2niix interface.

    Parameters
    ----------
    item_dicoms : list
        DICOM files to convert
    prefix : str
        Heuristic output path
    with_prov : bool
        Store provenance information
    bids_options : str or None
        If not None then output BIDS sidecar JSONs
        String may contain bids specific options
    tmpdir : str
        Conversion working directory
    dcmconfig : str, optional
        JSON file used for additional Dcm2niix configuration
    """
    import nipype

    if with_prov:
        from nipype import config

        config.enable_provenance()
    from nipype.interfaces.dcm2nii import Dcm2niix

    # <https://github.com/python/mypy/issues/9864>
    item_dicoms = list(map(op.abspath, item_dicoms))  # type: ignore[arg-type]

    fromfile = dcmconfig if dcmconfig else None
    if fromfile:
        lgr.info("Using custom config file %s", fromfile)

    convertnode = Node(Dcm2niix(from_file=fromfile), name="convert")
    convertnode.base_dir = tmpdir
    convertnode.inputs.source_names = item_dicoms
    convertnode.inputs.out_filename = op.basename(
        prefix
    ) + "_heudiconv%03d" % random.randint(0, 999)
    prefix_dir = op.dirname(prefix)
    # if provided prefix had a path in it -- pass is as output_dir instead of default curdir
    if prefix_dir:
        convertnode.inputs.output_dir = prefix_dir

    if nipype.__version__.split(".")[0] == "0":
        # deprecated since 1.0, might be needed(?) before
        convertnode.inputs.terminal_output = "allatonce"
    else:
        convertnode.terminal_output = "allatonce"
    convertnode.inputs.bids_format = bids_options is not None
    eg = convertnode.run()

    # prov information
    prov_file = prefix + "_prov.ttl" if with_prov else None
    if prov_file:
        safe_movefile(
            op.join(convertnode.base_dir, convertnode.name, "provenance.ttl"), prov_file
        )

    return eg, prov_file


def save_converted_files(
    res: Node,
    item_dicoms: list[str],
    bids_options: Optional[str],
    outtype: str,
    prefix: str,
    outname_bids: str,
    overwrite: bool,
) -> list[str]:
    """Copy converted files from tempdir to output directory.

    Will rename files if necessary.

    Parameters
    ----------
    res : Node
        Nipype conversion Node with results
    item_dicoms: list
        Filenames of converted DICOMs
    bids : list or None
        If not list save to BIDS
        List may contain bids specific options
    prefix : str

    Returns
    -------
    bids_outfiles
        Converted BIDS files

    """
    from nipype.interfaces.base import isdefined

    prefix_dirname, prefix_basename = op.split(prefix)

    bids_outfiles: list[str] = []
    res_files = res.outputs.converted_files

    if not len(res_files):
        lgr.debug("DICOMs {} were not converted".format(item_dicoms))
        return []

    if isdefined(res.outputs.bvecs) and isdefined(res.outputs.bvals):
        bvals, bvecs = res.outputs.bvals, res.outputs.bvecs
        bvals = list(bvals) if isinstance(bvals, TraitListObject) else bvals
        bvecs = list(bvecs) if isinstance(bvecs, TraitListObject) else bvecs
        if prefix_dirname.endswith("dwi"):
            outname_bvecs, outname_bvals = prefix + ".bvec", prefix + ".bval"
            safe_movefile(bvecs, outname_bvecs, overwrite)
            safe_movefile(bvals, outname_bvals, overwrite)
        else:
            if bvals_are_zero(bvals):
                to_remove = bvals + bvecs if isinstance(bvals, list) else [bvals, bvecs]
                for ftr in to_remove:
                    os.remove(ftr)
                lgr.debug("%s and %s were removed since not dwi", bvecs, bvals)
            else:
                lgr.warning(
                    DW_IMAGE_IN_FMAP_FOLDER_WARNING.format(folder=prefix_dirname)
                )
                lgr.warning(
                    ".bvec and .bval files will be generated. This is NOT BIDS compliant"
                )
                outname_bvecs, outname_bvals = prefix + ".bvec", prefix + ".bval"
                safe_movefile(bvecs, outname_bvecs, overwrite)
                safe_movefile(bvals, outname_bvals, overwrite)

    if isinstance(res_files, list):
        res_files = sorted(res_files)
        # we should provide specific handling for fmap,
        # dwi etc which might spit out multiple files

        suffixes = (
            [str(i + 1) for i in range(len(res_files))]
            if (bids_options is not None)
            else None
        )

        if not suffixes:
            lgr.warning(
                "Following series files likely have "
                "multiple (%d) volumes (orientations?) "
                "generated: %s ...",
                len(res_files),
                item_dicoms[0],
            )
            suffixes = [str(-i - 1) for i in range(len(res_files))]

        # Also copy BIDS files although they might need to
        # be merged/postprocessed later
        bids_files = (
            sorted(res.outputs.bids)
            if len(res.outputs.bids) == len(res_files)
            else [None] * len(res_files)
        )
        # preload since will be used in multiple spots
        bids_metas = [load_json(b) for b in bids_files if b]

        ###   Do we have a multi-echo series?   ###
        #   Some Siemens sequences (e.g. CMRR's MB-EPI) set the label 'TE1',
        #   'TE2', etc. in the 'ImageType' field. However, other seqs do not
        #   (e.g. MGH ME-MPRAGE). They do set a 'EchoNumber', but not for the
        #   first echo.  To compound the problem, the echoes are NOT in order,
        #   so the first NIfTI file does not correspond to echo-1, etc. So, we
        #   need to know, beforehand, whether we are dealing with a multi-echo
        #   series. To do that, the most straightforward way is to read the
        #   echo times for all bids_files and see if they are all the same or not.

        # Collect some metadata across all images
        echo_times: set[float] = set()
        channel_names: set[str] = set()
        image_types: set[str] = set()
        for metadata in bids_metas:
            if not metadata:
                continue
            try:
                echo_times.add(metadata["EchoTime"])
            except KeyError:
                pass
            try:
                channel_names.add(metadata["CoilString"])
            except KeyError:
                pass
            try:
                image_types.update(metadata["ImageType"])
            except KeyError:
                pass

        is_multiecho = (
            len(set(filter(bool, echo_times))) > 1
        )  # Check for varying echo times
        is_uncombined = (
            len(set(filter(bool, channel_names))) > 1
        )  # Check for uncombined data
        is_complex = (
            "M" in image_types and "P" in image_types
        )  # Determine if data are complex (magnitude + phase)
        echo_times_lst = sorted(echo_times)  # also converts to list
        channel_names_lst = sorted(channel_names)  # also converts to list

        ### Loop through the bids_files, set the output name and save files
        for fl, suffix, bids_file, bids_meta in zip(
            res_files, suffixes, bids_files, bids_metas
        ):
            # TODO: monitor conversion duration

            # set the prefix basename for this specific file (we'll modify it,
            # and we don't want to modify it for all the bids_files):
            this_prefix_basename = prefix_basename

            # Update name for certain criteria
            if bids_file:
                if is_multiecho:
                    this_prefix_basename = update_multiecho_name(
                        bids_meta, this_prefix_basename, echo_times_lst
                    )

                if is_complex:
                    this_prefix_basename = update_complex_name(
                        bids_meta, this_prefix_basename
                    )

                if is_uncombined:
                    this_prefix_basename = update_uncombined_name(
                        bids_meta, this_prefix_basename, channel_names_lst
                    )

            # Fallback option:
            # If we have failed to modify this_prefix_basename, because it didn't fall
            #   into any of the options above, just add the suffix at the end:
            if this_prefix_basename == prefix_basename:
                this_prefix_basename += suffix

            # Finally, form the outname by stitching the directory and outtype:
            outname = op.join(prefix_dirname, this_prefix_basename)
            outfile = outname + "." + outtype

            # Write the files needed:
            safe_movefile(fl, outfile, overwrite)
            if bids_file:
                outname_bids_file = "%s.json" % (outname)
                safe_movefile(bids_file, outname_bids_file, overwrite)
                bids_outfiles.append(outname_bids_file)

    # res_files is not a list
    else:
        outname = "{}.{}".format(prefix, outtype)
        safe_movefile(res_files, outname, overwrite)
        if isdefined(res.outputs.bids):
            try:
                safe_movefile(res.outputs.bids, outname_bids, overwrite)
                bids_outfiles.append(outname_bids)
            except TypeError:  ##catch lists
                raise TypeError("Multiple BIDS sidecars detected.")
    return bids_outfiles


def add_taskname_to_infofile(infofiles: str | list[str]) -> None:
    """Add the "TaskName" field to json files with _task- entity in the name.

    Note: _task- entity could be present not only in functional data
    but in many other modalities now.

    Parameters
    ----------
    infofiles: list or str
        json filenames or a single filename.
    """

    # in case they pass a string with a path:
    if isinstance(infofiles, str):
        infofiles = [infofiles]

    for infofile in infofiles:
        meta_info = load_json(infofile)
        m = re.search(r"(?<=_task-)\w+", op.basename(infofile))
        if m:
            meta_info["TaskName"] = m.group(0).split("_")[0]
        else:
            # leave it to bids-validator to validate/inform about presence
            # of required entities/fields.
            continue

        # write to outfile
        save_json(infofile, meta_info)


def bvals_are_zero(bval_file: str | list) -> bool:
    """Checks if all entries in a bvals file are zero (or 5, for Siemens files).

    Parameters
    ----------
    bval_file : str
      file with the bvals

    Returns
    -------
    True if all are all 0 or 5; False otherwise.
    """

    # GE hyperband multi-echo containing diffusion info
    if isinstance(bval_file, list):
        return all(map(bvals_are_zero, bval_file))

    with open(bval_file) as f:
        bvals = f.read().split()

    bvals_unique = set(float(b) for b in bvals)
    return bvals_unique == {0.0} or bvals_unique == {5.0}
