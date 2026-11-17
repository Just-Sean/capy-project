"""The production image: apps from a Git repository can be installed while it's built,
but the image that runs keeps none of the build tools.

The full build is checked by building it (`docker compose ... up --build`); these tests
read the Dockerfile so a change to its stages can't quietly undo either part."""

import re

from tests.test_production_settings import PROJECT_DIR

STAGE = re.compile(r"^FROM\s+\S+\s+AS\s+(\S+)", re.IGNORECASE)
# Anything that installs software: apt or apk packages, pip, or downloads.
INSTALLS = re.compile(r"\b(apt-get|apt|apk|pip|curl|wget|git)\b")
BUILD_ARGUMENT = re.compile(r"^ARG\b", re.IGNORECASE)


def instructions():
    """The Dockerfile's lines, without comments and blank lines."""
    lines = (PROJECT_DIR / "Dockerfile").read_text().splitlines()
    return [line for line in lines if line.strip() and not line.lstrip().startswith("#")]


def stages():
    """{"build": [...its lines...], "runtime": [...]}, by the names after FROM ... AS."""
    found = {}
    name = None
    for line in instructions():
        match = STAGE.match(line)
        if match:
            name = match.group(1).lower()
            found[name] = []
        elif name:
            found[name].append(line)
    return found


def test_the_build_stage_has_git_for_apps_from_a_git_repository():
    build = "\n".join(stages()["build"])
    assert "apt-get install -y --no-install-recommends git" in build
    # git is installed before the dependencies it's needed for.
    assert build.index("install -y --no-install-recommends git") < build.index("uv sync")


def test_the_runtime_image_installs_nothing():
    assert [line for line in stages()["runtime"] if INSTALLS.search(line)] == []


def test_no_build_arguments():
    # Build arguments are saved in the image's history, so secrets must never travel
    # that way (a private repository's login uses a Docker build secret instead).
    assert [line for line in instructions() if BUILD_ARGUMENT.match(line.lstrip())] == []
