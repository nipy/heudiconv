"""
(AKA dbic-bids) Flexible heuristic to establish BIDS DataLad datasets hierarchy

Initially developed and deployed at Dartmouth Brain Imaging Center
(http://dbic.dartmouth.edu) using Siemens Prisma 3T under the umbrellas of the
Center of Reproducible Neuroimaging Computation (ReproNim, http://repronim.org)
and Center for Open Neuroscience (CON, http://centerforopenneuroscience.org).

## Dataset ownership/location

Datasets will be arranged in a hierarchy similar to how study/exam cards are
arranged at the scanner console.  You should have

- "region" defined per each PI,
 - on the first level most probably as PI_StudentOrRA/ (e.g., Gobbini_Matteo)
   - StudyID_StudyName/   (e.g. 1002_faceangles)
     - Arbitrary name for the exam card -- it doesn't get into Study Description.

Selecting specific exam card would populate Study Description field using
aforementioned levels, which will be used by this heuristic to decide on the
location of the dataset.

In case of multiple sessions, it is recommended to generate separate "cards"
per each session.

## Sequence naming on the scanner console

Sequence names on the scanner must follow this specification to avoid manual
conversion/handling:

  [PREFIX:][WIP ]<datatype[-<suffix>]>[_ses-<SESID>][_task-<TASKID>][_acq-<ACQLABEL>][_run-<RUNID>][_dir-<DIR>][<more BIDS>][__<custom>]

where
 [PREFIX:] - leading capital letters followed by : are stripped/ignored
 [WIP ] - prefix is stripped/ignored (added by Philips for patch sequences)
 <...> - value to be entered
 [...] - optional -- might be nearly mandatory for some modalities (e.g.,
         run for functional) and very optional for others
 *ID - alpha-numerical identifier (e.g. 01,02, pre, post, pre01) for a run,
       task, session. Note that makes more sense to use numerical values for
       RUNID (e.g., _run-01, _run-02) for obvious sorting and possibly
       descriptive ones for e.g. SESID (_ses-movie, _ses-localizer)


<datatype[-suffix]>
   a known BIDS sequence datatype which is usually a name of the folder under
   subject's directory. And (optional) suffix is a specific sequence type
   (e.g., "bold" for func, or "T1w" for "anat"), which could often
   (but not always) be deduced from DICOM. Known to ReproIn BIDS modalities
   are:

     anat - anatomical data.  Might also be collected multiple times across
            runs (e.g. if subject is taken out of magnet etc), so could
            (optionally) have "_run" definition attached. For "standard anat"
            suffixes, please consult to "8.3 Anatomy imaging data" but most
            common are 'T1w', 'T2w', 'angio'.
     beh  - behavioral data. known but not "treated".
     func - functional (AKA task, including resting state) data.
            Typically contains multiple runs, and might have multiple different
            tasks different per each run
            (e.g. _task-memory_run-01, _task-oddball_run-02)
     fmap - field maps
     dwi  - diffusion weighted imaging (also can as well have runs)

   The other BIDS modalities are not known ATM and their data will not be
   converted and will be just skipped (with a warning). Full list of datatypes
   can be found at
   https://github.com/bids-standard/bids-specification/blob/v1.7.0/src/schema/objects/datatypes.yaml
   and their corresponding suffixes at
   https://github.com/bids-standard/bids-specification/tree/v1.7.0/src/schema/rules/datatypes

_ses-<SESID> (optional)
    a session.  Having a single sequence within a study would make that study
    follow "multi-session" layout. A common practice to have a _ses specifier
    within the scout sequence name. You can either specify explicit session
    identifier (SESID) or just say to maintain, create (starts with 1).
    You can also use _ses-{date} in case of scanning phantoms or non-human
    subjects and wanting sessions to be coded by the acquisition date.

_task-<TASKID> (optional)
    a short name for a task performed during that run.  If not provided and it
    is a func sequence, _task-UNKNOWN will be automatically added to comply with
    BIDS. Consult http://www.cognitiveatlas.org/tasks on known tasks.

_acq-<ACQLABEL> (optional)
    a short custom label to distinguish a different set of parameters used for
    acquiring the same modality (e.g. _acq-highres, _acq-lowres  etc)

_run-<RUNID> (optional)
    a (typically functional) run. The same idea as with SESID.

_dir-[AP,PA,LR,RL,VD,DV] (optional)
    to be used for fmap images, whenever a pair of the SE images is collected
    to be used to estimate the fieldmap

<more BIDS> (optional)
    any other fields (e.g. _acq-) from BIDS acquisition

__<custom> (optional)
  after two underscores any arbitrary comment which will not matter to how
  layout in BIDS. But that one theoretically should not be necessary,
  and (ab)use of it would just signal lack of thought while preparing sequence
  name to start with since everything could have been expressed in BIDS fields.

## Last moment checks/FAQ:

- Functional runs should have _task-<TASKID> field defined
- Do not use "+", "_" or "-" within SESID, TASKID, ACQLABEL, RUNID,  so we
  could detect "canceled" runs.
- If run was canceled -- just copy canceled run (with the same index) and re-run
  it. Files with overlapping name will be considered duplicate/canceled session
  and only the last one would remain.  The others would acquire
  __dup0<number>  suffix.

Although we still support "-" and "+" used within SESID and TASKID, their use is
not recommended, thus not listed here

## Scanner specifics

We perform following actions regardless of the type of scanner, but applied
generally to accommodate limitations imposed by different manufacturers/models:

### Philips

- We replace all ( with { and ) with } to be able e.g. to specify session {date}
- "WIP " prefix unconditionally added by the scanner is stripped
"""

