"""
A Python module for managing configurations across a heudiconv run.
"""

import atexit
import os
from pathlib import Path


# avoid telemetry check if user desires
_disable_et = bool(
    os.getenv("NO_ET") is not None
    or os.getenv("NIPYPE_NO_ET") is not None
)
os.environ["NIPYPE_NO_ET"] = "1"
os.environ["NO_ET"] = "1"
_latest_version = "Unknown"

if not _disable_et:
    # Ensure analytics hit only once
    from contextlib import suppress
    from requests import get, ConnectionError, ReadTimeout
    with suppress((ConnectionError, ReadTimeout)):
        res = get("https://rig.mit.edu/et/projects/nipy/heudiconv", timeout=0.1)
    try:
        _latest_version = res.json()['version']
    except Exception:
        pass


class _Config:
    """An abstract class forbidding instantiation."""

    _paths = tuple()

    def __init__(self):
        """Avert instantiation."""
        raise RuntimeError('Configuration type is not instantiable.')

    @classmethod
    def load(cls, settings, init=True):
        """Store settings from a dictionary."""
        for k, v in settings.items():
            if v is None:
                continue
            if k in cls._paths:
                setattr(cls, k, Path(v).absolute())
                continue
            if k in cls._multipaths:
                setattr(cls, k, tuple(Path(i).absolute() for i in v))
            if hasattr(cls, k):
                setattr(cls, k, v)

        if init:
            try:
                cls.init()
            except AttributeError:
                pass

    @classmethod
    def get(cls):
        """Return defined settings."""
        out = {}
        for k, v in cls.__dict__.items():
            if k.startswith('_') or v is None:
                continue
            if callable(getattr(cls, k)):
                continue
            if k in cls._paths:
                v = str(v)
            if k in cls._multipaths:
                v = tuple(str(i) for i in v)
            out[k] = v
        return out


class workflow(_Config):
    """Configure run-level settings."""

    _paths = (
        'dcmconfig',
        'outdir',
        'conv_outdir',
    )
    _multipaths = (
        'files',
    )

    dicom_dir_template = None
    "Template to search one or more directories for DICOMs and tarballs."
    files = None
    "Files (tarballs, DICOMs) or directories containing files to process."
    subjs = None
    "List of target subject IDs."
    converter = None
    "Tool to use for DICOM conversion."
    outdir = Path('.').absolute()
    "Output directory for conversion."
    locator = None
    "Study path under ``outdir``."
    conv_outdir = None
    "Anonymization output directory for converted files."
    anon_cmd = None
    "Command to run to anonymize subject IDs."
    heuristic = None
    "Path to custom file or name of built-in heuristic."
    with_prov = False
    "Store additional provenance information."
    session = None
    "Session for longitudinal studies."
    bids = None
    "Generate relevant BIDS files."
    overwrite = False
    "Overwrite existing converted files."
    datalad = False
    "Store the entire collection as DataLad datasets."
    debug = False
    "Do not catch exceptions and show traceback."
    grouping = None
    "DICOM grouping method."
    minmeta = None
    "Minimize BIDS sidecar metadata."
    random_seed = None
    "Random seed to initialize PRNG."
    dcmconfig = None
    "JSON file for additional dcm2niix configuration."
    queue = None
    "Batch system to submit jobs in parallel."
    queue_args = None
    "Additional queue arguments."

    @classmethod
    def init(cls):
        """Initialize heudiconv execution"""
        from .utils import load_heuristic

        if cls.heuristic is not None:
            cls.heuristic = load_heuristic(cls.heuristic)
        if cls.random_seed is not None:
            _init_seed(cls.random_seed)


def from_dict(settings):
    """Read and load settings from a flat dictionary."""
    workflow.load(settings)


def get(flat=False):
    """Get config as a dict."""
    settings = {
        'workflow': workflow.get(),
    }
    if not flat:
        return settings

    return {'.'.join((section, k)): v
            for section, configs in settings.items()
            for k, v in configs.items()}


def _init_seed(seed):
    import random
    import numpy as np
    random.seed(seed)
    np.random.seed(seed)


def add_tmpdir(tmpdir):
    """Track temporary directories"""
    _tmpdirs.add(tmpdir)


def _cleanup():
    """Cleanup tracked temporary directories"""
    for tmpdir in _tmpdirs:
        tmpdir.cleanup()


_tmpdirs = set()
# ensure cleanup of temporary directories occurs at exit
atexit.register(_cleanup)
