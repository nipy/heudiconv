# dicom operations
from __future__ import annotations

from collections.abc import Callable
import datetime
import logging
import os
import os.path as op
from pathlib import Path
import sys
import tarfile
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Hashable,
    List,
    NamedTuple,
    Optional,
    Protocol,
    Union,
    overload,
)
from unittest.mock import patch
import warnings

import pydicom as dcm

from .utils import (
    SeqInfo,
    TempDirs,
    get_typed_attr,
    load_json,
    set_readonly,
    strptime_dcm_da_tm,
    strptime_dcm_dt,
)

if TYPE_CHECKING:
    if sys.version_info >= (3, 8):
        from typing import Literal
    else:
        from typing_extensions import Literal

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    # suppress warning
    import nibabel.nicom.dicomwrappers as dw

# TODO: remove the kludge whenever
# https://github.com/moloney/dcmstack/pull/90 is merged and released
if not hasattr(dcm, "read_file"):
    dcm.read_file = dcm.dcmread

lgr = logging.getLogger(__name__)
total_files = 0
# Might be monkey patched by user heuristic to tune desired compression level.
# Preferably do not move/rename.
compresslevel = 9


class CustomSeqinfoT(Protocol):
    def __call__(self, wrapper: dw.Wrapper, series_files: list[str]) -> Hashable:
        ...


def create_seqinfo(
    mw: dw.Wrapper,
    series_files: list[str],
    series_id: str,
    custom_seqinfo: CustomSeqinfoT | None = None,
) -> SeqInfo:
    """Generate sequence info

    Parameters
    ----------
    mw: Wrapper
    series_files: list
    series_id: str
    """
    dcminfo = mw.dcm_data
    accession_number = dcminfo.get("AccessionNumber")

    # TODO: do not group echoes by default
    size: list[int] = list(mw.image_shape) + [len(series_files)]
    if len(size) < 4:
        size.append(1)

    # parse DICOM for seqinfo fields
    TR = get_typed_attr(dcminfo, "RepetitionTime", float, -1000) / 1000
    TE = get_typed_attr(dcminfo, "EchoTime", float, -1)
    refphys = get_typed_attr(dcminfo, "ReferringPhysicianName", str, "")
    image_type = get_typed_attr(dcminfo, "ImageType", tuple, ())
    is_moco = "MOCO" in image_type
    series_desc = get_typed_attr(dcminfo, "SeriesDescription", str, "")
    protocol_name = get_typed_attr(dcminfo, "ProtocolName", str, "")

    for k, m in (
        ([0x18, 0x24], "GE and Philips"),
        ([0x19, 0x109C], "Siemens"),
        ([0x18, 0x9005], "Siemens XA"),
    ):
        if v := dcminfo.get(k):
            sequence_name = v.value
            lgr.debug(
                "Identified sequence name as %s coming from the %r family of MR scanners",
                sequence_name,
                m,
            )
            break
    else:
        sequence_name = ""

    # initialized in `group_dicoms_to_seqinfos`
    global total_files
    total_files += len(series_files)

    custom_seqinfo_data = (
        custom_seqinfo(wrapper=mw, series_files=series_files)
        if custom_seqinfo
        else None
    )
    try:
        hash(custom_seqinfo_data)
    except TypeError:
        raise RuntimeError(
            "Data returned by the heuristics custom_seqinfo is not hashable. "
            "See https://heudiconv.readthedocs.io/en/latest/heuristics.html#custom_seqinfo for more "
            "details."
        )

    return SeqInfo(
        total_files_till_now=total_files,
        example_dcm_file=op.basename(series_files[0]),
        series_id=series_id,
        dcm_dir_name=op.basename(op.dirname(series_files[0])),
        series_files=len(series_files),
        unspecified="",
        dim1=size[0],
        dim2=size[1],
        dim3=size[2],
        dim4=size[3],
        TR=TR,
        TE=TE,
        protocol_name=protocol_name,
        is_motion_corrected=is_moco,
        is_derived="derived" in [x.lower() for x in image_type],
        patient_id=dcminfo.get("PatientID"),
        study_description=dcminfo.get("StudyDescription"),
        referring_physician_name=refphys,
        series_description=series_desc,
        sequence_name=sequence_name,
        image_type=image_type,
        accession_number=accession_number,
        # For demographics to populate BIDS participants.tsv
        patient_age=dcminfo.get("PatientAge"),
        patient_sex=dcminfo.get("PatientSex"),
        date=dcminfo.get("AcquisitionDate"),
        series_uid=dcminfo.get("SeriesInstanceUID"),
        time=dcminfo.get("AcquisitionTime"),
        custom=custom_seqinfo_data,
    )