from __future__ import annotations

from collections.abc import Iterable
from glob import glob
import hashlib
import logging
import os.path
import re
from typing import Any, Optional, TypeVar

import pydicom as dcm

from heudiconv.due import Doi, due
from heudiconv.utils import SeqInfo, StudySessionInfo

lgr = logging.getLogger("heudiconv")

T = TypeVar("T")

# Terminology to harmonise and use to name variables etc
# experiment
#  subject
#   [session]
#    exam (AKA scanning session) - currently seqinfo, unless brought together from multiple
#     series  (AKA protocol?)
#      - series_spec - deduced from fields the spec (literal value)
#      - series_info - the dictionary with fields parsed from series_spec

# Which fields in seqinfo (in this order) to check for the ReproIn spec
series_spec_fields = ("protocol_name", "series_description")

# dictionary from accession-number to runs that need to be marked as bad
# NOTE: even if filename has number that is 0-padded, internally no padding
# is done
fix_accession2run: dict[str, list[str]] = {
    # e.g.:
    # 'A000035': ['^8-', '^9-'],
}

# A dictionary containing fixes/remapping for sequence names per study.
# Keys are md5sum of study_description from DICOMs, in the form of PI-Experimenter^protocolname
# You can use `heudiconv -f reproin --command ls --files  PATH
# to list the "study hash".
# Values are list of tuples in the form (regex_pattern, substitution).
# If the  key is an empty string`''''`, it would apply to any study.
protocols2fix: dict[str | re.Pattern[str], list[tuple[str, str]]] = {
    # e.g., QA:
    # '43b67d9139e8c7274578b7451ab21123':
    #     [
    #      ('BOLD_p2_s4_3\.5mm', 'func_task-rest_acq-p2-s4-3.5mm'),
    #      ('BOLD_', 'func_task-rest'),
    #      ('_p2_s4',        '_acq-p2-s4'),
    #      ('_p2', '_acq-p2'),
    #     ],
    # '':  # for any study example with regexes used
    #     [
    #         ('AAHead_Scout_.*', 'anat-scout'),
    #         ('^dti_.*', 'dwi'),
    #         ('^.*_distortion_corr.*_([ap]+)_([12])', r'fmap-epi_dir-\1_run-\2'),
    #         ('^(.+)_ap.*_r(0[0-9])', r'func_task-\1_run-\2'),
    #         ('^t1w_.*', 'anat-T1w'),
    #         # problematic case -- multiple identically named pepolar fieldmap runs
    #         # I guess we will just sacrifice ability to detect canceled runs here.
    #         # And we cannot just use _run+ since it would increment independently
    #         # for ap and then for pa.  We will rely on having ap preceding pa.
    #         # Added  _acq-mb8  so they match the one in funcs
    #         ('func_task-discorr_acq-ap', r'fmap-epi_dir-ap_acq-mb8_run+'),
    #         ('func_task-discorr_acq-pa', r'fmap-epi_dir-pa_acq-mb8_run='),
    # ]
}

# list containing StudyInstanceUID to skip -- hopefully doesn't happen too often
dicoms2skip: list[str] = [
    # e.g.
    # '1.3.12.2.1107.5.2.43.66112.30000016110117002435700000001',
]

DEFAULT_FIELDS = {
    # Let it just be in each json file extracted
    "Acknowledgements": "We thank Terry Sacket and the rest of the DBIC (Dartmouth Brain Imaging "
    "Center) personnel for assistance in data collection, and "
    "Yaroslav O. Halchenko for preparing BIDS dataset. "
    "TODO: adjust to your case.",
}

