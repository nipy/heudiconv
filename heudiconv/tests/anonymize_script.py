#! /usr/bin/env python3

import hashlib
import re
import sys


def bids_id_(sid: str) -> str:
    m = re.compile(r"^(?:sub-|)(.+)$").search(sid)
    if m:
        parsed_id = m.group(1)
        return hashlib.md5(parsed_id.encode()).hexdigest()[:8]
    else:
        raise ValueError("invalid sid")


def main() -> str:
    sid = sys.argv[1]
    return bids_id_(sid)


if __name__ == "__main__":
    print(main())
