#!/usr/bin/env python
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the Heudiconv package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Bits of packaging metadata which cannot be expressed statically.

Everything else lives in pyproject.toml.  Here we only

- take the version from the pre-generated heudiconv/_version.py whenever
  versioningit is not available, and
- turn README.rst into the long description, absolutizing the links so that
  the README itself can stay portal-agnostic (see absolutize_links below).
"""

import os.path as op
import re

#: Repository the relative links in README.rst are relative to, and the ref to
#: point to.  Only used to render the long description for PyPI et al.
REPO_URL = "https://github.com/nipy/heudiconv"
REPO_REF = "master"

#: A link target which is already usable as is: an URL (scheme:...), a fragment
#: (#section), or a protocol-relative URL (//host/...)
ABSOLUTE = r"(?![a-z][a-z0-9+.-]*:|[#/])"

#: (regex, is_image) pairs covering the reStructuredText constructs which can
#: carry a relative link.  Group 1 is kept as is, group 2 is the target.
#: Images have to be served as raw content, everything else links to the page.
LINK_RES = [
    # .. image:: figs/workflow.png     (or `.. |sub| figure:: ...`)
    (rf"(?m)^(\s*\.\.\s+(?:\|[^|]+\|\s+)?(?:image|figure)::\s+){ABSOLUTE}(\S+)", True),
    # :target: some/page.rst
    (rf"(?m)^(\s*:target:\s+){ABSOLUTE}(\S+)", False),
    # `contributing guide <CONTRIBUTING.rst>`_
    (rf"(<){ABSOLUTE}([^<>\s]+)(?=>`_)", False),
    # .. _contributing guide: CONTRIBUTING.rst
    (rf"(?m)^(\s*\.\.\s+_[^:]+:\s+){ABSOLUTE}(\S+)$", False),
]


def absolutize_links(text, repo_url=REPO_URL, ref=REPO_REF):
    """Point relative links in ``text`` (reStructuredText) back to the repository

    Rendered outside of the repository -- on PyPI in particular -- relative
    links are broken, but spelling them out in README.rst would tie it to
    GitHub and break rendering of e.g. figures on readthedocs, where the very
    same README is ``.. include``d.  So keep them relative in the file and
    expand them only for whoever needs a self-contained document.

    >>> absolutize_links(".. image:: figs/workflow.png")
    '.. image:: https://raw.githubusercontent.com/nipy/heudiconv/master/figs/workflow.png'
    >>> absolutize_links("see the `guide <CONTRIBUTING.rst>`_.")
    'see the `guide <https://github.com/nipy/heudiconv/blob/master/CONTRIBUTING.rst>`_.'
    >>> absolutize_links("see `docs <./docs>`_.")  # the ./ prefix we tend to use
    'see `docs <https://github.com/nipy/heudiconv/blob/master/docs>`_.'
    >>> absolutize_links(".. image:: https://example.com/badge.svg")
    '.. image:: https://example.com/badge.svg'
    """
    raw_url = repo_url.replace(
        "https://github.com/", "https://raw.githubusercontent.com/"
    )
    for regex, is_image in LINK_RES:
        base = f"{raw_url}/{ref}/" if is_image else f"{repo_url}/blob/{ref}/"
        text = re.sub(
            regex, lambda m, base=base: m[1] + base + re.sub(r"^\./", "", m[2]), text
        )
    return text


def main():
    from setuptools import setup

    with open(op.join(op.dirname(__file__), "README.rst")) as f:
        long_description = absolutize_links(f.read())

    kwargs = {
        "long_description": long_description,
        "long_description_content_type": "text/x-rst",
    }

    try:
        import versioningit  # noqa: F401
    except ImportError:
        # versioningit isn't installed; assume we're building a Debian package
        # from an sdist on an older Debian that doesn't support pybuild
        vglobals = {}
        with open(op.join(op.dirname(__file__), "heudiconv", "_version.py")) as fp:
            exec(fp.read(), vglobals)
        kwargs["version"] = vglobals["__version__"]

    setup(**kwargs)


if __name__ == "__main__":
    main()
