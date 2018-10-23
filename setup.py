#!/usr/bin/env python
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the Heudiconv package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##


def main():

    import os.path as op

    from setuptools import findall, setup, find_packages

    thispath = op.dirname(__file__)
    ldict = locals()

    # Get version and release info, which is all stored in heudiconv/info.py
    info_file = op.join(thispath, 'heudiconv', 'info.py')
    with open(info_file) as infofile:
        # exec(infofile.read(), globals(), ldict)
        # Workaround for python 2.7 prior 2.7.8
        eval(compile(infofile.read(), '<string>', 'exec'), globals(), ldict)


    def findsome(subdir, extensions):
        """Find files under subdir having specified extensions

        Leading directory (datalad) gets stripped
        """
        return [
            f.split(op.sep, 1)[1] for f in findall(subdir)
            if op.splitext(f)[-1].lstrip('.') in extensions
        ]
    # Only recentish versions of find_packages support include
    # heudiconv_pkgs = find_packages('.', include=['heudiconv*'])
    # so we will filter manually for maximal compatibility
    heudiconv_pkgs = [pkg for pkg in find_packages('.') if pkg.startswith('heudiconv')]


    setup(
        name=ldict['__packagename__'],
        author=ldict['__author__'],
        #author_email="team@???",
        version=ldict['__version__'],
        description=ldict['__description__'],
        long_description=ldict['__longdesc__'],
        license=ldict['__license__'],
        packages=heudiconv_pkgs,
        entry_points={'console_scripts': [
            'heudiconv=heudiconv.cli.run:main',
            'heudiconv_monitor=heudiconv.cli.monitor:main',
        ]},
        install_requires=ldict['REQUIRES'],
        extras_require=ldict['EXTRA_REQUIRES'],
        )


if __name__ == '__main__':
    main()
