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

  [PREFIX:]<seqtype[-label]>[_ses-<SESID>][_task-<TASKID>][_acq-<ACQLABEL>][_run-<RUNID>][_dir-<DIR>][<more BIDS>][__<custom>]

where
 [PREFIX:] - leading capital letters followed by : are stripped/ignored
 <...> - value to be entered
 [...] - optional -- might be nearly mandatory for some modalities (e.g.,
         run for functional) and very optional for others
 *ID - alpha-numerical identifier (e.g. 01,02, pre, post, pre01) for a run,
       task, session. Note that makes more sense to use numerical values for
       RUNID (e.g., _run-01, _run-02) for obvious sorting and possibly
       descriptive ones for e.g. SESID (_ses-movie, _ses-localizer)


<seqtype[-label]>
   a known BIDS sequence type which is usually a name of the folder under
   subject's directory. And (optional) label is specific per sequence type
   (e.g. typical "bold" for func, or "T1w" for "anat"), which could often
   (but not always) be deduced from DICOM. Known to BIDS modalities are:

     anat - anatomical data.  Might also be collected multiple times across
            runs (e.g. if subject is taken out of magnet etc), so could
            (optionally) have "_run" definition attached. For "standard anat"
            labels, please consult to "8.3 Anatomy imaging data" but most
            common are 'T1w', 'T2w', 'angio'
     func - functional (AKA task, including resting state) data.
            Typically contains multiple runs, and might have multiple different
            tasks different per each run
            (e.g. _task-memory_run-01, _task-oddball_run-02)
     fmap - field maps
     dwi  - diffusion weighted imaging (also can as well have runs)

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
"""

import os
import re
from collections import OrderedDict
import hashlib
from glob import glob

import logging
lgr = logging.getLogger('heudiconv')

# Terminology to hamornise and use to name variables etc
# experiment
#  subject
#   [session]
#    exam (AKA scanning session) - currently seqinfo, unless brought together from multiple
#     series  (AKA protocol?)
#      - series_spec - deduced from fields the spec (literal value)
#      - series_info - the dictionary with fields parsed from series_spec

# Which fields in seqinfo (in this order) to check for the ReproIn spec
series_spec_fields = ('protocol_name', 'series_description')

# dictionary from accession-number to runs that need to be marked as bad
# NOTE: even if filename has number that is 0-padded, internally no padding
# is done
fix_accession2run = {
    'A000005': ['^1-'],
    'A000035': ['^8-', '^9-'],
    'A000067': ['^9-'],
    'A000072': ['^5-'],
    'A000081': ['^5-'],
    'A000082': ['^5-'],
    'A000088': ['^9-'],
    'A000090': ['^5-'],
    'A000127': ['^21-'],
    'A000130': ['^15-'],
    'A000137': ['^9-', '^11-'],
    'A000297': ['^12-'],
    'A000326': ['^15-'],
    'A000376': ['^15-'],
    'A000384': ['^8-', '^11-'],
    'A000467': ['^15-'],
    'A000490': ['^15-'],
    'A000511': ['^15-'],
    'A000797': ['^[1-7]-'],
}

# dictionary containing fixes, keys are md5sum of study_description from
# dicoms, in the form of PI-Experimenter^protocolname
# values are list of tuples in the form (regex_pattern, substitution)
protocols2fix = {
    # QA
    '43b67d9139e8c7274578b7451ab21123':
        [
         #('anat-scout.*', 'anat-scout_ses-{date}'),
         # do not change it so we retain _ses-{date}
         #('anat-scout.*', 'anat-scout'),
         ('BOLD_p2_s4_3\.5mm', 'func_task-rest_acq-p2-s4-3.5mm'),
         ('BOLD_p2_s4',        'func_task-rest_acq-p2-s4'),
         ('BOLD_p2_noprescannormalize', 'func-bold_task-rest_acq-p2noprescannormalize'),
         ('BOLD_p2',                    'func-bold_task-rest_acq-p2'),
         ('BOLD_', 'func_task-rest'),
         ('DTI_30_p2_s4_3\.5mm', 'dwi_acq-DTI-30-p2-s4-3.5mm'),
         ('DTI_30_p2_s4',        'dwi_acq-DTI-30-p2-s4'),
         ('DTI_30_p2',           'dwi_acq-DTI-30-p2'),
         ('_p2_s4_3\.5mm', '_acq-p2-s4-3.5mm'),
         ('_p2_s4',        '_acq-p2-s4'),
         ('_p2', '_acq-p2'),
        ],
    '9d148e2a05f782273f6343507733309d':
        [('anat_', 'anat-'),
         ('run-life[0-9]', 'run+_task-life'),
         ('scout_run\+', 'scout'),
         ('T2w', 'T2w_run+'),
         # substitutions for old protocol names
         ('AAHead_Scout_32ch-head-coil', 'anat-scout'),
         ('MPRAGE', 'anat-T1w_acq-MPRAGE_run+'),
         ('gre_field_mapping_2mm', 'fmap_run+_acq-2mm'),
         ('gre_field_mapping_3mm', 'fmap_run+_acq-3mm'),
         ('epi_bold_sms_p2_s4_2mm_life1_748',
            'func_run+_task-life_acq-2mm748'),
         ('epi_bold_sms_p2_s4_2mm_life2_692',
            'func_run+_task-life_acq-2mm692'),
         ('epi_bold_sms_p2_s4_2mm_life3_754',
            'func_run+_task-life_acq-2mm754'),
         ('epi_bold_sms_p2_s4_2mm_life4_824',
            'func_run+_task-life_acq-2mm824'),
         ('epi_bold_p2_3mm_nofs_life1_374',
            'func_run+_task-life_acq-3mmnofs374'),
         ('epi_bold_p2_3mm_nofs_life2_346',
          'func_run+_task-life_acq-3mmnofs346'),
         ('epi_bold_p2_3mm_nofs_life3_377',
          'func_run+_task-life_acq-3mmnofs377'),
         ('epi_bold_p2_3mm_nofs_life4_412',
          'func_run+_task-life_acq-3mmnofs412'),
         ('t2_space_sag_p4_iso', 'anat-T2w_run+'),
         ('gre_field_mapping_2.4mm', 'fmap_run+_acq-2.4mm'),
         ('rest_p2_sms4_2.4mm_64sl_1000tr_32te_600dyn',
            'func_run+_task-rest_acq-2.4mm64sl1000tr32te600dyn'),
         ('DTI_30', 'dwi_run+_acq-30'),
         ('t1_space_sag_p2_iso', 'anat-T1w_acq-060mm_run+')],
    '76b36c80231b0afaf509e2d52046e964':
        [('fmap_run\+_2mm', 'fmap_run+_acq-2mm')],
    'c6d8fbccc72990bee61d28e73b2618a4':
        [('run=', 'run+')],
    'a751cc977f1e354fcafcb0ea2de123bd':
        [
          ('_unlabeled', '_task-unlabeled'),
          ('_mSense', '_acq-mSense'),
          ('_p1_sms4_2.5mm', '_acq-p1-sms4-2.5mm'),
          ('_p1_sms4_3mm', '_acq-p1-sms4-3mm'),
        ],
    'd160113cf5ea8c5d0cbbbe14ef625e76':
        [
          ('_run0', '_run-0'),
        ],
    '1bd62e10672fe0b435a9aa8d75b45425':
        [
            # need to add incrementing session -- study should have 2
            # and no need for run+ for the scout!
            ('scout(_run\+)?$', 'scout_ses+'),
        ],
    'da218a66de902adb3ad9407d514e3639':
        [
            # those sequences renamed later to include DTI- in their acq-
            # so fot consistency
            ('hardi_64',  'dwi_acq-DTI-hardi64'),
            ('acq-hardi', 'acq-DTI-hardi'),
        ],
    'ed20c1ad4a0861b2b65768e159258eec':
        [
            ('fmap_acq-discorr-dti-', 'fmap_acq-dwi_dir-'),
            ('_test', ''),
        ],
}

# list containing StudyInstanceUID to skip -- hopefully doesn't happen too often
dicoms2skip = [
    '1.3.12.2.1107.5.2.43.66112.30000016110117002435700000001',
    '1.3.12.2.1107.5.2.43.66112.30000016102813152550600000004',  # double scout
]

DEFAULT_FIELDS = {
    # Let it just be in each json file extracted
    #'Manufacturer': "Siemens",
    #'ManufacturersModelName': "Prisma",
    "Acknowledgements":
        "We thank Terry Sacket and the rest of the DBIC (Dartmouth Brain Imaging "
        "Center) personnel for assistance in data collection, and "
        "Yaroslav Halchenko and Matteo Visconti for preparing BIDS dataset. "
        "TODO: more",
}


def _delete_chars(from_str, deletechars):
    """ Delete characters from string allowing for Python 2 / 3 difference
    """
    try:
        return from_str.translate(None, deletechars)
    except TypeError:
        return from_str.translate(str.maketrans('', '', deletechars))


def filter_dicom(dcmdata):
    """Return True if a DICOM dataset should be filtered out, else False"""
    return True if dcmdata.StudyInstanceUID in dicoms2skip else False


def filter_files(fn):
    """Return True if a file should be kept, else False.
    We're using it to filter out files that do not start with a number."""

    # do not check for these accession numbers because they haven't been
    # recopied with the initial number
    donotfilter = ['A000012', 'A000013', 'A000020', 'A000041']

    split = os.path.split(fn)
    split2 = os.path.split(split[0])
    sequence_dir = split2[1]
    split3 = os.path.split(split2[0])
    accession_number = split3[1]
    return True
    if accession_number == 'A000043':
        # crazy one that got copied for some runs but not for others,
        # so we are going to discard those that got copied and let heudiconv
        # figure out the rest
        return False if re.match('^[0-9]+-', sequence_dir) else True
    elif accession_number == 'unknown':
        # this one had some stuff without study description, filter stuff before
        # collecting info, so it doesn't crash completely
        return False if re.match('^[34][07-9]-sn', sequence_dir) else True
    elif accession_number in donotfilter:
        return True
    elif accession_number.startswith('phantom-'):
        # Accessions on phantoms, e.g. in dartmouth-phantoms/bids_test4-20161014
        return True
    elif accession_number.startswith('heudiconvdcm'):
        # we were given some tarball with dicoms which was extracted so we
        # better obey
        return True
    else:
        return True if re.match('^[0-9]+-', sequence_dir) else False


