"""Secret .env files never reach git or the Docker image; .env.example does."""

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
SECRET_FILES = [".env", ".env.local", ".env.production", "config/.env"]
KEPT_FILES = [".env.example"]


def ignored(ignore_file, names, tmp_path):
    """The names git ignores under ignore_file's rules, checked in an empty repo.

    .dockerignore is checked the same way: for its "**/" patterns and "!" exceptions
    Docker and git agree. (Without "**/", Docker would only match at the top level.)
    """
    git = shutil.which("git")
    assert git, "git is needed to run this test"
    subprocess.run([git, "init", "-q", str(tmp_path)], check=True)
    shutil.copy(PROJECT_DIR / ignore_file, tmp_path / ".gitignore")
    result = subprocess.run(
        [git, "-C", str(tmp_path), "check-ignore", "--no-index", *names],
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 1), result.stderr  # 1 means "nothing ignored"
    return set(result.stdout.split())


@pytest.mark.parametrize("ignore_file", [".gitignore", ".dockerignore"])
def test_secret_env_files_are_ignored(ignore_file, tmp_path):
    assert ignored(ignore_file, SECRET_FILES, tmp_path) == set(SECRET_FILES)


@pytest.mark.parametrize("ignore_file", [".gitignore", ".dockerignore"])
def test_env_example_is_kept(ignore_file, tmp_path):
    assert ignored(ignore_file, KEPT_FILES, tmp_path) == set()