def validate_dicom(
    fl: str, dcmfilter: Optional[Callable[[dcm.dataset.Dataset], Any]]
) -> Optional[tuple[dw.Wrapper, tuple[int, str], Optional[str]]]:
    """
    Parse DICOM attributes. Returns None if not valid.
    """
    mw = dw.wrapper_from_file(fl, force=True, stop_before_pixels=True)
    # clean series signature
    for sig in ("iop", "ICE_Dims", "SequenceName"):
        try:
            del mw.series_signature[sig]
        except KeyError:
            pass
    # Workaround for protocol name in private siemens csa header
    if not getattr(mw.dcm_data, "ProtocolName", "").strip():
        mw.dcm_data.ProtocolName = (
            parse_private_csa_header(mw.dcm_data, "ProtocolName", "tProtocolName")
            if mw.is_csa
            else ""
        )
    try:
        protocol_name = mw.dcm_data.ProtocolName
        assert isinstance(protocol_name, str)
        series_id = (int(mw.dcm_data.SeriesNumber), protocol_name)
    except AttributeError as e:
        lgr.warning('Ignoring %s since not quite a "normal" DICOM: %s', fl, e)
        return None
    if dcmfilter is not None and dcmfilter(mw.dcm_data):
        lgr.warning("Ignoring %s because of DICOM filter", fl)
        return None
    if mw.dcm_data[0x0008, 0x0016].repval in (
        "Raw Data Storage",
        "GrayscaleSoftcopyPresentationStateStorage",
    ):
        return None
    try:
        file_studyUID = mw.dcm_data.StudyInstanceUID
        assert isinstance(file_studyUID, str)
    except AttributeError:
        lgr.info("File {} is missing any StudyInstanceUID".format(fl))
        file_studyUID = None
    return mw, series_id, file_studyUID


class SeriesID(NamedTuple):
    series_number: int
    protocol_name: str
    file_studyUID: Optional[str] = None

    def __str__(self) -> str:
        s = f"{self.series_number}-{self.protocol_name}"
        if self.file_studyUID is not None:
            s += f"-{self.file_studyUID}"
        return s


@overload
def group_dicoms_into_seqinfos(
    files: list[str],
    grouping: str,
    file_filter: Optional[Callable[[str], Any]] = None,
    dcmfilter: Optional[Callable[[dcm.dataset.Dataset], Any]] = None,
    flatten: Literal[False] = False,
    custom_grouping: str
    | Callable[
        [list[str], Optional[Callable[[dcm.dataset.Dataset], Any]], type[SeqInfo]],
        dict[SeqInfo, list[str]],
    ]
    | None = None,
    custom_seqinfo: CustomSeqinfoT | None = None,
) -> dict[Optional[str], dict[SeqInfo, list[str]]]:
    ...


@overload
def group_dicoms_into_seqinfos(
    files: list[str],
    grouping: str,
    file_filter: Optional[Callable[[str], Any]] = None,
    dcmfilter: Optional[Callable[[dcm.dataset.Dataset], Any]] = None,
    *,
    flatten: Literal[True],
    custom_grouping: str
    | Callable[
        [list[str], Optional[Callable[[dcm.dataset.Dataset], Any]], type[SeqInfo]],
        dict[SeqInfo, list[str]],
    ]
    | None = None,
    custom_seqinfo: CustomSeqinfoT | None = None,
) -> dict[SeqInfo, list[str]]:
    ...


