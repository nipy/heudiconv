#!/usr/bin/env python
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the Heudiconv package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##


def main():
    import os.path as op

    from setuptools import find_packages, findall, setup

    thispath = op.dirname(__file__)
    ldict = locals()

    # Get version and release info, which is all stored in heudiconv/info.py
    info_file = op.join(thispath, "heudiconv", "info.py")
    with open(info_file) as infofile:
        exec(infofile.read(), globals(), ldict)

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

    def findsome(subdir, extensions):
        """Find files under subdir having specified extensions

        Leading directory (datalad) gets stripped
        """
        return [
            f.split(op.sep, 1)[1]
            for f in findall(subdir)
            if op.splitext(f)[-1].lstrip(".") in extensions
        ]

    # Only recentish versions of find_packages support include
    # heudiconv_pkgs = find_packages('.', include=['heudiconv*'])
    # so we will filter manually for maximal compatibility
    heudiconv_pkgs = [pkg for pkg in find_packages(".") if pkg.startswith("heudiconv")]

    setup(
        name=ldict["__packagename__"],
        author=ldict["__author__"],
        # author_email="team@???",
        description=ldict["__description__"],
        long_description=ldict["__longdesc__"],
        license=ldict["__license__"],
        classifiers=ldict["CLASSIFIERS"],
        packages=heudiconv_pkgs,
        entry_points={
            "console_scripts": [
                "heudiconv=heudiconv.cli.run:main",
                "heudiconv_monitor=heudiconv.cli.monitor:main",
            ]
        },
        python_requires=ldict["PYTHON_REQUIRES"],
        install_requires=ldict["REQUIRES"],
        extras_require=ldict["EXTRA_REQUIRES"],
        package_data={
            "heudiconv": ["py.typed"],
            "heudiconv.tests": [
                op.join("data", "*.dcm"),
                op.join("data", "*", "*.dcm"),
                op.join("data", "*", "*", "*.dcm"),
                op.join("data", "sample_nifti*"),
            ],
        },
        **kwargs,
    )


if __name__ == "__main__":
    main()
