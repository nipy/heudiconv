"""Handle BIDS specific operations"""

import os
import os.path as op
import logging
import re
from collections import OrderedDict
from .utils import (load_json, save_json, create_file_if_missing,
                    json_dumps_pretty

lgr = logging.getLogger(__name__)

def populate_bids_templates(path, defaults={}):
    """Premake BIDS text files with templates"""

    lgr.info("Populating template files under %s", path)
    descriptor = op.join(path, 'dataset_description.json')
    if not exists(descriptor):
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
            " itself.")
    create_file_if_missing(op.join(path, 'CHANGES'),
        "0.0.1  Initial data acquired\n"
        "TODOs:\n\t- verify and possibly extend information in participants.tsv"
        "(see for example http://datasets.datalad.org/?dir=/openfmri/ds000208)"
        "\n\t- fill out dataset_description.json, README, sourcedata/README "
        "(if present)\n\t- provide _events.tsv file for each _bold.nii.gz with "
        "onsets of events (see  '8.5 Task events'  of BIDS specification)")
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
        lgr.debug("Generating %s", events_file)
        with open(events_file, 'w') as f:
            f.write("onset\tduration\ttrial_type\tresponse_time")
    # extract tasks files stubs
    for task_acq, fields in tasks.items():
        task_file = op.join(path, task_acq + '_bold.json')
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
        #json.dump(json_, open(jsonfile, 'w'), indent=2)
        save_json(jsonfile, json_, indent=2) # ensure this does same as above

    # Load the beast
    seqtype = op.basename(op.dirname(jsonfile))

    # MG - want to expand this for other _epi
    # possibly add IntendedFor automatically as well?
    if seqtype == 'fmap':
        json_basename = '_'.join(jsonfile.split('_')[:-1])
        # if we got by now all needed .json files -- we can fix them up
        # unfortunately order of "items" is not guaranteed atm
        if len(glob(json_basename + '*.json')) == 3:
            json_phasediffname = json_basename + '_phasediff.json'
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
            # might have been made R/O already
            os.chmod(json_phasediffname, 0o0664)
            #json.dump(json_, open(json_phasediffname, 'w'), indent=2)
            save_json(json_phasediffname, json_, indent=2)
            os.chmod(json_phasediffname, 0o0444)


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