def group_dicoms_into_seqinfos(
    files: list[str],
    grouping: str,
    file_filter: Optional[Callable[[str], Any]] = None,
    dcmfilter: Optional[Callable[[dcm.dataset.Dataset], Any]] = None,
    flatten: Literal[False, True] = False,
    custom_grouping: str
    | Callable[
        [list[str], Optional[Callable[[dcm.dataset.Dataset], Any]], type[SeqInfo]],
        dict[SeqInfo, list[str]],
    ]
    | None = None,
    custom_seqinfo: CustomSeqinfoT | None = None,
) -> dict[Optional[str], dict[SeqInfo, list[str]]] | dict[SeqInfo, list[str]]:
    """Process list of dicoms and return seqinfo and file group
    `seqinfo` contains per-sequence extract of fields from DICOMs which
    will be later provided into heuristics to decide on filenames

    Parameters
    ----------
    files : list of str
      List of files to consider
    grouping : {'studyUID', 'accession_number', 'all', 'custom'}
      How to group DICOMs for conversion. If 'custom', see `custom_grouping`
      parameter.
    file_filter : callable, optional
      Applied to each item of filenames. Should return True if file needs to be
      kept, False otherwise.
    dcmfilter : callable, optional
      If called on dcm_data and returns True, it is used to set series_id
    flatten : bool, optional
      Creates a flattened `seqinfo` with corresponding DICOM files. True when
      invoked with `dicom_dir_template`.
    custom_grouping: str or callable, optional
      grouping key defined within heuristic. Can be a string of a
      DICOM attribute, or a method that handles more complex groupings.
    custom_seqinfo: callable, optional
      A callable which will be provided MosaicWrapper giving possibility to
      extract any custom DICOM metadata of interest.

    Returns
    -------
    seqinfo : list of list
      `seqinfo` is a list of info entries per each sequence (some entry
      there defines a key for `filegrp`)
    filegrp : dict
      `filegrp` is a dictionary with files grouped per each sequence
    """
    allowed_groupings = ["studyUID", "accession_number", "all", "custom"]
    if grouping not in allowed_groupings:
        raise ValueError("I do not know how to group by {0}".format(grouping))
    per_studyUID = grouping == "studyUID"
    # per_accession_number = grouping == 'accession_number'
    lgr.info("Analyzing %d dicoms", len(files))

    group_keys: list[SeriesID] = []
    group_values: list[int] = []
    mwgroup: list[dw.Wrapper] = []
    studyUID: Optional[str] = None

    if file_filter:
        nfl_before = len(files)
        files = list(filter(file_filter, files))
        nfl_after = len(files)
        lgr.info(
            "Filtering out {0} dicoms based on their filename".format(
                nfl_before - nfl_after
            )
        )

    if grouping == "custom":
        if custom_grouping is None:
            raise RuntimeError("Custom grouping is not defined in heuristic")
        if callable(custom_grouping):
            return custom_grouping(files, dcmfilter, SeqInfo)
        grouping = custom_grouping
        study_customgroup = None

    removeidx = []
    for idx, filename in enumerate(files):
        mwinfo = validate_dicom(filename, dcmfilter)
        if mwinfo is None:
            removeidx.append(idx)
            continue
        mw, series_id_, file_studyUID = mwinfo
        series_id = SeriesID(series_id_[0], series_id_[1])
        if per_studyUID:
            series_id = series_id._replace(file_studyUID=file_studyUID)

        if flatten:
            if per_studyUID:
                if studyUID is None:
                    studyUID = file_studyUID
                assert (
                    studyUID == file_studyUID
                ), "Conflicting study identifiers found [{}, {}].".format(
                    studyUID, file_studyUID
                )
            elif custom_grouping:
                file_customgroup = mw.dcm_data.get(grouping)
                if study_customgroup is None:
                    study_customgroup = file_customgroup
                assert (
                    study_customgroup == file_customgroup
                ), "Conflicting {0} found: [{1}, {2}]".format(
                    grouping, study_customgroup, file_customgroup
                )

        ingrp = False
        # check if same series was already converted
        for idx in range(len(mwgroup)):
            if mw.is_same_series(mwgroup[idx]):
                if grouping != "all":
                    assert (
                        mwgroup[idx].dcm_data.get("StudyInstanceUID") == file_studyUID
                    ), "Same series found for multiple different studies"
                ingrp = True
                series_id = SeriesID(
                    mwgroup[idx].dcm_data.SeriesNumber,
                    mwgroup[idx].dcm_data.ProtocolName,
                )
                if per_studyUID:
                    series_id = series_id._replace(file_studyUID=file_studyUID)
                group_keys.append(series_id)
                group_values.append(idx)

        if not ingrp:
            mwgroup.append(mw)
            group_keys.append(series_id)
            group_values.append(len(mwgroup) - 1)

    group_map = dict(zip(group_keys, group_values))

    if removeidx:
        # remove non DICOMS from files
        for idx in sorted(removeidx, reverse=True):
            del files[idx]

    seqinfos: dict[Optional[str], dict[SeqInfo, list[str]]] = {}
    flat_seqinfos: dict[SeqInfo, list[str]] = {}
    # for the next line to make any sense the series_id needs to
    # be sortable in a way that preserves the series order
    for series_id, mwidx in sorted(group_map.items()):
        mw = mwgroup[mwidx]
        series_files = [files[i] for i, s in enumerate(group_keys) if s == series_id]
        if per_studyUID:
            studyUID = series_id.file_studyUID
            series_id = series_id._replace(file_studyUID=None)
        series_id_str = str(series_id)
        if mw.image_shape is None:
            # this whole thing has no image data (maybe just PSg DICOMs)
            # If this is a Siemens PhoenixZipReport or PhysioLog, keep it:
            if mw.dcm_data.get("SeriesDescription") == "PhoenixZIPReport":
                # give it a dummy shape, so that we can continue:
                mw.image_shape = (0, 0, 0)
            else:
                # nothing to see here, just move on
                continue
        seqinfo = create_seqinfo(mw, series_files, series_id_str, custom_seqinfo)

        key: Optional[str]
        if per_studyUID:
            key = studyUID
        elif grouping == "accession_number":
            key = mw.dcm_data.get("AccessionNumber")
        elif grouping == "all":
            key = "all"
        elif custom_grouping:
            key = mw.dcm_data.get(custom_grouping)
        else:
            key = ""
        lgr.debug(
            "%30s %30s %27s %27s %5s nref=%-2d nsrc=%-2d %s"
            % (
                key,
                seqinfo.series_id,
                seqinfo.series_description,
                mw.dcm_data.ProtocolName,
                seqinfo.is_derived,
                len(mw.dcm_data.get("ReferencedImageSequence", "")),
                len(mw.dcm_data.get("SourceImageSequence", "")),
                seqinfo.image_type,
            )
        )

        if not flatten:
            seqinfos.setdefault(key, {})[seqinfo] = series_files
        else:
            flat_seqinfos[seqinfo] = series_files

    if not flatten:
        entries = len(seqinfos)
        subentries = sum(map(len, seqinfos.values()))
    else:
        entries = len(flat_seqinfos)
        subentries = sum(map(len, flat_seqinfos.values()))

    if per_studyUID:
        lgr.info(
            "Generated sequence info for %d studies with %d entries total",
            entries,
            subentries,
        )
    elif grouping == "accession_number":
        lgr.info(
            "Generated sequence info for %d accession numbers with %d entries total",
            entries,
            subentries,
        )
    else:
        lgr.info("Generated sequence info with %d entries", entries)
    if not flatten:
        return seqinfos
    else:
        return flat_seqinfos