def create_key(subdir, file_suffix, outtype=('nii.gz', 'dicom'),
               annotation_classes=None, prefix=''):
    if not subdir:
        raise ValueError('subdir must be a valid format string')
    # may be even add "performing physician" if defined??
    template = os.path.join(
        prefix,
        "{bids_subject_session_dir}",
        subdir,
        "{bids_subject_session_prefix}_%s" % file_suffix
    )
    return template, outtype, annotation_classes


def md5sum(string):
    """Computes md5sum of as string"""
    if not string:
        return ""  # not None so None was not compared to strings
    m = hashlib.md5(string.encode())
    return m.hexdigest()

def get_study_description(seqinfo):
    # Centralized so we could fix/override
    v = get_unique(seqinfo, 'study_description')
    return v

def get_study_hash(seqinfo):
    # XXX: ad hoc hack
    return md5sum(get_study_description(seqinfo))


def fix_canceled_runs(seqinfo, accession2run=fix_accession2run):
    """Function that adds cancelme_ to known bad runs which were forgotten
    """
    accession_number = get_unique(seqinfo, 'accession_number')
    if accession_number in accession2run:
        lgr.info("Considering some runs possibly marked to be "
                 "canceled for accession %s", accession_number)
        badruns = accession2run[accession_number]
        badruns_pattern = '|'.join(badruns)
        for i, s in enumerate(seqinfo):
            if re.match(badruns_pattern, s.series_id):
                lgr.info('Fixing bad run {0}'.format(s.series_id))
                fixedkwargs = dict()
                for key in series_spec_fields:
                    fixedkwargs[key] = 'cancelme_' + getattr(s, key)
                seqinfo[i] = s._replace(**fixedkwargs)
    return seqinfo