POPULATE_INTENDED_FOR_OPTS = {
    "matching_parameters": ["ImagingVolume", "Shims"],
    "criterion": "Closest",
}


KNOWN_DATATYPES = {"anat", "func", "dwi", "behav", "fmap"}


def _delete_chars(from_str: str, deletechars: str) -> str:
    return from_str.translate(str.maketrans("", "", deletechars))


def filter_dicom(dcmdata: dcm.dataset.Dataset) -> bool:
    """Return True if a DICOM dataset should be filtered out, else False"""
    return True if dcmdata.StudyInstanceUID in dicoms2skip else False


def filter_files(_fn: str) -> bool:
    """Return True if a file should be kept, else False.

    ATM reproin does not do any filtering. Override if you need to add some
    """
    return True


def create_key(
    subdir: Optional[str],
    file_suffix: str,
    outtype: tuple[str, ...] = ("nii.gz", "dicom"),
    annotation_classes: None = None,
    prefix: str = "",
) -> tuple[str, tuple[str, ...], None]:
    if not subdir:
        raise ValueError("subdir must be a valid format string")
    # may be even add "performing physician" if defined??
    template = os.path.join(
        prefix,
        "{bids_subject_session_dir}",
        subdir,
        "{bids_subject_session_prefix}_%s" % file_suffix,
    )
    return template, outtype, annotation_classes


def md5sum(string: Optional[str]) -> str:
    """Computes md5sum of a string"""
    if not string:
        return ""  # not None so None was not compared to strings
    m = hashlib.md5(string.encode())
    return m.hexdigest()


def get_study_description(seqinfo: list[SeqInfo]) -> str:
    # Centralized so we could fix/override
    v = get_unique(seqinfo, "study_description")
    assert isinstance(v, str)
    return v


def get_study_hash(seqinfo: list[SeqInfo]) -> str:
    # XXX: ad hoc hack
    return md5sum(get_study_description(seqinfo))


def fix_canceled_runs(seqinfo: list[SeqInfo]) -> list[SeqInfo]:
    """Function that adds cancelme_ to known bad runs which were forgotten"""
    if not fix_accession2run:
        return seqinfo  # nothing to do
    for i, curr_seqinfo in enumerate(seqinfo):
        accession_number = curr_seqinfo.accession_number
        if accession_number and accession_number in fix_accession2run:
            lgr.info(
                "Considering some runs possibly marked to be "
                "canceled for accession %s",
                accession_number,
            )
            # This code is reminiscent of prior logic when operating on
            # a single accession, but left as is for now
            badruns = fix_accession2run[accession_number]
            badruns_pattern = "|".join(badruns)
            if re.match(badruns_pattern, curr_seqinfo.series_id):
                lgr.info("Fixing bad run {0}".format(curr_seqinfo.series_id))
                fixedkwargs = dict()
                for key in series_spec_fields:
                    fixedkwargs[key] = "cancelme_" + getattr(curr_seqinfo, key)
                seqinfo[i] = curr_seqinfo._replace(**fixedkwargs)
    return seqinfo


def fix_dbic_protocol(seqinfo: list[SeqInfo]) -> list[SeqInfo]:
    """Ad-hoc fixup for existing protocols.

    It will operate in 3 stages on `protocols2fix` records.
    1. consider a record which has md5sum of study_description
    2. apply all substitutions, where key is a regular expression which
       successfully searches (not necessarily matches, so anchor appropriately)
       study_description
    3. apply "catch all" substitutions in the key containing an empty string

    3. is somewhat redundant since `re.compile('.*')` could match any, but is
    kept for simplicity of its specification.
    """

    study_hash = get_study_hash(seqinfo)
    study_description = get_study_description(seqinfo)

    # We will consider first study specific (based on hash)
    if study_hash in protocols2fix:
        _apply_substitutions(
            seqinfo, protocols2fix[study_hash], "study (%s) specific" % study_hash
        )
    # Then go through all regexps returning regex "search" result
    # on study_description
    for sub, substitutions in protocols2fix.items():
        if isinstance(sub, re.Pattern) and sub.search(study_description):
            _apply_substitutions(
                seqinfo, substitutions, "%r regex matching" % sub.pattern
            )
    # and at the end - global
    if "" in protocols2fix:
        _apply_substitutions(seqinfo, protocols2fix[""], "global")

    return seqinfo


