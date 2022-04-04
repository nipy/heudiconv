#! /usr/bin/env python3

import sys
import re
import hashlib


def bids_id_(sid):
    parsed_id = re.compile(r"^(?:sub-|)(.+)$").search(sid).group(1)
    return hashlib.md5(parsed_id.encode()).hexdigest()[:8]


def main():
    sid = sys.argv[1]
    return bids_id_(sid)


if __name__ == '__main__':
    print(main())
