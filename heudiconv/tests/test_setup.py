"""Tests for the build-time helpers in setup.py

They are not exercised by the doctest collection, since pytest never collects
the setup.py sitting in the rootdir.
"""

from __future__ import annotations

import doctest
import importlib.util
from pathlib import Path
import re
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
SETUP_PY = REPO_ROOT / "setup.py"


@pytest.fixture(scope="module")
def setup_py() -> ModuleType:
    if not SETUP_PY.exists():
        pytest.skip(f"No {SETUP_PY} -- not running from a source checkout")
    spec = importlib.util.spec_from_file_location("heudiconv_setup", SETUP_PY)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.ai_generated
def test_setup_doctests(setup_py: ModuleType) -> None:
    results = doctest.testmod(setup_py)
    assert results.failed == 0


@pytest.mark.ai_generated
def test_readme_is_absolutized(setup_py: ModuleType) -> None:
    """No link should be left relative in the rendered long description"""
    rendered = setup_py.absolutize_links((REPO_ROOT / "README.rst").read_text())
    # every regex only matches links which are still relative
    for regex, _ in setup_py.LINK_RES:
        assert re.search(regex, rendered) is None, f"{regex} still matches"
    # and thus rendering the rendered README changes nothing
    assert setup_py.absolutize_links(rendered) == rendered