def fix_dbic_protocol(seqinfo, keys=series_spec_fields, subsdict=protocols2fix):
    """Ad-hoc fixup for existing protocols
    """
    study_hash = get_study_hash(seqinfo)

    if study_hash not in subsdict:
        raise ValueError("I don't know how to fix {0}".format(study_hash))

    # need to replace both protocol_name series_description
    substitutions = subsdict[study_hash]
    for i, s in enumerate(seqinfo):
        fixed_kwargs = dict()
        for key in keys:
            value = getattr(s, key)
            # replace all I need to replace
            for substring, replacement in substitutions:
                value = re.sub(substring, replacement, value)
            fixed_kwargs[key] = value
        # namedtuples are immutable
        seqinfo[i] = s._replace(**fixed_kwargs)

    return seqinfo


def fix_seqinfo(seqinfo):
    """Just a helper on top of both fixers
    """
    # add cancelme to known bad runs
    seqinfo = fix_canceled_runs(seqinfo)
    study_hash = get_study_hash(seqinfo)
    if study_hash in protocols2fix:
        lgr.info("Fixing up protocol for {0}".format(study_hash))
        seqinfo = fix_dbic_protocol(seqinfo)
    return seqinfo


def ls(study_session, seqinfo):
    """Additional ls output for a seqinfo"""
    #assert len(sequences) <= 1  # expecting only a single study here
    #seqinfo = sequences.keys()[0]
    return ' study hash: %s' % get_study_hash(seqinfo)


