"""Track archive sources while their extracted files are in use."""

from __future__ import annotations

import atexit
import os.path as op
from pathlib import Path
from typing import Optional

from .utils import TempDirs


class _ArchiveTempDirs(TempDirs):
    def __init__(self) -> None:
        super().__init__()
        self._archives: dict[str, str] = {}

    def __call__(
        self, prefix: Optional[str] = None, *, archive: Optional[str] = None
    ) -> str:
        directory = super().__call__(prefix)
        if archive is not None:
            self._archives[directory] = op.abspath(archive)
        return directory

    def source_path(self, filename: str) -> str:
        """Return an archive/member reference, or the original unarchived path.

        Archive references use the absolute archive filename as a directory,
        followed by the member's relative path. They identify the source and
        are independent of the temporary extraction directory.
        """
        for parent in Path(filename).parents:
            archive = self._archives.get(str(parent))
            if archive is not None:
                return op.join(archive, op.relpath(filename, parent))
        return filename

    def rmtree(self, tmpdir: str) -> None:
        super().rmtree(tmpdir)
        self._archives.pop(tmpdir, None)


tempdirs = _ArchiveTempDirs()
atexit.register(tempdirs.cleanup)
