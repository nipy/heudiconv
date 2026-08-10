"""Assorted constants describing the project.

Packaging metadata (dependencies, classifiers, entry points, ...) lives in
``pyproject.toml``; only values needed at run time belong here.
"""

__author__ = "HeuDiConv team and contributors"
__url__ = "https://github.com/nipy/heudiconv"
__packagename__ = "heudiconv"
__description__ = "Heuristic DICOM Converter"

# Keep in sync with the "datalad" extra in pyproject.toml
MIN_DATALAD_VERSION = "0.13.0"
