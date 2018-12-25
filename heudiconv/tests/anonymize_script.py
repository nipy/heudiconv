#! /usr/bin/env python 

import sys
import re
import ctypes


def bids_id_(sid):
    parsed_id = re.compile(r"^(?:sub-|)(.+)$").search(sid).group(1)
    return str(ctypes.c_size_t(hash(parsed_id)).value)


def main():
    sid = sys.argv[1]
    return bids_id_(sid)


if __name__ == '__main__':
    main()