def get_reproducible_int(dicom_list: list[str]) -> int:
    """Get integer that can be used to reproducibly sort input DICOMs, which is based on when they were acquired.

    Parameters
    ----------
    dicom_list : list[str]
        Paths to existing DICOM files

    Returns
    -------
    int
        An integer relating to when the DICOM was acquired

    Raises
    ------
    AssertionError

    Notes
    -----

    1. When date and time for can be read (see :func:`get_datetime_from_dcm`), return
        that value as time in seconds since epoch (i.e., Jan 1 1970).
    2. In cases where a date/time/datetime is not available (e.g., anonymization stripped this info), return
        epoch + AcquisitionNumber (in seconds), which is AcquisitionNumber as an integer
    3. If 1 and 2 are not possible, then raise AssertionError and provide message about missing information

    Cases are based on only the first element of the dicom_list.

    """
    import calendar

    dicom = dcm.dcmread(dicom_list[0], stop_before_pixels=True, force=True)
    dicom_datetime = get_datetime_from_dcm(dicom)
    if dicom_datetime:
        return calendar.timegm(dicom_datetime.timetuple())

    acquisition_number = dicom.get("AcquisitionNumber")
    if acquisition_number:
        return int(acquisition_number)

    raise AssertionError(
        "No metadata found that can be used to sort DICOMs reproducibly. Was header information erased?"
    )


