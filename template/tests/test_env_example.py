""".env.example lists every environment variable the project reads, and nothing else.

"Reads" means the project's Python files (all of them except tests and migrations)
and its compose files. A variable only the Dockerfile sets isn't read, so it isn't
listed.
"""

import io
import os
import re
import tokenize
from collections import Counter
from pathlib import Path

import environ
import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
SKIPPED_FOLDERS = {"tests", "migrations"}  # plus hidden folders such as .venv and .git

# Python: env("NAME"), env.bool("NAME", ...), env.str(var="NAME"), os.environ["NAME"],
# os.environ.get("NAME"), os.getenv("NAME"), either quote style. Not
# os.environ.setdefault(...): that sets a variable instead of reading one.
PYTHON_READ = re.compile(
    r"""(?:\benv(?:\.\w+)?\(|\benviron\.get\(|\benviron\[|\bgetenv\()"""
    r"""\s*(?:var\s*=\s*)?["']([A-Z][A-Z0-9_]*)["']"""
)
# Compose: ${NAME}, ${NAME:-default} or $NAME. Not $$NAME, which compose treats as a
# literal "$".
COMPOSE_READ = re.compile(r"(?<!\$)\$\{?([A-Z][A-Z0-9_]*)")
YAML_COMMENT = re.compile(r"(?:^|(?<=\s))#.*", re.MULTILINE)

# A variable line in .env.example: NAME=value, export NAME=value, or commented out as
# # NAME=value. It starts the line and has nothing after the value, so a sentence in a
# comment that happens to contain NAME=value doesn't count. An indented line doesn't
# count either: django-environ doesn't load it.
LISTED = re.compile(r"^(?:#+[ \t]*)?(?:export[ \t]+)?([A-Z][A-Z0-9_]*)=(\S*)[ \t]*$", re.MULTILINE)
# A line django-environ loads: NAME=value at the start of the line, nothing after it.
ACTIVE = re.compile(r"(?:export[ \t]+)?[A-Z][A-Z0-9_]*=\S*")

# django-environ reads any word it doesn't recognize as false, so a typo like "ture"
# would silently turn a setting off.
BOOL_READ = re.compile(r"""\benv\.bool\(\s*(?:var\s*=\s*)?["']([A-Z][A-Z0-9_]*)["']""")
TRUE_FALSE_WORDS = {*environ.Env.BOOLEAN_TRUE_STRINGS, "false", "off", "no", "n", "0"}
DJANGO_ENVS = {"development", "test", "production"}


def without_comments(source):
    """Python source with its comments blanked out, so commented-out code isn't a read."""
    lines = source.splitlines(keepends=True)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            (row, start), (_, end) = token.start, token.end
            line = lines[row - 1]
            lines[row - 1] = line[:start] + " " * (end - start) + line[end:]
    return "".join(lines)


def read_in_python(source):
    return set(PYTHON_READ.findall(without_comments(source)))


def read_in_compose(text):
    return set(COMPOSE_READ.findall(YAML_COMMENT.sub("", text)))


def listed_in(text):
    return [name for name, _ in LISTED.findall(text)]


def values_in(text):
    """Each listed variable's value, whether the line is commented out or not."""
    return dict(LISTED.findall(text))


def python_files():
    for folder, subfolders, files in os.walk(PROJECT_DIR):
        subfolders[:] = [
            name for name in subfolders if not name.startswith(".") and name not in SKIPPED_FOLDERS
        ]
        for name in files:
            if name.endswith(".py") and name != "tests.py":
                yield Path(folder, name)


def variables_read():
    names = set()
    for file in python_files():
        names |= read_in_python(file.read_text())
    for file in PROJECT_DIR.glob("compose*.yaml"):
        names |= read_in_compose(file.read_text())
    return names


def true_false_variables():
    names = set()
    for file in python_files():
        names |= set(BOOL_READ.findall(without_comments(file.read_text())))
    return names


def env_example():
    return (PROJECT_DIR / ".env.example").read_text()


def variables_listed():
    return listed_in(env_example())


