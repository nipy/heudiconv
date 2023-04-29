#!/usr/bin/env python
from __future__ import annotations

import argparse
from collections import OrderedDict
import json
import logging
import os
import os.path as op
from pathlib import Path
import re
import shlex
import subprocess
import time
from typing import Any, Optional

import inotify.adapters
from inotify.constants import IN_CREATE, IN_ISDIR, IN_MODIFY
from tinydb import TinyDB

_DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_LOGGER = logging.getLogger(__name__)

MASK = IN_MODIFY | IN_CREATE
MASK_NEWDIR = IN_CREATE | IN_ISDIR
WAIT_TIME = 86400  # in seconds


# def _configure_logging():
_LOGGER.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
formatter = logging.Formatter(_DEFAULT_LOG_FORMAT)
ch.setFormatter(formatter)
_LOGGER.addHandler(ch)


def run_heudiconv(args: list[str]) -> tuple[str, dict[str, Any]]:
    info_dict: dict[str, Any] = dict()
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    cmd = " ".join(map(shlex.quote, args))
    return_code = proc.wait()
    if return_code == 0:
        _LOGGER.info("Done running %s", cmd)
        info_dict["success"] = 1
    else:
        _LOGGER.error("%s failed", cmd)
        info_dict["success"] = 0
    # get info on what we run
    stdout = proc.communicate()[0].decode("utf-8")
    match = re.match("INFO: PROCESSING STARTS: (.*)", stdout)
    info_dict_ = json.loads(match.group(1) if match else "{}")
    info_dict.update(info_dict_)
    return stdout, info_dict


def process(
    paths2process: dict[str, float],
    db: Optional[TinyDB],
    wait: int | float = WAIT_TIME,
    logdir: str = "log",
) -> None:
    # if paths2process and
    # time.time() - os.path.getmtime(paths2process[0]) > WAIT_TIME:
    processed: list[str] = []
    for path, mod_time in paths2process.items():
        if time.time() - mod_time > wait:
            # process_me = paths2process.popleft().decode('utf-8')
            process_me = path
            process_dict: dict[str, Any] = {
                "input_path": process_me,
                "accession_number": op.basename(process_me),
            }
            print("Time to process {0}".format(process_me))
            stdout, run_dict = run_heudiconv(["ls", "-l", process_me])
            process_dict.update(run_dict)
            if db is not None:
                db.insert(process_dict)
            # save log
            log = Path(logdir, process_dict["accession_number"] + ".log")
            log.write_text(stdout)
            # if we processed it, or it failed,
            # we need to remove it to avoid running it again
            processed.append(path)
    for processed_path in processed:
        del paths2process[processed_path]


def monitor(
    topdir: str = "/tmp/new_dir",
    check_ptrn: str = "/20../../..",
    db: Optional[TinyDB] = None,
    wait: int | float = WAIT_TIME,
    logdir: str = "log",
) -> None:
    # make logdir if not existent
    try:
        os.makedirs(logdir)
    except OSError:
        pass
    # paths2process = deque()
    paths2process: dict[str, float] = OrderedDict()
    # watch only today's folder
    path_re = re.compile("(%s%s)/?$" % (topdir, check_ptrn))
    i = inotify.adapters.InotifyTree(topdir.encode())  # , mask=MASK)
    for event in i.event_gen():
        if event is not None:
            (header, type_names, watch_path, filename) = event
            _LOGGER.info(
                "WD=(%d) MASK=(%d) COOKIE=(%d) LEN=(%d) MASK->NAMES=%s"
                " WATCH-PATH=[%s] FILENAME=[%s]",
                header.wd,
                header.mask,
                header.cookie,
                header.len,
                type_names,
                watch_path.decode("utf-8"),
                filename.decode("utf-8"),
            )
            if header.mask == MASK_NEWDIR and path_re.match(watch_path.decode("utf-8")):
                # we got our directory, now let's do something on it
                newpath2process = op.join(watch_path, filename).decode("utf-8")
                # paths2process.append(newpath2process)
                # update time
                paths2process[newpath2process] = time.time()
                print(newpath2process, time.time())
            # check if we need to update the time
            for path in paths2process.keys():
                if path in watch_path.decode("utf-8"):
                    paths2process[path] = time.time()
                    print("Updating {0}: {1}".format(path, paths2process[path]))

        # check if there's anything to process
        process(paths2process, db, wait=wait, logdir=logdir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="monitor.py",
        description=(
            "Small monitoring script to detect new directories and " "process them"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("path", help="Which directory to monitor")
    parser.add_argument(
        "--check_ptrn",
        "-p",
        help="regexp pattern for which subdirectories to check",
        default="/20../../..",
    )
    parser.add_argument(
        "--database", "-d", help="database location", default="database.json"
    )
    parser.add_argument(
        "--wait_time",
        "-w",
        help="After how long should we start processing datasets? (in seconds)",
        default=86400,
        type=float,
    )
    parser.add_argument(
        "--logdir", "-l", help="Where should we save the logs?", default="log"
    )
    return parser.parse_args()


def main() -> None:
    parsed = parse_args()
    print("Got {0}".format(parsed))
    # open database
    db = TinyDB(parsed.database, default_table="heudiconv")
    monitor(
        parsed.path, parsed.check_ptrn, db, wait=parsed.wait_time, logdir=parsed.logdir
    )


if __name__ == "__main__":
    main()