# XXX we killed session indicator!  what should we do now?!!!
# WE DON:T NEED IT -- it will be provided into conversion_info as `session`
# So we just need subdir and file_suffix!
def infotodict(seqinfo):
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
    and_dicom = ('dicom', 'nii.gz')

    info = OrderedDict()
    skipped, skipped_unknown = [], []
    current_run = 0
    run_label = None   # run-
    dcm_image_iod_spec = None
    skip_derived = False
    for s in seqinfo:
        # XXX: skip derived sequences, we don't store them to avoid polluting
        # the directory, unless it is the motion corrected ones
        # (will get _rec-moco suffix)
        if skip_derived and s.is_derived and not s.is_motion_corrected:
            skipped.append(s.series_id)
            lgr.debug("Ignoring derived data %s", s.series_id)
            continue

        # possibly apply present formatting in the series_description or protocol name
        for f in 'series_description', 'protocol_name':
            s = s._replace(**{f: getattr(s, f).format(**s._asdict())})

        template = None
        suffix = ''
        seq = []

        # figure out type of image from s.image_info -- just for checking ATM
        # since we primarily rely on encoded in the protocol name information
        prev_dcm_image_iod_spec = dcm_image_iod_spec
        if len(s.image_type) > 2:
            # https://dicom.innolitics.com/ciods/cr-image/general-image/00080008
            # 0 - ORIGINAL/DERIVED
            # 1 - PRIMARY/SECONDARY
            # 3 - Image IOD specific specialization (optional)
            dcm_image_iod_spec = s.image_type[2]
            image_type_seqtype = {
                'P': 'fmap',   # phase
                'FMRI': 'func',
                'MPR': 'anat',
                # 'M': 'func',  "magnitude"  -- can be for scout, anat, bold, fmap
                'DIFFUSION': 'dwi',
                'MIP_SAG': 'anat',  # angiography
                'MIP_COR': 'anat',  # angiography
                'MIP_TRA': 'anat',  # angiography
            }.get(dcm_image_iod_spec, None)
        else:
            dcm_image_iod_spec = image_type_seqtype = None

        series_info = {}  # For please lintian and its friends
        for sfield in series_spec_fields:
            svalue = getattr(s, sfield)
            series_info = parse_series_spec(svalue)
            if series_info:  # looks like a valid spec - we are done
                series_spec = svalue
                break
            else:
                lgr.debug(
                    "Failed to parse reproin spec in .%s=%r",
                    sfield, svalue)

        if not series_info:
            series_spec = None  # we cannot know better
            lgr.warning(
                "Could not determine the series name by looking at "
                "%s fields", ', '.join(series_spec_fields))
            skipped_unknown.append(s.series_id)
            continue

        if dcm_image_iod_spec and dcm_image_iod_spec.startswith('MIP'):
            series_info['acq'] = series_info.get('acq', '') + sanitize_str(dcm_image_iod_spec)

        seqtype = series_info.pop('seqtype')
        seqtype_label = series_info.pop('seqtype_label', None)

        if image_type_seqtype and seqtype != image_type_seqtype:
            lgr.warning(
                "Deduced seqtype to be %s from DICOM, but got %s out of %s",
                image_type_seqtype, seqtype, series_spec)

        # if s.is_derived:
        #     # Let's for now stash those close to original images
        #     # TODO: we might want a separate tree for all of this!?
        #     # so more of a parameter to the create_key
        #     #seqtype += '/derivative'
        #     # just keep it lower case and without special characters
        #     # XXXX what for???
        #     #seq.append(s.series_description.lower())
        #     prefix = os.path.join('derivatives', 'scanner')
        # else:
        #     prefix = ''
        prefix = ''

        # analyze s.protocol_name (series_id is based on it) for full name mapping etc
        if seqtype == 'func' and not seqtype_label:
            if '_pace_' in series_spec:
                seqtype_label = 'pace'  # or should it be part of seq-
            else:
                # assume bold by default
                seqtype_label = 'bold'

        if seqtype == 'fmap' and not seqtype_label:
            if not dcm_image_iod_spec:
                raise ValueError("Do not know image data type yet to make decision")
            seqtype_label = {
                'M': 'magnitude',  # might want explicit {file_index}  ?
                'P': 'phasediff',
                'DIFFUSION': 'epi', # according to KODI those DWI are the EPIs we need
            }[dcm_image_iod_spec]

        # label for dwi as well
        if seqtype == 'dwi' and not seqtype_label:
            seqtype_label = 'dwi'

        run = series_info.get('run')
        if run is not None:
            # so we have an indicator for a run
            if run == '+':
                # some sequences, e.g.  fmap, would generate two (or more?)
                # sequences -- e.g. one for magnitude(s) and other ones for
                # phases.  In those we must not increment run!
                if dcm_image_iod_spec and dcm_image_iod_spec == 'P':
                    if prev_dcm_image_iod_spec != 'M':
                        # XXX if we have a known earlier study, we need to always
                        # increase the run counter for phasediff because magnitudes
                        # were not acquired
                        if get_study_hash([s]) == '9d148e2a05f782273f6343507733309d':
                            current_run += 1
                        else:
                            raise RuntimeError(
                                "Was expecting phase image to follow magnitude "
                                "image, but previous one was %r", prev_dcm_image_iod_spec)
                        # else we do nothing special
                else:  # and otherwise we go to the next run
                    current_run += 1
            elif run == '=':
                if not current_run:
                    current_run = 1
            elif run.isdigit():
                current_run_ = int(run)
                if current_run_ < current_run:
                    lgr.warning(
                        "Previous run (%s) was larger than explicitly specified %s",
                        current_run, current_run_)
                current_run = current_run_
            else:
                raise ValueError(
                    "Don't know how to deal with run specification %s" % repr(run))
            if isinstance(current_run, str) and current_run.isdigit():
                current_run = int(current_run)
            run_label = "run-" + ("%02d" % current_run
                                  if isinstance(current_run, int)
                                  else current_run)
        else:
            # if there is no _run -- no run label addded
            run_label = None

        # yoh: had a wrong assumption
        # if s.is_motion_corrected:
        #     assert s.is_derived, "Motion corrected images must be 'derived'"

        if s.is_motion_corrected and 'rec-' in series_info.get('bids', ''):
            raise NotImplementedError("want to add _acq-moco but there is _acq- already")

        suffix_parts = [
            None if not series_info.get('task') else "task-%s" % series_info['task'],
            None if not series_info.get('acq') else "acq-%s" % series_info['acq'],
            # But we want to add an indicator in case it was motion corrected
            # in the magnet. ref sample  /2017/01/03/qa
            None if not s.is_motion_corrected else 'rec-moco',
            series_info.get('bids'),
            run_label,
            seqtype_label,
        ]
        # filter tose which are None, and join with _
        suffix = '_'.join(filter(bool, suffix_parts))

        # # .series_description in case of
        # sdesc = s.study_description
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
        if "_Scout" in s.series_description or \
                (seqtype == 'anat' and seqtype_label and seqtype_label.startswith('scout')):
            outtype = ('dicom',)
        else:
            outtype = ('nii.gz', 'dicom')

        template = create_key(seqtype, suffix, prefix=prefix, outtype=outtype)
        # we wanted ordered dict for consistent demarcation of dups
        if template not in info:
            info[template] = []
        info[template].append(s.series_id)

    if skipped:
        lgr.info("Skipped %d sequences: %s" % (len(skipped), skipped))
    if skipped_unknown:
        lgr.warning("Could not figure out where to stick %d sequences: %s" %
                    (len(skipped_unknown), skipped_unknown))

    info = get_dups_marked(info)  # mark duplicate ones with __dup-0x suffix

    info = dict(info)  # convert to dict since outside functionality depends on it being a basic dict
    return info


