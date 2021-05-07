import logging
import tempfile


class TempDirs:
    """A helper to centralize handling and cleanup of dirs"""

    dirs = set()
    lgr = logging.getLogger('heudiconv.tempdirs')

    def __init__(self):
        import atexit
        atexit.register(self.cleanup)

    def add_tmpdir(self, prefix=None):
        tmpdir = tempfile.mkdtemp(prefix=prefix)
        self.dirs.add(tmpdir)
        return tmpdir

    def cleanup(self):
        """Cleanup tracked temporary directories"""
        import shutil

        self.lgr.debug("Removing %d temporary directories", len(self.dirs))
        for tmpdir in self.dirs:
            try:
                self.lgr.debug("Removing %s", tmpdir)
                shutil.rmtree(tmpdir)
            except FileNotFoundError:
                pass


tmpdirs = TempDirs()
