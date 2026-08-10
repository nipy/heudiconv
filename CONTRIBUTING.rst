=========================
Contributing to HeuDiConv
=========================

Quick reference
---------------

::

    pip install -e .[all]        # install HeuDiConv and all its dependencies in editable mode
    pip install pre-commit       # then `pre-commit install` to format/lint on every commit

    pytest -v heudiconv          # run the test suite
    pytest -v -k test_name ...   # run a subset of the tests
    pytest -v -m ai_generated .  # run only the tests marked as AI-generated

    tox                          # run linting, type checking, and tests as CI would
    tox -e lint                  # flake8 + codespell only
    tox -e typing                # mypy only

The sections below describe each of those in more detail.

Files organization
------------------

* `heudiconv/ <./heudiconv>`_ is the main Python module where major development is happening, with
  major submodules being:

  - ``cli/`` - wrappers and argument parsers bringing the HeuDiConv functionality to the command
    line.
  - ``external/`` - general compatibility layers for external functions HeuDiConv depends on.
  - ``heuristics/`` - heuristic evaluators for workflows, pull requests here are particularly
    welcome.
  - ``tests/`` - the test suite, along with the small DICOM/NIfTI samples it operates on.

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
    * minor: Increment the minor version when merged
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

We support Python 3 only (>= 3.9), and test against all Python versions from 3.9 through 3.13.

Dependencies which you will need are listed in `pyproject.toml <./pyproject.toml>`_.
Note that you will likely have these will already be available on your system if you used a
package manager (e.g. Debian's ``apt-get``, Gentoo's ``emerge``, or simply PIP) to install the
software.

HeuDiConv also calls out to a number of external tools, most notably ``dcm2niix``, and some tests
additionally need ``git-annex`` and ``datalad``.  All of them are nowadays installable from PyPI,
so a plain virtualenv is enough to get a complete development environment::

  pip install dcm2niix git-annex

`dcm2niix <https://pypi.org/project/dcm2niix/>`__ and
`git-annex <https://pypi.org/project/git-annex/>`__ are wheels bundling the corresponding binaries
for common platforms; ``datalad`` is pulled in by the ``datalad`` (and hence ``all``) extra of
HeuDiConv itself.  You may of course still prefer to obtain them from your system package manager
(e.g. NeuroDebian, conda, or Homebrew) if you already have those set up.

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


Code style
----------

Formatting and linting are automated; do not hand-tune style.  Install the hooks once::

    pip install pre-commit
    pre-commit install

and every commit will then be checked with `black <https://black.readthedocs.io>`_ (formatting),
`isort <https://pycqa.github.io/isort/>`_ (import sorting), `flake8 <https://flake8.pycqa.org>`_
(linting), and `codespell <https://github.com/codespell-project/codespell>`_ (typos).  You can run
them all against the whole tree at any point with ``pre-commit run -a``, and the linting subset via
``tox -e lint``.  Their configuration lives in ``.pre-commit-config.yaml``, ``tox.ini``, and
``.codespellrc``.

Beyond what the tools enforce:

* **Do not duplicate code.**  Copy-pasted logic is the single most reliable way to introduce bugs
  into this codebase: the copies inevitably diverge, a fix lands in one of them and not the others,
  and the discrepancy is then found by users rather than by us.  If you catch yourself
  copy-pasting, factor the common part out into a helper instead — even for two occurrences, and
  even when the copies differ in small ways (that is what arguments are for).  This applies with
  equal force to tests, docs, and heuristics, not just to library code.
* HeuDiConv is fully type-annotated and ships a ``py.typed`` marker.  New functions must have
  annotated arguments and return values; ``mypy`` is run in CI and can be run locally with
  ``tox -e typing``.
* All public functions (i.e. functions whose name does not start with an underscore) should have
  informative docstrings with sample usage presented as doctests when appropriate.  Note that
  ``pytest`` is configured with ``--doctest-modules``, so doctests are collected and executed as
  part of the test suite.
* Docstrings are formatted in `NumPy style <https://numpydoc.readthedocs.io/en/latest/format.html>`_.
* Line length is whatever ``black`` produces (88 columns); ``flake8`` is configured to ignore
  ``E501``, so the occasional long URL or string literal is tolerated rather than mangled.

Testing
-------

New code should be accompanied by new tests, and all tests should pass before you submit a pull
request::

    cd /path/to/your/clone/of/heudiconv
    pytest -v heudiconv

The suite lives in ``heudiconv/tests/`` (plus per-submodule test files) and is built on
`pytest <https://docs.pytest.org>`_.  A number of tests need external tools (``dcm2niix``,
``git-annex``, ``datalad``) and will be skipped if those are unavailable, so a fully green local
run may still cover less than CI does.

The no-duplication rule above applies to tests in particular.  Whenever a set of tests differ only
in their inputs and expected outputs, express them as a **single**
`parametrized <https://docs.pytest.org/en/stable/how-to/parametrize.html>`_ test rather than as
several near-identical functions::

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0.02, True),  # 2% difference - compatible
            (0.03, True),
            (0.10, False),
        ],
    )
    def test_something(value: float, expected: bool) -> None:
        assert check(value) is expected

Adding a case then costs one line, every case is exercised by the same assertions, and a failure
reports which case broke.  Shared setup belongs in a fixture for the same reason.

To reproduce the full CI matrix of linting, type checking, and tests in one go, run ``tox``.

AI-assisted contributions
-------------------------

Contributions developed with the help of AI assistants (Claude Code, Copilot, etc.) are welcome,
subject to the same review bar as any other contribution: you are the author, and you are
responsible for understanding, verifying, and standing behind every line you submit.

**Any test which was generated by an AI assistant must be marked** with the ``ai_generated``
marker, which is registered in ``tox.ini``::

    import pytest

    @pytest.mark.ai_generated
    def test_something() -> None:
        ...

Mark the test if the assistant wrote the bulk of it, even if you subsequently edited it; there is
no need to mark a hand-written test that merely received an AI-suggested tweak.  For a
parametrized test, place the marker on the test function alongside the ``parametrize`` decorators.
The marker is purely informational — such tests run as part of the normal suite — but it lets us
filter them::

    pytest -v -m ai_generated .        # only AI-generated tests
    pytest -v -m "not ai_generated" .  # everything else

This matters because AI-generated tests have a characteristic failure mode: they can encode the
implementation's current behavior rather than the behavior we actually want, and so pass while
asserting the wrong thing.  Being able to identify them makes it feasible to revisit them when the
underlying behavior is questioned.  Please double-check that such tests would indeed fail without
the accompanying change.

Assistants also have a strong tendency to emit a pile of copy-pasted test functions where one
parametrized test would do, so the no-duplication rule needs enforcing especially firmly here.
Before submitting AI-assisted tests, read them over and collapse any near-identical functions into
a single ``@pytest.mark.parametrize``\ d test, hoist repeated setup into a fixture, and delete the
cases which are not actually distinct.  Reviewers will ask for this, so it is cheaper to do it up
front — and it is a good forcing function for the understanding you are expected to have of the
code you submit.

If an assistant was used substantially for the non-test portion of a change as well, please say so
in the pull request description.  Do not paste in code you do not understand or cannot explain in
review.
