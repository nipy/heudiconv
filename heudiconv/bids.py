"""Handle BIDS specific operations"""

import os
import os.path as op
import logging
import re
from collections import OrderedDict
from datetime import datetime
import csv
from random import sample
from glob import glob

from heudiconv.external.pydicom import dcm

from .parser import find_files
from .utils import (
    load_json,
    save_json,
    create_file_if_missing,
    json_dumps_pretty,
    set_readonly,
    is_readonly,
)

lgr = logging.getLogger(__name__)

def populate_bids_templates(path, defaults={}):
    """Premake BIDS text files with templates"""

    lgr.info("Populating template files under %s", path)
    descriptor = op.join(path, 'dataset_description.json')
    if not op.lexists(descriptor):
        save_json(descriptor,
              OrderedDict([
                  ('Name', "TODO: name of the dataset"),
                  ('BIDSVersion', "1.0.1"),
                  ('License', defaults.get('License',
                        "TODO: choose a license, e.g. PDDL "
                        "(http://opendatacommons.org/licenses/pddl/)")),
                  ('Authors', defaults.get('Authors',
                        ["TODO:", "First1 Last1", "First2 Last2", "..."])),
                  ('Acknowledgements', defaults.get('Acknowledgements',
                        'TODO: whom you want to acknowledge')),
                  ('HowToAcknowledge',
                        "TODO: describe how to acknowledge -- either cite a "
                        "corresponding paper, or just in acknowledgement "
                        "section"),
                  ('Funding', ["TODO", "GRANT #1", "GRANT #2"]),
                  ('ReferencesAndLinks',
                        ["TODO", "List of papers or websites"]),
                  ('DatasetDOI', 'TODO: eventually a DOI for the dataset')
        ]))
    sourcedata_README = op.join(path, 'sourcedata', 'README')
    if op.exists(op.dirname(sourcedata_README)):
        create_file_if_missing(sourcedata_README,
            ("TODO: Provide description about source data, e.g. \n"
            "Directory below contains DICOMS compressed into tarballs per "
            "each sequence, replicating directory hierarchy of the BIDS dataset"
            " itself."))
    create_file_if_missing(op.join(path, 'CHANGES'),
        "0.0.1  Initial data acquired\n"
        "TODOs:\n\t- verify and possibly extend information in participants.tsv"
        " (see for example http://datasets.datalad.org/?dir=/openfmri/ds000208)"
        "\n\t- fill out dataset_description.json, README, sourcedata/README"
        " (if present)\n\t- provide _events.tsv file for each _bold.nii.gz with"
        " onsets of events (see  '8.5 Task events'  of BIDS specification)")
    create_file_if_missing(op.join(path, 'README'),
        "TODO: Provide description for the dataset -- basic details about the "
        "study, possibly pointing to pre-registration (if public or embargoed)")

    # TODO: collect all task- .json files for func files to
    tasks = {}
    # way too many -- let's just collect all which are the same!
    # FIELDS_TO_TRACK = {'RepetitionTime', 'FlipAngle', 'EchoTime',
    #                    'Manufacturer', 'SliceTiming', ''}
    for fpath in find_files('.*_task-.*\_bold\.json', topdir=path,
                        exclude_vcs=True, exclude="/\.(datalad|heudiconv)/"):
        task = re.sub('.*_(task-[^_\.]*(_acq-[^_\.]*)?)_.*', r'\1', fpath)
        json_ = load_json(fpath)
        if task not in tasks:
            tasks[task] = json_
        else:
            rec = tasks[task]
            # let's retain only those fields which have the same value
            for field in sorted(rec):
                if field not in json_ or json_[field] != rec[field]:
                    del rec[field]
        # create a stub onsets file for each one of those
        suf = '_bold.json'
        assert fpath.endswith(suf)
        events_file = fpath[:-len(suf)] + '_events.tsv'
        # do not touch any existing thing, it may be precious
        if not op.lexists(events_file):
            lgr.debug("Generating %s", events_file)
            with open(events_file, 'w') as f:
                f.write("onset\tduration\ttrial_type\tresponse_time\tstim_file\tTODO -- fill in rows and add more tab-separated columns if desired")
    # extract tasks files stubs
    for task_acq, fields in tasks.items():
        task_file = op.join(path, task_acq + '_bold.json')
        # do not touch any existing thing, it may be precious
        if not op.lexists(task_file):
            lgr.debug("Generating %s", task_file)
            fields["TaskName"] = ("TODO: full task name for %s" %
                                  task_acq.split('_')[0].split('-')[1])
            fields["CogAtlasID"] = "TODO"
            with open(task_file, 'w') as f:
                f.write(json_dumps_pretty(fields, indent=2, sort_keys=True))