def lines_django_environ_would_misread(text):
    """Line numbers of lines that aren't blank, a comment or a plain NAME=value: an
    indented variable isn't loaded, and a comment after a value becomes part of it."""
    return [
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip() and not line.startswith("#") and not ACTIVE.fullmatch(line)
    ]


def test_the_readers_still_find_variables():
    # Guards the test itself: if the patterns stopped matching, everything would pass.
    assert {"DJANGO_SECRET_KEY", "DATABASE_URL", "WEB_CONCURRENCY", "POSTGRES_PORT"} <= (
        variables_read()
    )


def test_every_variable_the_project_reads_is_listed():
    missing = sorted(variables_read() - set(variables_listed()))
    assert missing == [], f"Add these to .env.example, with what they're for: {missing}"


def test_every_listed_variable_is_read_somewhere():
    unused = sorted(set(variables_listed()) - variables_read())
    assert unused == [], f"Nothing reads these; remove them from .env.example: {unused}"


def test_each_variable_is_listed_once():
    twice = sorted(name for name, count in Counter(variables_listed()).items() if count > 1)
    assert twice == [], f"Listed more than once in .env.example: {twice}"


def test_every_line_is_blank_a_comment_or_a_variable():
    misread = lines_django_environ_would_misread(env_example())
    assert misread == [], (
        f"Lines {misread} of .env.example: write NAME=value at the start of the line, "
        "with no comment after the value"
    )


def test_django_env_shows_a_real_environment():
    assert values_in(env_example()).get("DJANGO_ENV") in DJANGO_ENVS


def test_true_false_values_are_words_django_environ_knows():
    # Checks commented-out values too: they get uncommented as they are.
    values = values_in(env_example())
    wrong = sorted(
        name
        for name in true_false_variables() & values.keys()
        if values[name].lower() not in TRUE_FALSE_WORDS
    )
    assert wrong == [], f"Use true or false for these in .env.example: {wrong}"


# --- The patterns themselves ------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        'A = env("X")',
        "A = env('X')",
        'A = env.bool("X", default=True)',
        'A = env.str(var="X")',
        'A = env(\n    # what it is\n    "X",\n)',
        'A = os.environ["X"]',
        'A = os.environ.get("X", "1")',
        'A = os.getenv("X")',
        'A = environ.get("X")',
    ],
)
def test_python_reads_are_found(source):
    assert read_in_python(source) == {"X"}


@pytest.mark.parametrize(
    "source",
    [
        'os.environ.setdefault("X", "config.settings")',
        '# A = env("X")',
        'A = 1  # was env("X")',
        "A = environ.Env()",
    ],
)
def test_python_non_reads_are_ignored(source):
    assert read_in_python(source) == set()


@pytest.mark.parametrize("text", ["p: ${X}", 'p: "${X:-5432}"', "p: $X"])
def test_compose_reads_are_found(text):
    assert read_in_compose(text) == {"X"}


@pytest.mark.parametrize("text", ["p: $${X}", "# p: ${X}", "p: 1  # ${X}"])
def test_compose_non_reads_are_ignored(text):
    assert read_in_compose(text) == set()


@pytest.mark.parametrize(
    "line", ["X=1", "X=", "# X=1", "#X=1", "## X=1", "export X=1", "# X=postgres://a:b@c/d"]
)
def test_variable_lines_are_listed(line):
    assert listed_in(line) == ["X"]


@pytest.mark.parametrize(
    "line", ["  X=1", "# X=true turns it on", "X=1  # a note", "# Set X to false."]
)
def test_other_lines_are_not_listed(line):
    assert listed_in(line) == []


def test_values_are_read_from_commented_and_uncommented_lines():
    assert values_in("A=1\n# B=true\n") == {"A": "1", "B": "true"}


@pytest.mark.parametrize("line", ["  X=1", "X=1  # a note", "X=a b", "  # indented comment"])
def test_lines_django_environ_would_misread_are_caught(line):
    assert lines_django_environ_would_misread(f"# fine\n\nY=2\n{line}\n") == [4]


def test_true_false_reads_are_found():
    source = 'A = env.bool("X", default=True)\nB = env("Y")\n# C = env.bool("Z")\n'
    assert set(BOOL_READ.findall(without_comments(source))) == {"X"}