def _apply_substitutions(
    seqinfo: list[SeqInfo], substitutions: list[tuple[str, str]], subs_scope: str
) -> None:
    lgr.info("Considering %s substitutions", subs_scope)
    for i, curr_seqinfo in enumerate(seqinfo):
        fixed_kwargs = dict()
        # need to replace both protocol_name series_description
        for key in series_spec_fields:
            oldvalue = value = getattr(curr_seqinfo, key)
            # replace all I need to replace
            for substring, replacement in substitutions:
                value = re.sub(substring, replacement, value)
            if oldvalue != value:
                lgr.info(" %s: %r -> %r", key, oldvalue, value)
            fixed_kwargs[key] = value
        # namedtuples are immutable
        seqinfo[i] = curr_seqinfo._replace(**fixed_kwargs)


def fix_seqinfo(seqinfo: list[SeqInfo]) -> list[SeqInfo]:
    """Just a helper on top of both fixers"""
    # add cancelme to known bad runs
    seqinfo = fix_canceled_runs(seqinfo)
    seqinfo = fix_dbic_protocol(seqinfo)
    return seqinfo


def ls(_study_session: StudySessionInfo, seqinfo: list[SeqInfo]) -> str:
    """Additional ls output for a seqinfo"""
    # assert len(sequences) <= 1  # expecting only a single study here
    # seqinfo = sequences.keys()[0]
    return " study hash: %s" % get_study_hash(seqinfo)