def get_dups_marked(info):
    # analyze for "cancelled" runs, if run number was explicitly specified and
    # thus we ended up with multiple entries which would mean that older ones
    #  were "cancelled"
    info = info.copy()
    dup_id = 0
    for template, series_ids in list(info.items()):
        if len(series_ids) > 1:
            lgr.warning("Detected %d duplicated run(s) for template %s: %s",
                        len(series_ids) - 1, template[0], series_ids[:-1])
            # copy the duplicate ones into separate ones
            for dup_series_id in series_ids[:-1]:
                dup_id += 1
                dup_template = (
                    '%s__dup-%02d' % (template[0], dup_id),
                    ) + template[1:]
                # There must have not been such a beast before!
                assert dup_template not in info
                info[dup_template] = [dup_series_id]
            info[template] = series_ids[-1:]
        assert len(info[template]) == 1
    return info


def get_unique(seqinfos, attr):
    """Given a list of seqinfos, which must have come from a single study
    get specific attr, which must be unique across all of the entries

    If not -- fail!

    """
    values = set(getattr(si, attr) for si in seqinfos)
    assert (len(values) == 1)
    return values.pop()


# TODO: might need to do groupping per each session and return here multiple
# hits, or may be we could just somehow demarkate that it will be multisession
# one and so then later value parsed (again) in infotodict  would be used???
def infotoids(seqinfos, outdir):
    # decide on subjid and session based on patient_id
    lgr.info("Processing sequence infos to deduce study/session")
    study_description = get_study_description(seqinfos)
    study_description_hash = md5sum(study_description)
    subject = fixup_subjectid(get_unique(seqinfos, 'patient_id'))
    # TODO:  fix up subject id if missing some 0s
    if study_description:
        split = study_description.split('^', 1)
        # split first one even more, since couldbe PI_Student or PI-Student
        split = re.split('-|_', split[0], 1) + split[1:]

        # locator = study_description.replace('^', '/')
        locator = '/'.join(split)
    else:
        locator = 'unknown'

    # TODO: actually check if given study is study we would care about
    # and if not -- we should throw some ???? exception

    # So -- use `outdir` and locator etc to see if for a given locator/subject
    # and possible ses+ in the sequence names, so we would provide a sequence
    # So might need to go through  parse_series_spec(s.protocol_name)
    # to figure out presence of sessions.
    ses_markers = []

    # there might be fixups needed so we could deduce session etc
    # this copy is not replacing original one, so the same fix_seqinfo
    # might be called later
    seqinfos = fix_seqinfo(seqinfos)
    for s in seqinfos:
        if s.is_derived:
            continue
        session_ = parse_series_spec(s.protocol_name).get('session', None)
        if session_ and '{' in session_:
            # there was a marker for something we could provide from our seqinfo
            # e.g. {date}
            session_ = session_.format(**s._asdict())
        ses_markers.append(session_)
    ses_markers = list(filter(bool, ses_markers))  # only present ones
    session = None
    if ses_markers:
        # we have a session or possibly more than one even
        # let's figure out which case we have
        nonsign_vals = set(ses_markers).difference('+=')
        # although we might want an explicit '=' to note the same session as
        # mentioned before?
        if len(nonsign_vals) > 1:
            lgr.warning( #raise NotImplementedError(
                "Cannot deal with multiple sessions in the same study yet!"
                " We will process until the end of the first session"
            )
        if nonsign_vals:
            # get only unique values
            ses_markers = list(set(ses_markers))
            if set(ses_markers).intersection('+='):
                raise NotImplementedError(
                    "Should not mix hardcoded session markers with incremental ones (+=)"
                )
            assert len(ses_markers) == 1
            session = ses_markers[0]
        else:
            # TODO - I think we are doomed to go through the sequence and split
            # ... actually the same as with nonsign_vals, we just would need to figure
            # out initial one if sign ones, and should make use of knowing
            # outdir
            #raise NotImplementedError()
            # we need to look at what sessions we already have
            sessions_dir = os.path.join(outdir, locator, 'sub-' + subject)
            prior_sessions = sorted(glob(os.path.join(sessions_dir, 'ses-*')))
            # TODO: more complicated logic
            # For now just increment session if + and keep the same number if =
            # and otherwise just give it 001
            # Note: this disables our safety blanket which would refuse to process
            # what was already processed before since it would try to override,
            # BUT there is no other way besides only if heudiconv was storing
            # its info based on some UID
            if ses_markers == ['+']:
                session = '%03d' % (len(prior_sessions) + 1)
            elif ses_markers == ['=']:
                session = os.path.basename(prior_sessions[-1])[4:] if prior_sessions else '001'
            else:
                session = '001'


    if study_description_hash == '9d148e2a05f782273f6343507733309d':
        session = 'siemens1'
        lgr.info('Imposing session {0}'.format(session))

    return {
        # TODO: request info on study from the JedCap
        'locator': locator,
        # Sessions to be deduced yet from the names etc TODO
        'session': session,
        'subject': subject,
    }