def get_datetime_from_dcm(dcm_data: dcm.FileDataset) -> Optional[datetime.datetime]:
    """Extract datetime from filedataset, or return None is no datetime information found.

    Parameters
    ----------
    dcm_data : dcm.FileDataset
        DICOM with header, e.g., as ready by pydicom.dcmread.
        Objects with __getitem__ and have those keys with values properly formatted may also work

    Returns
    -------
    Optional[datetime.datetime]
        One of several datetimes that are related to when the scan occurred, or None if no datetime can be found

    Notes
    ------
    The following fields are checked in order

    1. AcquisitionDate & AcquisitionTime  (0008,0022); (0008,0032)
    2. AcquisitionDateTime (0008,002A);
    3. SeriesDate & SeriesTime  (0008,0021); (0008,0031)

    """

    def check_tag(x: str) -> bool:
        return x in dcm_data and dcm_data[x].value.strip()

    if check_tag("AcquisitionDate") and check_tag("AcquisitionTime"):
        return strptime_dcm_da_tm(dcm_data, "AcquisitionDate", "AcquisitionTime")
    if check_tag("AcquisitionDateTime"):
        return strptime_dcm_dt(dcm_data, "AcquisitionDateTime")
    if check_tag("SeriesDate") and check_tag("SeriesTime"):
        return strptime_dcm_da_tm(dcm_data, "SeriesDate", "SeriesTime")
    return None