def tuneup_bids_json_files(json_files):
    """Given a list of BIDS .json files, e.g. """
    if not json_files:
        return
    # Harmonize generic .json formatting
    for jsonfile in json_files:
        json_ = load_json(jsonfile)
        # sanitize!
        for f1 in ['Acquisition', 'Study', 'Series']:
            for f2 in ['DateTime', 'Date']:
                json_.pop(f1 + f2, None)
        # TODO:  should actually be placed into series file which must
        #        go under annex (not under git) and marked as sensitive
        # MG - Might want to replace with flag for data sensitivity
        # related - https://github.com/nipy/heudiconv/issues/92
        if 'Date' in str(json_):
            # Let's hope no word 'Date' comes within a study name or smth like
            # that
            raise ValueError("There must be no dates in .json sidecar")
        save_json(jsonfile, json_, indent=2)

    # Load the beast
    seqtype = op.basename(op.dirname(jsonfile))

    # MG - want to expand this for other _epi
    # possibly add IntendedFor automatically as well?
    if seqtype == 'fmap':
        json_basename = '_'.join(jsonfile.split('_')[:-1])
        # if we got by now all needed .json files -- we can fix them up
        # unfortunately order of "items" is not guaranteed atm
        json_phasediffname = json_basename + '_phasediff.json'
        json_mag = json_basename + '_magnitude*.json'
        if op.exists(json_phasediffname) and len(glob(json_mag)) >= 1:
            json_ = load_json(json_phasediffname)
            # TODO: we might want to reorder them since ATM
            # the one for shorter TE is the 2nd one!
            # For now just save truthfully by loading magnitude files
            lgr.debug("Placing EchoTime fields into phasediff file")
            for i in 1, 2:
                try:
                    json_['EchoTime%d' % i] = (load_json(json_basename +
                                          '_magnitude%d.json' % i)['EchoTime'])
                except IOError as exc:
                    lgr.error("Failed to open magnitude file: %s", exc)
            # might have been made R/O already, but if not -- it will be set
            # only later in the pipeline, so we must not make it read-only yet
            was_readonly = is_readonly(json_phasediffname)
            if was_readonly:
                set_readonly(json_phasediffname, False)
            save_json(json_phasediffname, json_, indent=2)
            if was_readonly:
                set_readonly(json_phasediffname)


def add_participant_record(studydir, subject, age, sex):
    participants_tsv = op.join(studydir, 'participants.tsv')
    participant_id = 'sub-%s' % subject

    if not create_file_if_missing(participants_tsv,
           '\t'.join(['participant_id', 'age', 'sex', 'group']) + '\n'):
        # check if may be subject record already exists
        with open(participants_tsv) as f:
            f.readline()
            known_subjects = {l.split('\t')[0] for l in f.readlines()}
        if participant_id in known_subjects:
            return
    # Add a new participant
    with open(participants_tsv, 'a') as f:
        f.write(
          '\t'.join(map(str, [participant_id,
                              age.lstrip('0').rstrip('Y') if age else 'N/A',
                              sex,
                              'control'])) + '\n')


def find_subj_ses(f_name):
    """Given a path to the bids formatted filename parse out subject/session"""
    # we will allow the match at either directories or within filename
    # assuming that bids layout is "correct"
    regex = re.compile('sub-(?P<subj>[a-zA-Z0-9]*)([/_]ses-(?P<ses>[a-zA-Z0-9]*))?')
    regex_res = regex.search(f_name)
    res = regex_res.groupdict() if regex_res else {}
    return res.get('subj', None), res.get('ses', None)