def sanitize_str(value):
    """Remove illegal characters for BIDS from task/acq/etc.."""
    return _delete_chars(value, '#!@$%^&.,:;_-')


def parse_series_spec(series_spec):
    """Parse protocol name according to our convention with minimal set of fixups
    """
    # Since Yarik didn't know better place to put it in, but could migrate outside
    # at some point. TODO
    series_spec = series_spec.replace("anat_T1w", "anat-T1w")
    series_spec = series_spec.replace("hardi_64", "dwi_acq-hardi64")
    series_spec = series_spec.replace("AAHead_Scout", "anat-scout")

    # Parse the name according to our convention/specification

    # leading or trailing spaces do not matter
    series_spec = series_spec.strip(' ')

    # Strip off leading CAPITALS: prefix to accommodate some reported usecases:
    # https://github.com/ReproNim/reproin/issues/14
    # where PU: prefix is added by the scanner
    series_spec = re.sub("^[A-Z]*:", "", series_spec)

    # Remove possible suffix we don't care about after __
    series_spec = series_spec.split('__', 1)[0]

    bids = None  # we don't know yet for sure
    # We need to figure out if it is a valid bids
    split = series_spec.split('_')
    prefix = split[0]

    # Fixups
    if prefix == 'scout':
        prefix = split[0] = 'anat-scout'

    if prefix != 'bids' and '-' in prefix:
        prefix, _ = prefix.split('-', 1)
    if prefix == 'bids':
        bids = True  # for sure
        split = split[1:]

    def split2(s):
        # split on - if present, if not -- 2nd one returned None
        if '-' in s:
            return s.split('-', 1)
        return s, None

    # Let's analyze first element which should tell us sequence type
    seqtype, seqtype_label = split2(split[0])
    if seqtype not in {'anat', 'func', 'dwi', 'behav', 'fmap'}:
        # It is not something we don't consume
        if bids:
            lgr.warning("It was instructed to be BIDS sequence but unknown "
                        "type %s found", seqtype)
        return {}

    regd = dict(seqtype=seqtype)
    if seqtype_label:
        regd['seqtype_label'] = seqtype_label
    # now go through each to see if one which we care
    bids_leftovers = []
    for s in split[1:]:
        key, value = split2(s)
        if value is None and key[-1] in "+=":
            value = key[-1]
            key = key[:-1]

        # sanitize values, which must not have _ and - is undesirable ATM as well
        # TODO: BIDSv2.0 -- allows "-" so replace with it instead
        value = str(value).replace('_', 'X').replace('-', 'X')

        if key in ['ses', 'run', 'task', 'acq']:
            # those we care about explicitly
            regd[{'ses': 'session'}.get(key, key)] = sanitize_str(value)
        else:
            bids_leftovers.append(s)

    if bids_leftovers:
        regd['bids'] = '_'.join(bids_leftovers)

    # TODO: might want to check for all known "standard" BIDS suffixes here
    # among bids_leftovers, thus serve some kind of BIDS validator

    # if not regd.get('seqtype_label', None):
    #     # might need to assign a default label for each seqtype if was not
    #     # given
    #     regd['seqtype_label'] = {
    #         'func': 'bold'
    #     }.get(regd['seqtype'], None)

    return regd


