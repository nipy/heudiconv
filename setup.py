#!/usr/bin/env python
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the Heudiconv package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Shim to support builds without versioningit.

All packaging metadata lives in pyproject.toml.  This file is kept around only
to be able to take the version from the pre-generated heudiconv/_version.py
whenever versioningit is not available.
"""


def main():
    import os.path as op

    from setuptools import setup

    try:
        import versioningit  # noqa: F401
    except ImportError:
        # versioningit isn't installed; assume we're building a Debian package
        # from an sdist on an older Debian that doesn't support pybuild
        vglobals = {}
        with open(op.join(op.dirname(__file__), "heudiconv", "_version.py")) as fp:
            exec(fp.read(), vglobals)
        kwargs = {"version": vglobals["__version__"]}
    else:
        kwargs = {}

    setup(**kwargs)


if __name__ == "__main__":
    main()
