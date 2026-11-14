"""No .env file reaches git except .env.example, and none reaches the Docker image.
Private keys (*.pem, *.key) reach neither."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
SECRET_FILES = [
    ".env",
    ".env.local",
    ".env.production",
    ".env.postgres",
    ".envrc",
    "config/.env",
    "server.key",
    "certs/site.pem",
]
SECRET_PATTERNS = (".env", ".pem", ".key")
EXAMPLE = ".env.example"

# Only the copied file's rules count: not this machine's own git settings or ignore list.
ISOLATED_GIT = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def ignored(ignore_file, names, tmp_path):
    """The names git ignores under ignore_file's rules, checked in an empty repo.

    .dockerignore is checked the same way. Git and Docker agree on patterns that start
    with "**/"; without it Docker only matches the top folder, which
    test_dockerignore_secret_rules_cover_every_folder guards against.
    """
    git = shutil.which("git")
    assert git, "git is needed to run this test"
    run = {"env": ISOLATED_GIT, "capture_output": True, "text": True}
    subprocess.run([git, "init", "-q", "--template=", str(tmp_path)], check=True, **run)
    shutil.copy(PROJECT_DIR / ignore_file, tmp_path / ".gitignore")
    command = [git, "-C", str(tmp_path), "-c", "core.excludesFile=", "check-ignore"]
    result = subprocess.run([*command, "--no-index", *names], **run)
    assert result.returncode in (0, 1), result.stderr  # 1 means "nothing ignored"
    return set(result.stdout.split())


@pytest.mark.parametrize("ignore_file", [".gitignore", ".dockerignore"])
def test_secret_env_files_are_ignored(ignore_file, tmp_path):
    assert ignored(ignore_file, SECRET_FILES, tmp_path) == set(SECRET_FILES)


def test_git_keeps_env_example(tmp_path):
    assert ignored(".gitignore", [EXAMPLE], tmp_path) == set()


def test_the_image_gets_no_env_file_at_all(tmp_path):
    # Nothing in the image reads .env.example, so it stays out too.
    assert ignored(".dockerignore", [EXAMPLE, f"config/{EXAMPLE}"], tmp_path) == {
        EXAMPLE,
        f"config/{EXAMPLE}",
    }


def test_dockerignore_secret_rules_cover_every_folder():
    lines = (PROJECT_DIR / ".dockerignore").read_text().splitlines()
    rules = [
        line
        for line in lines
        if not line.startswith("#") and any(pattern in line for pattern in SECRET_PATTERNS)
    ]
    assert len(rules) >= len(SECRET_PATTERNS), f".dockerignore is missing secret rules: {rules}"
    assert all(line.startswith("**/") for line in rules), (
        f"Start these with **/ so Docker matches them in every folder: {rules}"
    )