def fixup_subjectid(subjectid):
    """Just in case someone managed to miss a zero or added an extra one"""
    # make it lowercase
    subjectid = subjectid.lower()
    reg = re.match("sid0*(\d+)$", subjectid)
    if not reg:
        # some completely other pattern
        # just filter out possible _- in it
        return re.sub('[-_]', '', subjectid)
    return "sid%06d" % int(reg.groups()[0])


def test_filter_files():
    # Filtering is currently disabled -- any sequence directory is Ok
    assert(filter_files('/home/mvdoc/dbic/09-run_func_meh/0123432432.dcm'))
    assert(filter_files('/home/mvdoc/dbic/run_func_meh/012343143.dcm'))


def test_md5sum():
    assert md5sum('cryptonomicon') == '1cd52edfa41af887e14ae71d1db96ad1'
    assert md5sum('mysecretmessage') == '07989808231a0c6f522f9d8e34695794'


def test_fix_canceled_runs():
    from collections import namedtuple
    FakeSeqInfo = namedtuple('FakeSeqInfo',
                             ['accession_number', 'series_id',
                              'protocol_name', 'series_description'])

    seqinfo = []
    runname = 'func_run+'
    for i in range(1, 6):
        seqinfo.append(
            FakeSeqInfo('accession1',
                        '{0:02d}-'.format(i) + runname,
                        runname, runname)
        )

    fake_accession2run = {
        'accession1': ['^01-', '^03-']
    }

    seqinfo_ = fix_canceled_runs(seqinfo, fake_accession2run)

    for i, s in enumerate(seqinfo_, 1):
        output = runname
        if i == 1 or i == 3:
            output = 'cancelme_' + output
        for key in ['series_description', 'protocol_name']:
            value = getattr(s, key)
            assert(value == output)
        # check we didn't touch series_id
        assert(s.series_id == '{0:02d}-'.format(i) + runname)


