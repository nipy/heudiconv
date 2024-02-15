=========================
Contributing to HeuDiConv
=========================

Files organization
------------------

* `heudiconv/ <./heudiconv>`_ is the main Python module where major development is happening, with
  major submodules being:

  - ``cli/`` - wrappers and argument parsers bringing the HeuDiConv functionality to the command
    line.
  - ``external/`` - general compatibility layers for external functions HeuDiConv depends on.
  - ``heuristics/`` - heuristic evaluators for workflows, pull requests here are particularly
    welcome.

* `docs/ <./docs>`_ - documentation directory.
* `utils/ <./utils>`_ - helper utilities used during development, testing, and distribution of
  HeuDiConv.

How to contribute
-----------------

The preferred way to contribute to the HeuDiConv code base is
to fork the `main repository <https://github.com/nipy/heudiconv/>`_ on GitHub.

If you are unsure what that means, here is a set-up workflow you may wish to follow:

0. Fork the `project repository <https://github.com/nipy/heudiconv>`_ on GitHub, by clicking
   on the “Fork” button near the top of the page — this will create a copy of the repository
   writeable by your GitHub user.
1. Set up a clone of the repository on your local machine and connect it to both the “official”
   and your copy of the repository on GitHub::

     git clone git://github.com/nipy/heudiconv
     cd heudiconv
     git remote rename origin official
     git remote add origin git://github.com/YOUR_GITHUB_USERNAME/heudiconv

2. When you wish to start a new contribution, create a new branch::

     git checkout -b topic_of_your_contribution

3. When you are done making the changes you wish to contribute, record them in Git::

     git add the/paths/to/files/you/modified can/be/more/than/one
     git commit

3. Push the changes to your copy of the code on GitHub, following which Git will
   provide you with a link which you can click to initiate a pull request::

     git push -u origin topic_of_your_contribution

(If any of the above seems overwhelming, you can look up the `Git documentation
<http://git-scm.com/documentation>`_ on the web.)


Releases and Changelog
----------------------

HeuDiConv uses the `auto <https://intuit.github.io/auto/>`_ tool to generate the changelog and automatically release the project.

`auto` is used in the HeuDiConv GitHub actions, which monitors the labels on the pull request.
HeuDiConv automation can add entries to the changelog, cut releases, and
push new images to `dockerhub <https://hub.docker.com/r/nipy/heudiconv>`_.

The following pull request labels are respected:

    * major: Increment the major version when merged
    * minot: Increment the minot version when merged
    * patch: Increment the patch version when merged
    * skip-release: Preserve the current version when merged
    * release: Create a release when this pr is merged
    * internal: Changes only affect the internal API
    * documentation: Changes only affect the documentation
    * tests: Add or improve existing tests
    * dependencies: Update one or more dependencies version
    * performance: Improve performance of an existing feature


Development environment
-----------------------

We support Python 3 only (>= 3.7).

Dependencies which you will need are `listed in the repository <heudiconv/info.py>`_.
Note that you will likely have these will already be available on your system if you used a
package manager (e.g. Debian's ``apt-get``, Gentoo's ``emerge``, or simply PIP) to install the
software.

Development work might require live access to the copy of HeuDiConv which is being developed.
If a system-wide release of HeuDiConv is already installed, or likely to be, it is best to keep
development work sandboxed inside a dedicated virtual environment.
This is best accomplished via::

  cd /path/to/your/clone/of/heudiconv
  mkdir -p venvs/dev
  python -m venv venvs/dev
  source venvs/dev/bin/activate
  pip install -e .[all]


Documentation
-------------

To contribute to the documentation, we recommend building the docs
locally prior to submitting a patch.

To build the docs locally:

 1. From the root of the heudiconv repository, `pip install -r docs/requirements.txt`
 2. From the `docs/` directory, run `make html`


Additional Hints
----------------

It is recommended to check that your contribution complies with the following
rules before submitting a pull request:

* All public functions (i.e. functions whose name does not start with an underscore) should have
  informative docstrings with sample usage presented as doctests when appropriate.
* Docstrings are formatted in `NumPy style <https://numpydoc.readthedocs.io/en/latest/format.html>`_.
* Lines are no longer than 120 characters.
* All tests still pass::

    cd /path/to/your/clone/of/heudiconv
    pytest -vvs .

* New code should be accompanied by new tests.
