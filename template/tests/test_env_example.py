""".env.example lists every environment variable the project reads, and nothing else."""

import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

# Where the project reads environment variables, and how each file reads them:
# settings use django-environ (env("NAME"), env.bool("NAME", ...)), Gunicorn uses
# os.environ.get("NAME", ...), and compose uses ${NAME} or ${NAME:-default}.
READERS = {
    "config/settings.py": re.compile(r"\benv(?:\.\w+)?\(\s*\"([A-Z][A-Z0-9_]*)\""),
    "gunicorn.conf.py": re.compile(r"os\.environ(?:\.get)?\(\s*\"([A-Z][A-Z0-9_]*)\""),
    "compose.yaml": re.compile(r"\$\{([A-Z][A-Z0-9_]*)"),
}

# A variable in .env.example: "NAME=value", or commented out as "# NAME=value".
LISTED = re.compile(r"^#?\s*([A-Z][A-Z0-9_]*)=", re.MULTILINE)


def variables_read():
    names = set()
    for file, pattern in READERS.items():
        names |= set(pattern.findall((PROJECT_DIR / file).read_text()))
    return names


def variables_listed():
    return set(LISTED.findall((PROJECT_DIR / ".env.example").read_text()))


def test_the_readers_still_find_variables():
    # Guards the test itself: if the patterns stopped matching, everything would pass.
    assert {"DJANGO_SECRET_KEY", "DATABASE_URL", "WEB_CONCURRENCY", "POSTGRES_PORT"} <= (
        variables_read()
    )


def test_every_variable_the_project_reads_is_listed():
    missing = sorted(variables_read() - variables_listed())
    assert missing == [], f"Add these to .env.example, with what they're for: {missing}"


def test_every_listed_variable_is_read_somewhere():
    unused = sorted(variables_listed() - variables_read())
    assert unused == [], f"Nothing reads these; remove them from .env.example: {unused}"