def test_fix_dbic_protocol():
    from collections import namedtuple
    FakeSeqInfo = namedtuple('FakeSeqInfo',
                             ['accession_number', 'study_description',
                              'field1', 'field2'])
    accession_number = 'A003'
    seq1 = FakeSeqInfo(accession_number,
                       'mystudy',
                       '02-anat-scout_run+_MPR_sag',
                       '11-func_run-life2_acq-2mm692')
    seq2 = FakeSeqInfo(accession_number,
                       'mystudy',
                       'nochangeplease',
                       'nochangeeither')


    seqinfos = [seq1, seq2]
    keys = ['field1']
    subsdict = {
        md5sum('mystudy'):
            [('scout_run\+', 'scout'),
             ('run-life[0-9]', 'run+_task-life')],
    }

    seqinfos_ = fix_dbic_protocol(seqinfos, keys=keys, subsdict=subsdict)
    assert(seqinfos[1] == seqinfos_[1])
    # field2 shouldn't have changed since I didn't pass it
    assert(seqinfos_[0] == FakeSeqInfo(accession_number,
                                       'mystudy',
                                       '02-anat-scout_MPR_sag',
                                       seq1.field2))

    # change also field2 please
    keys = ['field1', 'field2']
    seqinfos_ = fix_dbic_protocol(seqinfos, keys=keys, subsdict=subsdict)
    assert(seqinfos[1] == seqinfos_[1])
    # now everything should have changed
    assert(seqinfos_[0] == FakeSeqInfo(accession_number,
                                       'mystudy',
                                       '02-anat-scout_MPR_sag',
                                       '11-func_run+_task-life_acq-2mm692'))


def test_sanitize_str():
    assert sanitize_str('super@duper.faster') == 'superduperfaster'
    assert sanitize_str('perfect') == 'perfect'
    assert sanitize_str('never:use:colon:!') == 'neverusecolon'


def test_fixupsubjectid():
    assert fixup_subjectid("abra") == "abra"
    assert fixup_subjectid("sub") == "sub"
    assert fixup_subjectid("sid") == "sid"
    assert fixup_subjectid("sid000030") == "sid000030"
    assert fixup_subjectid("sid0000030") == "sid000030"
    assert fixup_subjectid("sid00030") == "sid000030"
    assert fixup_subjectid("sid30") == "sid000030"
    assert fixup_subjectid("SID30") == "sid000030"


def test_parse_series_spec():
    pdpn = parse_series_spec

    assert pdpn("nondbic_func-bold") == {}
    assert pdpn("cancelme_func-bold") == {}

    assert pdpn("bids_func-bold") == \
           pdpn("func-bold") == \
           {'seqtype': 'func', 'seqtype_label': 'bold'}

    # pdpn("bids_func_ses+_task-boo_run+") == \
    # order and PREFIX: should not matter, as well as trailing spaces
    assert \
        pdpn(" PREFIX:bids_func_ses+_task-boo_run+  ") == \
        pdpn("PREFIX:bids_func_ses+_task-boo_run+") == \
        pdpn("bids_func_ses+_run+_task-boo") == \
           {
               'seqtype': 'func',
               # 'seqtype_label': 'bold',
               'session': '+',
               'run': '+',
               'task': 'boo',
            }

    # TODO: fix for that
    assert pdpn("bids_func-pace_ses-1_task-boo_acq-bu_bids-please_run-2__therest") == \
           pdpn("bids_func-pace_ses-1_run-2_task-boo_acq-bu_bids-please__therest") == \
           pdpn("func-pace_ses-1_task-boo_acq-bu_bids-please_run-2") == \
           {
               'seqtype': 'func', 'seqtype_label': 'pace',
               'session': '1',
               'run': '2',
               'task': 'boo',
               'acq': 'bu',
               'bids': 'bids-please'
           }

    assert pdpn("bids_anat-scout_ses+") == \
           {
               'seqtype': 'anat',
               'seqtype_label': 'scout',
               'session': '+',
           }

    assert pdpn("anat_T1w_acq-MPRAGE_run+") == \
           {
                'seqtype': 'anat',
                'run': '+',
                'acq': 'MPRAGE',
                'seqtype_label': 'T1w'
           }