# XXX we killed session indicator!  what should we do now?!!!
# WE DON'T NEED IT -- it will be provided into conversion_info as `session`
# So we just need subdir and file_suffix!
@due.dcite(
    Doi("10.5281/zenodo.1207117"),
    path="heudiconv.heuristics.reproin",
    description="ReproIn heudiconv heuristic for turnkey conversion into BIDS",
)
def infotodict(
    seqinfo: list[SeqInfo],
) -> dict[tuple[str, tuple[str, ...], None], list[str]]:
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    session: scan index for longitudinal acq
    """
    seqinfo = fix_seqinfo(seqinfo)
    lgr.info("Processing %d seqinfo entries", len(seqinfo))

    info: dict[tuple[str, tuple[str, ...], None], list[str]] = {}
    skipped: list[str] = []
    skipped_unknown: list[str] = []
    current_run = 0
    run_label: Optional[str] = None  # run-
    dcm_image_iod_spec: Optional[str] = None
    skip_derived = False
    for curr_seqinfo in seqinfo:
        # XXX: skip derived sequences, we don't store them to avoid polluting
        # the directory, unless it is the motion corrected ones
        # (will get _rec-moco suffix)
        if skip_derived and curr_seqinfo.is_derived and not curr_seqinfo.is_motion_corrected:
            skipped.append(curr_seqinfo.series_id)
            lgr.debug("Ignoring derived data %s", curr_seqinfo.series_id)
            continue

        # possibly apply present formatting in the series_description or protocol name
        for f in "series_description", "protocol_name":
            curr_seqinfo = curr_seqinfo._replace(
                **{f: getattr(curr_seqinfo, f).format(**curr_seqinfo._asdict())}
            )

        template = None
        suffix = ""
        # seq = []

        # figure out type of image from curr_seqinfo.image_info -- just for checking ATM
        # since we primarily rely on encoded in the protocol name information
        prev_dcm_image_iod_spec = dcm_image_iod_spec
        if len(curr_seqinfo.image_type) > 2:
            # https://dicom.innolitics.com/ciods/cr-image/general-image/00080008
            # 0 - ORIGINAL/DERIVED
            # 1 - PRIMARY/SECONDARY
            # 3 - Image IOD specific specialization (optional)
            dcm_image_iod_spec = curr_seqinfo.image_type[2]
            image_type_datatype = {
                # Note: P and M are too generic to make a decision here, could be
                #  for different datatypes (bold, fmap, etc)
                "FMRI": "func",
                "MPR": "anat",
                "DIFFUSION": "dwi",
                "MIP_SAG": "anat",  # angiography
                "MIP_COR": "anat",  # angiography
                "MIP_TRA": "anat",  # angiography
            }.get(dcm_image_iod_spec, None)
        else:
            dcm_image_iod_spec = image_type_datatype = None

        series_info = {}  # For please lintian and its friends
        for sfield in series_spec_fields:
            svalue = getattr(curr_seqinfo, sfield)
            series_info = parse_series_spec(svalue)
            if series_info:  # looks like a valid spec - we are done
                series_spec = svalue
                break
            else:
                lgr.debug("Failed to parse reproin spec in .%s=%r", sfield, svalue)

        if not series_info:
            series_spec = None  # we cannot know better
            lgr.warning(
                "Could not determine the series name by looking at %s fields",
                ", ".join(series_spec_fields),
            )
            skipped_unknown.append(curr_seqinfo.series_id)
            continue

        if dcm_image_iod_spec and dcm_image_iod_spec.startswith("MIP"):
            series_info["acq"] = series_info.get("acq", "") + sanitize_str(
                dcm_image_iod_spec
            )

        datatype = series_info.pop("datatype")
        datatype_suffix = series_info.pop("datatype_suffix", None)

        if image_type_datatype and datatype != image_type_datatype:
            lgr.warning(
                "Deduced datatype to be %s from DICOM, but got %s out of %s",
                image_type_datatype,
                datatype,
                series_spec,
            )

        # if curr_seqinfo.is_derived:
        #     # Let's for now stash those close to original images
        #     # TODO: we might want a separate tree for all of this!?
        #     # so more of a parameter to the create_key
        #     #datatype += '/derivative'
        #     # just keep it lower case and without special characters
        #     # XXXX what for???
        #     #seq.append(curr_seqinfo.series_description.lower())
        #     prefix = os.path.join('derivatives', 'scanner')
        # else:
        #     prefix = ''
        prefix = ""

        #
        # Figure out the datatype_suffix (BIDS _suffix)
        #
        # If none was provided -- let's deduce it from the information we find:
        # analyze curr_seqinfo.protocol_name (series_id is based on it) for full name mapping etc
        if not datatype_suffix:
            if datatype == "func":
                if "_pace_" in series_spec:
                    datatype_suffix = "pace"  # or should it be part of seq-
                elif "P" in curr_seqinfo.image_type:
                    datatype_suffix = "phase"
                elif "M" in curr_seqinfo.image_type:
                    datatype_suffix = "bold"
                else:
                    # assume bold by default
                    datatype_suffix = "bold"
            elif datatype == "fmap":
                # TODO: support phase1 phase2 like in "Case 2: Two phase images ..."
                if not dcm_image_iod_spec:
                    raise ValueError("Do not know image data type yet to make decision")
                datatype_suffix = {
                    # might want explicit {file_index}  ?
                    # _epi for pepolar fieldmaps, see
                    # https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#case-4-multiple-phase-encoded-directions-pepolar
                    "M": "epi" if "dir" in series_info else "magnitude",
                    "P": "phasediff",
                    "DIFFUSION": "epi",  # according to KODI those DWI are the EPIs we need
                }[dcm_image_iod_spec]
            elif datatype == "dwi":
                # label for dwi as well
                datatype_suffix = "dwi"

        #
        # Even if datatype_suffix was provided, for some data we might need to override,
        # since they are complementary files produced along-side with original
        # ones.
        #
        if curr_seqinfo.series_description.endswith("_SBRef"):
            datatype_suffix = "sbref"

        if not datatype_suffix:
            # Might be provided by the bids ending within series_spec, we would
            # just want to check if that the last element is not _key-value pair
            bids_ending = series_info.get("bids", None)
            if not bids_ending or "-" in bids_ending.split("_")[-1]:
                lgr.warning(
                    "We ended up with an empty label/suffix for %r", series_spec
                )

        run = series_info.get("run")
        if run is not None:
            # so we have an indicator for a run
            if run == "+":
                # some sequences, e.g.  fmap, would generate two (or more?)
                # sequences -- e.g. one for magnitude(s) and other ones for
                # phases.  In those we must not increment run!
                if dcm_image_iod_spec and dcm_image_iod_spec == "P":
                    if prev_dcm_image_iod_spec != "M":
                        # XXX if we have a known earlier study, we need to always
                        # increase the run counter for phasediff because magnitudes
                        # were not acquired
                        if get_study_hash([curr_seqinfo]) == "9d148e2a05f782273f6343507733309d":
                            current_run += 1
                        else:
                            raise RuntimeError(
                                "Was expecting phase image to follow magnitude "
                                "image, but previous one was %r",
                                prev_dcm_image_iod_spec,
                            )
                        # else we do nothing special
                else:  # and otherwise we go to the next run
                    current_run += 1
            elif run == "=":
                if not current_run:
                    current_run = 1
            elif run.isdigit():
                current_run_ = int(run)
                if current_run_ < current_run:
                    lgr.warning(
                        "Previous run (%s) was larger than explicitly specified %s",
                        current_run,
                        current_run_,
                    )
                current_run = current_run_
            else:
                raise ValueError(
                    "Don't know how to deal with run specification %s" % repr(run)
                )
            run_label = "run-%02d" % current_run
        else:
            # if there is no _run -- no run label added
            run_label = None

        # yoh: had a wrong assumption
        # if curr_seqinfo.is_motion_corrected:
        #     assert curr_seqinfo.is_derived, "Motion corrected images must be 'derived'"

        if curr_seqinfo.is_motion_corrected and "rec-" in series_info.get("bids", ""):
            raise NotImplementedError(
                "want to add _rec-moco but there is _rec- already"
            )

        def from_series_info(name: str) -> Optional[str]:
            """A little helper to provide _name-value if series_info knows it

            Returns None otherwise
            """
            if series_info.get(name):  # noqa: B023
                return "%s-%s" % (name, series_info[name])  # noqa: B023
            else:
                return None

        # TODO: get order from schema, do not hardcode. ATM could be checked at
        # https://bids-specification.readthedocs.io/en/stable/99-appendices/04-entity-table.html
        # https://github.com/bids-standard/bids-specification/blob/HEAD/src/schema/rules/entities.yaml
        # ATM we at large rely on possible (re)ordering according to schema to be done
        # by heudiconv, not reproin here.
        filename_suffix_parts = [
            from_series_info("task"),
            from_series_info("acq"),
            # But we want to add an indicator in case it was motion corrected
            # in the magnet. ref sample  /2017/01/03/qa
            None if not curr_seqinfo.is_motion_corrected else "rec-moco",
            from_series_info("dir"),
            series_info.get("bids"),
            run_label,
            datatype_suffix,
        ]
        # filter those which are None, and join with _
        suffix = "_".join(filter(bool, filename_suffix_parts))  # type: ignore[arg-type]

        # # .series_description in case of
        # sdesc = curr_seqinfo.study_description
        # # temporary aliases for those phantoms which we already collected
        # # so we rename them into this
        # #MAPPING
        #
        # # the idea ias to have sequence names in the format like
        # # bids_<subdir>_bidsrecord
        # # in bids record we could have  _run[+=]
        # #  which would say to either increment run number from already encountered
        # #  or reuse the last one
        # if seq:
        #     suffix += 'seq-%s' % ('+'.join(seq))

        # For scouts -- we want only dicoms
        # https://github.com/nipy/heudiconv/issues/145
        outtype: tuple[str, ...]
        if (
            "_Scout" in curr_seqinfo.series_description
            or (
                datatype == "anat"
                and datatype_suffix
                and datatype_suffix.startswith("scout")
            )
            or (
                curr_seqinfo.series_description.lower()
                == curr_seqinfo.protocol_name.lower() + "_setter"
            )
        ):
            outtype = ("dicom",)
        else:
            outtype = ("nii.gz", "dicom")

        template = create_key(datatype, suffix, prefix=prefix, outtype=outtype)
        # we wanted ordered dict for consistent demarcation of dups
        if template not in info:
            info[template] = []
        info[template].append(curr_seqinfo.series_id)

    if skipped:
        lgr.info("Skipped %d sequences: %s" % (len(skipped), skipped))
    if skipped_unknown:
        lgr.warning(
            "Could not figure out where to stick %d sequences: %s"
            % (len(skipped_unknown), skipped_unknown)
        )

    info = get_dups_marked(info)  # mark duplicate ones with __dup-0x suffix
    return info


def get_dups_marked(
    info: dict[tuple[str, tuple[str, ...], None], list[T]], per_series: bool = True
) -> dict[tuple[str, tuple[str, ...], None], list[T]]:
    """

    Parameters
    ----------
    info
    per_series: bool
      If set to False, it would create growing index through all series. That
      could lead to non-desired effects if some "multi file" scans (such as
      fmap with magnitude{1,2} and phasediff) would not be able to associate
      multiple files for the same acquisition.   By default (True) dup indices
      would be per each series (change introduced in 0.5.2)

    Returns
    -------

    """
    # analyze for "cancelled" runs, if run number was explicitly specified and
    # thus we ended up with multiple entries which would mean that older ones
    #  were "cancelled"
    info = info.copy()
    dup_id = 0
    for template, series_ids in list(info.items()):
        if len(series_ids) > 1:
            lgr.warning(
                "Detected %d duplicated run(s) for template %s: %s",
                len(series_ids) - 1,
                template[0],
                series_ids[:-1],
            )
            # copy the duplicate ones into separate ones
            if per_series:
                dup_id = 0  # reset since declared per series
            for dup_series_id in series_ids[:-1]:
                dup_id += 1
                dup_template = ("%s__dup-%02d" % (template[0], dup_id),) + template[1:]
                # There must have not been such a beast before!
                if dup_template in info:
                    raise AssertionError(
                        "{} is already known to info={}. "
                        "May be a bug for per_series=True handling?"
                        "".format(dup_template, info)
                    )
                info[dup_template] = [dup_series_id]
            info[template] = series_ids[-1:]
        assert len(info[template]) == 1
    return info


def get_unique(seqinfos: list[SeqInfo], attr: str) -> Any:
    """Given a list of seqinfos, which must have come from a single study,
    get specific attr, which must be unique across all of the entries

    If not -- fail!

    """
    values = set(getattr(si, attr) for si in seqinfos)
    if len(values) != 1:
        raise AssertionError(
            f"Was expecting a single value for attribute {attr!r} "
            f"but got: {', '.join(sorted(values))}"
        )
    return values.pop()


# TODO: might need to do grouping per each session and return here multiple
# hits, or may be we could just somehow demarkate that it will be multisession
# one and so then later value parsed (again) in infotodict would be used???
def infotoids(seqinfos: Iterable[SeqInfo], outdir: str) -> dict[str, Optional[str]]:
    seqinfo_lst = list(seqinfos)
    # decide on subjid and session based on patient_id
    lgr.info("Processing sequence infos to deduce study/session")
    study_description = get_study_description(seqinfo_lst)
    study_description_hash = md5sum(study_description)
    subject = fixup_subjectid(get_unique(seqinfo_lst, "patient_id"))
    # TODO:  fix up subject id if missing some 0s
    if study_description:
        # Generally it is a ^ but if entered manually, ppl place space in it
        split = re.split("[ ^]", study_description, maxsplit=1)
        # split first one even more, since could be PI_Student or PI-Student
        split = re.split("[-_]", split[0], maxsplit=1) + split[1:]

        # locator = study_description.replace('^', '/')
        locator = "/".join(split)
    else:
        locator = "unknown"

    # TODO: actually check if given study is study we would care about
    # and if not -- we should throw some ???? exception

    # So -- use `outdir` and locator etc to see if for a given locator/subject
    # and possible ses+ in the sequence names, so we would provide a sequence
    # So might need to go through  parse_series_spec(curr_seqinfo.protocol_name)
    # to figure out presence of sessions.
    ses_markers: list[str] = []

    # there might be fixups needed so we could deduce session etc
    # this copy is not replacing original one, so the same fix_seqinfo
    # might be called later
    seqinfo_lst = fix_seqinfo(seqinfo_lst)
    for s in seqinfo_lst:
        if s.is_derived:
            continue
        session_ = parse_series_spec(s.protocol_name).get("session", None)
        if session_ and "{" in session_:
            # there was a marker for something we could provide from our seqinfo
            # e.g. {date}
            session_ = session_.format(**s._asdict())
        if session_:
            ses_markers.append(session_)
    session: Optional[str] = None
    if ses_markers:
        # we have a session or possibly more than one even
        # let's figure out which case we have
        nonsign_vals = set(ses_markers).difference("+=")
        # although we might want an explicit '=' to note the same session as
        # mentioned before?
        if len(nonsign_vals) > 1:
            lgr.warning(  # raise NotImplementedError(
                "Cannot deal with multiple sessions in the same study yet!"
                " We will process until the end of the first session"
            )
        if nonsign_vals:
            # get only unique values
            ses_markers = list(set(ses_markers))
            if set(ses_markers).intersection("+="):
                raise NotImplementedError(
                    "Should not mix hardcoded session markers with incremental ones (+=)"
                )
            if not len(ses_markers) == 1:
                raise NotImplementedError(
                    "Should have got a single session marker.  Got following: %s"
                    % ", ".join(map(repr, ses_markers))
                )
            session = ses_markers[0]
        else:
            # TODO - I think we are doomed to go through the sequence and split
            # ... actually the same as with nonsign_vals, we just would need to figure
            # out initial one if sign ones, and should make use of knowing
            # outdir
            # raise NotImplementedError()
            # we need to look at what sessions we already have
            sessions_dir = os.path.join(outdir, locator, "sub-" + subject)
            prior_sessions = sorted(glob(os.path.join(sessions_dir, "ses-*")))
            # TODO: more complicated logic
            # For now just increment session if + and keep the same number if =
            # and otherwise just give it 001
            # Note: this disables our safety blanket which would refuse to process
            # what was already processed before since it would try to override,
            # BUT there is no other way besides only if heudiconv was storing
            # its info based on some UID
            if ses_markers == ["+"]:
                session = "%03d" % (len(prior_sessions) + 1)
            elif ses_markers == ["="]:
                session = (
                    os.path.basename(prior_sessions[-1])[4:]
                    if prior_sessions
                    else "001"
                )
            else:
                session = "001"

    if study_description_hash == "9d148e2a05f782273f6343507733309d":
        session = "siemens1"
        lgr.info("Imposing session {0}".format(session))

    return {
        # TODO: request info on study from the JedCap
        "locator": locator,
        # Sessions to be deduced yet from the names etc TODO
        "session": session,
        "subject": subject,
    }


def sanitize_str(value: str) -> str:
    """Remove illegal characters for BIDS from task/acq/etc.."""
    return _delete_chars(value, "#!@$%^&.,:;_-")


def parse_series_spec(series_spec: str) -> dict[str, str]:
    """Parse protocol name according to our convention with minimal set of fixups"""
    # Since Yarik didn't know better place to put it in, but could migrate outside
    # at some point. TODO
    series_spec = series_spec.replace("anat_T1w", "anat-T1w")
    series_spec = series_spec.replace("hardi_64", "dwi_acq-hardi64")
    series_spec = series_spec.replace("AAHead_Scout", "anat-scout")

    # Parse the name according to our convention/specification

    # leading or trailing spaces do not matter
    series_spec = series_spec.strip(" ")

    # Strip off leading CAPITALS: prefix to accommodate some reported usecases:
    # https://github.com/ReproNim/reproin/issues/14
    # where PU: prefix is added by the scanner
    series_spec = re.sub("^[A-Z]*:", "", series_spec)
    series_spec = re.sub("^WIP ", "", series_spec)  # remove Philips WIP prefix

    # Remove possible suffix we don't care about after __
    series_spec = series_spec.split("__", 1)[0]

    bids = False  # we don't know yet for sure
    # We need to figure out if it is a valid bids
    split = series_spec.split("_")
    prefix = split[0]

    # Fixups
    if prefix == "scout":
        prefix = split[0] = "anat-scout"

    if prefix != "bids" and "-" in prefix:
        prefix, _ = prefix.split("-", 1)
    if prefix == "bids":
        bids = True  # for sure
        split = split[1:]

    def split2(s: str) -> tuple[str, Optional[str]]:
        # split on - if present, if not -- 2nd one returned None
        if "-" in s:
            a, _, b = s.partition("-")
            return a, b
        return s, None

    # Let's analyze first element which should tell us sequence type
    datatype, datatype_suffix = split2(split[0])
    if datatype not in KNOWN_DATATYPES:
        # It is not something we don't consume
        if bids:
            lgr.warning(
                "It was instructed to be BIDS datatype but unknown "
                "%s found. Known are: %s",
                datatype,
                ", ".join(KNOWN_DATATYPES),
            )
        return {}

    regd = dict(datatype=datatype)
    if datatype_suffix:
        regd["datatype_suffix"] = datatype_suffix
    # now go through each to see if one which we care
    bids_leftovers = []
    for s in split[1:]:
        key, value = split2(s)
        if value is None and key[-1] in "+=":
            value = key[-1]
            key = key[:-1]

        # sanitize values, which must not have _ and - is undesirable ATM as well
        # TODO: BIDSv2.0 -- allows "-" so replace with it instead
        value = (
            str(value)
            .replace("_", "X")
            .replace("-", "X")
            .replace("(", "{")
            .replace(")", "}")
        )  # for Philips

        if key in ["ses", "run", "task", "acq", "dir"]:
            # those we care about explicitly
            regd[{"ses": "session"}.get(key, key)] = sanitize_str(value)
        else:
            bids_leftovers.append(s)

    if bids_leftovers:
        regd["bids"] = "_".join(bids_leftovers)

    # TODO: might want to check for all known "standard" BIDS suffixes here
    # among bids_leftovers, thus serve some kind of BIDS validator

    # if not regd.get('datatype_suffix', None):
    #     # might need to assign a default label for each datatype if was not
    #     # given
    #     regd['datatype_suffix'] = {
    #         'func': 'bold'
    #     }.get(regd['datatype'], None)

    return regd


def fixup_subjectid(subjectid: str) -> str:
    """Just in case someone managed to miss a zero or added an extra one"""
    # make it lowercase
    subjectid = subjectid.lower()
    reg = re.match(r"sid0*(\d+)$", subjectid)
    if not reg:
        # some completely other pattern
        # just filter out possible _- in it
        return re.sub("[-_]", "", subjectid)
    return "sid%06d" % int(reg.groups()[0])