def save_scans_key(item, bids_files):
    """
    Parameters
    ----------
    items:
    bids_files: str or list

    Returns
    -------

    """
    rows = {}
    assert bids_files, "we do expect some files since it was called"
    # we will need to deduce subject and session from the bids_filename
    # and if there is a conflict, we would just blow since this function
    # should be invoked only on a result of a single item conversion as far
    # as I see it, so should have the same subject/session
    subj, ses = None, None
    for bids_file in bids_files:
        # get filenames
        f_name = '/'.join(bids_file.split('/')[-2:])
        f_name = f_name.replace('json', 'nii.gz')
        rows[f_name] = get_formatted_scans_key_row(item)
        subj_, ses_ = find_subj_ses(f_name)
        if not subj_:
            lgr.warning(
                "Failed to detect fullfilled BIDS layout.  "
                "No scans.tsv file(s) will be produced for %s",
                ", ".join(bids_files)
            )
            return
        if subj and subj_ != subj:
            raise ValueError(
                "We found before subject %s but now deduced %s from %s"
                % (subj, subj_, f_name))
        subj = subj_
        if ses and ses_ != ses:
            raise ValueError(
                "We found before session %s but now deduced %s from %s"
                % (ses, ses_, f_name)
            )
        ses = ses_
    # where should we store it?
    output_dir = op.dirname(op.dirname(bids_file))
    # save
    ses = '_ses-%s' % ses if ses else ''
    add_rows_to_scans_keys_file(
        op.join(output_dir, 'sub-{0}{1}_scans.tsv'.format(subj, ses)), rows)


def add_rows_to_scans_keys_file(fn, newrows):
    """
    Add new rows to file fn for scans key filename

    Parameters
    ----------
    fn: filename
    newrows: extra rows to add
        dict fn: [acquisition time, referring physician, random string]
    """
    if op.lexists(fn):
        with open(fn, 'r') as csvfile:
            reader = csv.reader(csvfile, delimiter='\t')
            existing_rows = [row for row in reader]
        # skip header
        fnames2info = {row[0]: row[1:] for row in existing_rows[1:]}

        newrows_key = newrows.keys()
        newrows_toadd = list(set(newrows_key) - set(fnames2info.keys()))
        for key_toadd in newrows_toadd:
            fnames2info[key_toadd] = newrows[key_toadd]
        # remove
        os.unlink(fn)
    else:
        fnames2info = newrows

    header = ['filename', 'acq_time', 'operator', 'randstr']
    # prepare all the data rows
    data_rows = [[k] + v for k, v in fnames2info.items()]
    # sort by the date/filename
    data_rows_sorted = sorted(data_rows, key=lambda x: (x[1], x[0]))
    # save
    with open(fn, 'a') as csvfile:
        writer = csv.writer(csvfile, delimiter='\t')
        writer.writerows([header] + data_rows_sorted)


def get_formatted_scans_key_row(item):
    """
    Parameters
    ----------
    item

    Returns
    -------
    row: list
        [ISO acquisition time, performing physician name, random string]

    """
    dcm_fn = item[-1][0]
    from heudiconv.external.dcmstack import ds
    mw = ds.wrapper_from_data(dcm.read_file(dcm_fn,
                                            stop_before_pixels=True,
                                            force=True))
    # we need to store filenames and acquisition times
    # parse date and time and get it into isoformat
    try:
        date = mw.dcm_data.ContentDate
        time = mw.dcm_data.ContentTime.split('.')[0]
        td = time + date
        acq_time = datetime.strptime(td, '%H%M%S%Y%m%d').isoformat()
    except AttributeError as exc:
        lgr.warning("Failed to get date/time for the content: %s", str(exc))
        acq_time = None
    # add random string
    randstr = ''.join(map(chr, sample(k=8, population=range(33, 127))))
    try:
        perfphys = mw.dcm_data.PerformingPhysicianName
    except AttributeError:
        perfphys = ''
    row = [acq_time, perfphys, randstr]
    # empty entries should be 'n/a'
    # https://github.com/dartmouth-pbs/heudiconv/issues/32
    row = ['n/a' if not str(e) else e for e in row]
    return row


def convert_sid_bids(subject_id):
    """Strips any non-BIDS compliant characters within subject_id

    Parameters
    ----------
    subject_id : string

    Returns
    -------
    sid : string
        New subject ID
    subject_id : string
        Original subject ID
    """
    cleaner = lambda y: ''.join([x for x in y if x.isalnum()])
    sid = cleaner(subject_id)
    if not sid:
        raise ValueError(
            "Subject ID became empty after cleanup.  Please provide manually "
            "a suitable alphanumeric subject ID")
    lgr.warning('{0} contained nonalphanumeric character(s), subject '
                'ID was cleaned to be {1}'.format(subject_id, sid))
    return sid, subject_id
