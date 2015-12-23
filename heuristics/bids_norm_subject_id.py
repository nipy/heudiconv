#!/usr/bin/env python
import re, sys

print "sub-" + re.sub("[^a-zA-Z0-9]*", "", sys.argv[1])
