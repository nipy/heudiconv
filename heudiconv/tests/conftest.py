import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def git_env() -> None:
    os.environ["GIT_AUTHOR_EMAIL"] = "maxm@example.com"
    os.environ["GIT_AUTHOR_NAME"] = "Max Mustermann"
    os.environ["GIT_COMMITTER_EMAIL"] = "maxm@example.com"
    os.environ["GIT_COMMITTER_NAME"] = "Max Mustermann"