def compress_dicoms(
    dicom_list: list[str], out_prefix: str, tempdirs: TempDirs, overwrite: bool
) -> Optional[str]:
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
    tempdirs : TempDirs
      TempDirs object to handle multiple tmpdirs
    overwrite : bool
      Overwrite existing tarfiles

    Returns
    -------
    filename : str
      Result tarball
    """

    tmpdir = tempdirs(prefix="dicomtar")
    outtar = out_prefix + ".dicom.tgz"

    if op.exists(outtar) and not overwrite:
        lgr.info("File {} already exists, will not overwrite".format(outtar))
        return None
    # tarfile encodes current time.time inside making those non-reproducible
    # so we should choose which date to use.
    # Solution from DataLad although ugly enough:

    dicom_list = sorted(dicom_list)
    dcm_time = get_reproducible_int(dicom_list)

    def _assign_dicom_time(ti: tarfile.TarInfo) -> tarfile.TarInfo:
        # Reset the date to match the one from the dicom, not from the
        # filesystem so we could sort reproducibly
        ti.mtime = dcm_time
        return ti

    with patch("time.time", lambda: dcm_time):
        try:
            if op.lexists(outtar):
                os.unlink(outtar)
            with tarfile.open(
                outtar, "w:gz", compresslevel=compresslevel, dereference=True
            ) as tar:
                for filename in dicom_list:
                    outfile = op.join(tmpdir, op.basename(filename))
                    if not op.islink(outfile):
                        os.symlink(op.realpath(filename), outfile)
                    # place into archive stripping any lead directories and
                    # adding the one corresponding to prefix
                    tar.add(
                        outfile,
                        arcname=op.join(op.basename(out_prefix), op.basename(outfile)),
                        recursive=False,
                        filter=_assign_dicom_time,
                    )
        finally:
            tempdirs.rmtree(tmpdir)

    return outtar


# Note: This function is passed to nipype by `embed_metadata_from_dicoms()`,
# and nipype reparses the function source in a clean namespace that does not
# have `from __future__ import annotations` enabled.  Thus, we need to use
# Python 3.7-compatible annotations on this function, and any non-builtin types
# used in the annotations need to be included by import statements passed to
# the `nipype.Function` constructor.
def embed_dicom_and_nifti_metadata(
    dcmfiles: List[str],
    niftifile: str,
    infofile: Union[str, Path],
    bids_info: Optional[Dict[str, Any]],
) -> None:
    """Embed metadata from nifti (affine etc) and dicoms into infofile (json)

    `niftifile` should exist. Its affine's orientation information is used while
    establishing new `NiftiImage` out of dicom stack and together with `bids_info`
    (if provided) is dumped into json `infofile`

    Parameters
    ----------
    dcmfiles
    niftifile
    infofile
    bids_info: dict
      Additional metadata to be embedded. `infofile` is overwritten if exists,
      so here you could pass some metadata which would overload (at the first
      level of the dict structure, no recursive fancy updates) what is obtained
      from nifti and dicoms

    """
    # These imports need to be within the body of the function so that they
    # will be available when executed by nipype:
    import json
    import os.path

    import dcmstack as ds
    import nibabel as nb

    from heudiconv.utils import save_json

    stack = ds.parse_and_stack(dcmfiles, force=True).values()
    if len(stack) > 1:
        raise ValueError("Found multiple series")
    # may be odict now - iter to be safe
    stack = next(iter(stack))

    if not os.path.exists(niftifile):
        raise NotImplementedError(
            "%s does not exist. "
            "We are not producing new nifti files here any longer. "
            "Use dcm2niix directly or .convert.nipype_convert helper ." % niftifile
        )

    orig_nii = nb.load(niftifile)
    aff = orig_nii.affine  # type: ignore[attr-defined]
    ornt = nb.orientations.io_orientation(aff)
    axcodes = nb.orientations.ornt2axcodes(ornt)
    new_nii = stack.to_nifti(voxel_order="".join(axcodes), embed_meta=True)
    meta_info_str = ds.NiftiWrapper(new_nii).meta_ext.to_json()
    meta_info = json.loads(meta_info_str)
    assert isinstance(meta_info, dict)

    if bids_info:
        meta_info.update(bids_info)

    # write to outfile
    save_json(infofile, meta_info)


def embed_metadata_from_dicoms(
    bids_options: Optional[str],
    item_dicoms: list[str],
    outname: str,
    outname_bids: str,
    prov_file: Optional[str],
    scaninfo: str,
    tempdirs: TempDirs,
    with_prov: bool,
) -> None:
    """
    Enhance sidecar information file with more information from DICOMs

    Parameters
    ----------
    bids_options
    item_dicoms
    outname
    outname_bids
    prov_file
    scaninfo
    tempdirs
    with_prov

    Returns
    -------

    """
    from nipype import Function, Node

    tmpdir = tempdirs(prefix="embedmeta")

    # We need to assure that paths are absolute if they are relative
    # <https://github.com/python/mypy/issues/9864>
    item_dicoms = list(map(op.abspath, item_dicoms))  # type: ignore[arg-type]

    embedfunc = Node(
        Function(
            input_names=[
                "dcmfiles",
                "niftifile",
                "infofile",
                "bids_info",
            ],
            function=embed_dicom_and_nifti_metadata,
            imports=[
                "from pathlib import Path",
                "from typing import Any, Dict, List, Optional, Union",
            ],
        ),
        name="embedder",
    )
    embedfunc.inputs.dcmfiles = item_dicoms
    embedfunc.inputs.niftifile = op.abspath(outname)
    embedfunc.inputs.infofile = op.abspath(scaninfo)
    embedfunc.inputs.bids_info = (
        load_json(op.abspath(outname_bids)) if (bids_options is not None) else None
    )
    embedfunc.base_dir = tmpdir
    cwd = os.getcwd()

    lgr.debug(
        "Embedding into %s based on dicoms[0]=%s for nifti %s",
        scaninfo,
        item_dicoms[0],
        outname,
    )
    try:
        if op.lexists(scaninfo):
            # TODO: handle annexed file case
            if not op.islink(scaninfo):
                set_readonly(scaninfo, False)
        res = embedfunc.run()
        set_readonly(scaninfo)
        if with_prov:
            assert isinstance(prov_file, str)
            g = res.provenance.rdf()
            g.parse(prov_file, format="turtle")
            g.serialize(prov_file, format="turtle")
            set_readonly(prov_file)
    except Exception as exc:
        lgr.error("Embedding failed: %s", str(exc))
        os.chdir(cwd)


def parse_private_csa_header(
    dcm_data: dcm.dataset.Dataset,
    _public_attr: str,
    private_attr: str,
    default: Optional[str] = None,
) -> str:
    """
    Parses CSA header in cases where value is not defined publicly

    Parameters
    ----------
    dcm_data : pydicom Dataset object
        DICOM metadata
    public_attr : string
        non-private DICOM attribute
    private_attr : string
        private DICOM attribute
    default (optional)
        default value if private_attr not found

    Returns
    -------
    val (default: empty string)
        private attribute value or default
    """
    # TODO: provide mapping to private_attr from public_attr
    import dcmstack.extract as dsextract
    from nibabel.nicom import csareader

    try:
        # TODO: test with attr besides ProtocolName
        csastr = csareader.get_csa_header(dcm_data, "series")["tags"][
            "MrPhoenixProtocol"
        ]["items"][0]
        csastr = csastr.replace("### ASCCONV BEGIN", "### ASCCONV BEGIN ### ")
        parsedhdr = dsextract.parse_phoenix_prot("MrPhoenixProtocol", csastr)
        val = parsedhdr[private_attr].replace(" ", "")
    except Exception as e:
        lgr.debug("Failed to parse CSA header: %s", str(e))
        val = default or ""
    assert isinstance(val, str)
    return val
