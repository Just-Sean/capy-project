""".env.example lists every environment variable the project reads, and nothing else.

"Reads" means the project's Python files (all of them except tests, migrations and
virtualenvs) and its compose files. A variable only the Dockerfile sets isn't read, so
it isn't listed.
"""

import io
import os
import re
import sys
import tokenize
from collections import Counter
from pathlib import Path

import environ
import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
# Also skipped: hidden folders (.venv, .git) and any folder holding a virtualenv.
SKIPPED_FOLDERS = {"tests", "migrations"}

# Python: env("NAME"), env.bool("NAME", ...), env.str(var="NAME"), os.environ["NAME"],
# os.environ.get("NAME"), os.getenv("NAME") (or environ/getenv imported from os), either
# quote style. Not os.environ.setdefault(...), which sets a variable, and not
# request.environ, which holds a web request's details. Only a name written out in
# quotes is found: env.db() with no name reads DATABASE_URL unseen, so always pass the
# name.
PYTHON_READ = re.compile(
    r"""(?:\benv(?:\.\w+)?\(|(?:\bos\.|(?<![\w.]))(?:environ\.get\(|environ\[|getenv\())"""
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
LISTED = re.compile(r"^(?:#+[ \t]*)?(?:export )?([A-Z][A-Z0-9_]*)=(\S*)[ \t]*$", re.MULTILINE)
# A line django-environ loads as written: NAME=value at the start of the line, with no
# spaces, quotes or comment in the value. ("export " takes exactly one space.)
ACTIVE = re.compile(r"(?:export )?[A-Z][A-Z0-9_]*=[^\s\"']*")

# django-environ reads any word it doesn't recognize as false, so a typo like "ture"
# would silently turn a setting off.
BOOL_READ = re.compile(r"""\benv\.bool\(\s*(?:var\s*=\s*)?["']([A-Z][A-Z0-9_]*)["']""")
TRUE_FALSE_WORDS = {*environ.Env.BOOLEAN_TRUE_STRINGS, "false", "off", "no", "n", "0"}
DJANGO_ENVS = {"development", "test", "production"}  # as in config/settings/environment.py


def without_comments(source):
    """Python source with its comments blanked out, so commented-out code isn't a read."""
    lines = source.split("\n")  # the same rows tokenize counts (not splitlines())
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            (row, start), (_, end) = token.start, token.end
            line = lines[row - 1]
            lines[row - 1] = line[:start] + " " * (end - start) + line[end:]
    return "\n".join(lines)


def read_in_python(source):
    return set(PYTHON_READ.findall(without_comments(source)))


def read_in_compose(text):
    return set(COMPOSE_READ.findall(YAML_COMMENT.sub("", text)))


def listed_in(text):
    return [name for name, _ in LISTED.findall(text)]


def values_in(text):
    """Each listed variable's value, whether the line is commented out or not."""
    return dict(LISTED.findall(text))


def is_test_file(name):
    # The files pytest collects (pyproject.toml's python_files), plus conftest.py.
    return name in ("tests.py", "conftest.py") or name.startswith("test_")


def python_files():
    for folder, subfolders, files in os.walk(PROJECT_DIR):
        subfolders[:] = [
            name
            for name in subfolders
            if not name.startswith(".")
            and name not in SKIPPED_FOLDERS
            and not Path(folder, name, "pyvenv.cfg").exists()
        ]
        for name in files:
            if name.endswith(".py") and not is_test_file(name):
                yield Path(folder, name)


def found_in_python_files(pattern):
    names = set()
    for file in python_files():
        try:
            with tokenize.open(file) as handle:  # honors a file's declared encoding
                names |= set(pattern.findall(without_comments(handle.read())))
        except (SyntaxError, UnicodeDecodeError, tokenize.TokenError) as error:
            pytest.fail(f"Can't scan {file.relative_to(PROJECT_DIR)}: {error}")
    return names


def variables_read():
    names = found_in_python_files(PYTHON_READ)
    for file in PROJECT_DIR.glob("compose*.yaml"):
        names |= read_in_compose(file.read_text())
    return names


def env_example():
    return (PROJECT_DIR / ".env.example").read_text()


def variables_listed():
    return listed_in(env_example())


def lines_django_environ_would_misread(text):
    """Line numbers of lines that aren't blank, a comment or a plain NAME=value. An
    indented variable isn't loaded, and a comment after a value becomes part of it.
    Spaces and quotes in values are refused too, to keep the file simple."""
    return [
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip() and not line.startswith("#") and not ACTIVE.fullmatch(line)
    ]


def shows_a_real_environment(text):
    return values_in(text).get("DJANGO_ENV") in DJANGO_ENVS


def wrong_true_false_values(text, true_false_names):
    """Names of true/false variables whose value, commented out or not (it gets
    uncommented as it is), isn't a word django-environ knows."""
    values = values_in(text)
    return sorted(
        name
        for name in true_false_names & values.keys()
        if values[name].lower() not in TRUE_FALSE_WORDS
    )


def names_django_environ_loads(text, monkeypatch):
    loaded = {}
    monkeypatch.setattr(environ.Env, "ENVIRON", loaded)
    environ.Env.read_env(io.StringIO(text))
    return set(loaded)


# --- The real .env.example -------------------------------------------------------


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
        "with no spaces or quotes in the value and no comment after it"
    )


def test_every_listed_variable_loads_once_uncommented(monkeypatch):
    uncommented = "\n".join(
        line.lstrip("#").lstrip() if listed_in(line) else line
        for line in env_example().splitlines()
    )
    loaded = names_django_environ_loads(uncommented, monkeypatch)
    not_loaded = sorted(set(variables_listed()) - loaded)
    assert not_loaded == [], f"django-environ wouldn't load these: {not_loaded}"


def test_django_env_shows_a_real_environment():
    assert shows_a_real_environment(env_example())


def test_true_false_values_are_words_django_environ_knows():
    wrong = wrong_true_false_values(env_example(), found_in_python_files(BOOL_READ))
    assert wrong == [], f"Use true or false for these in .env.example: {wrong}"


def test_the_worker_count_shown_is_gunicorns_default():
    # .env.example shows WEB_CONCURRENCY commented out at its default, so it must say
    # what gunicorn.conf.py really uses when the variable isn't set.
    config = (PROJECT_DIR / "gunicorn.conf.py").read_text()
    found = re.search(r"""WEB_CONCURRENCY["'],\s*["'](\d+)["']""", config)
    assert found, (
        "gunicorn.conf.py no longer reads WEB_CONCURRENCY with a default: update this test"
    )
    default = found.group(1)
    assert values_in(env_example())["WEB_CONCURRENCY"] == default
    assert f"Default {default}." in env_example()


# --- The helpers themselves ------------------------------------------------------


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
        'A = getenv("X")',
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
        'host = request.environ.get("X")',
        'path = request.environ["X"]',
    ],
)
def test_python_non_reads_are_ignored(source):
    assert read_in_python(source) == set()


@pytest.mark.parametrize("separator", ["\x0c", ""])
def test_unusual_line_breaks_dont_shift_comment_blanking(separator):
    source = f'S = "a{separator}b"\nA = 1\nB = env("X")  # was env("Y")\n'
    assert read_in_python(source) == {"X"}


@pytest.mark.parametrize("text", ["p: ${X}", 'p: "${X:-5432}"', "p: $X"])
def test_compose_reads_are_found(text):
    assert read_in_compose(text) == {"X"}


@pytest.mark.parametrize("text", ["p: $${X}", "# p: ${X}", "p: 1  # ${X}"])
def test_compose_non_reads_are_ignored(text):
    assert read_in_compose(text) == set()


def test_scans_project_code_but_not_tests_or_virtualenvs(tmp_path, monkeypatch):
    files = {
        "billing/client.py": 'KEY = os.environ["APP_KEY"]',
        "billing/test_client.py": 'os.environ["TEST_ONLY"]',
        "conftest.py": 'os.environ["CONFTEST_ONLY"]',
        "venv/pyvenv.cfg": "",
        "venv/lib/site.py": 'os.environ["VENV_ONLY"]',
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    monkeypatch.setattr(sys.modules[__name__], "PROJECT_DIR", tmp_path)
    assert found_in_python_files(PYTHON_READ) == {"APP_KEY"}


def test_a_file_that_cant_be_scanned_is_named(tmp_path, monkeypatch):
    (tmp_path / "broken.py").write_text('A = """never closed\n')
    monkeypatch.setattr(sys.modules[__name__], "PROJECT_DIR", tmp_path)
    with pytest.raises(pytest.fail.Exception, match="broken.py"):
        found_in_python_files(PYTHON_READ)


def test_a_declared_encoding_is_honored(tmp_path, monkeypatch):
    source = '# -*- coding: latin-1 -*-\nNAME = "café"\nA = env("X")\n'
    (tmp_path / "old.py").write_bytes(source.encode("latin-1"))
    monkeypatch.setattr(sys.modules[__name__], "PROJECT_DIR", tmp_path)
    assert found_in_python_files(PYTHON_READ) == {"X"}


@pytest.mark.parametrize(
    "line", ["X=1", "X=", "# X=1", "#X=1", "## X=1", "export X=1", "# X=postgres://a:b@c/d"]
)
def test_variable_lines_are_listed(line):
    assert listed_in(line) == ["X"]


@pytest.mark.parametrize(
    "line",
    ["  X=1", "# X=true turns it on", "X=1  # a note", "# Set X to false.", "export  X=1"],
)
def test_other_lines_are_not_listed(line):
    assert listed_in(line) == []


def test_values_are_read_from_commented_and_uncommented_lines():
    assert values_in("A=1\n# B=true\n") == {"A": "1", "B": "true"}


@pytest.mark.parametrize(
    "line",
    ["  X=1", "X=1  # a note", "X=a b", 'X="a"', "export  X=1", "export\tX=1", "  # indented"],
)
def test_lines_django_environ_would_misread_are_caught(line):
    assert lines_django_environ_would_misread(f"# fine\n\nY=2\n{line}\n") == [4]


@pytest.mark.parametrize("text", ["X=1", "export X=1", "X=postgres://a:b@c:5432/d"])
def test_lines_the_test_accepts_are_loaded(text, monkeypatch):
    assert lines_django_environ_would_misread(text) == []
    assert names_django_environ_loads(text, monkeypatch) == {"X"}


@pytest.mark.parametrize(
    ("text", "real"),
    [
        ("DJANGO_ENV=development", True),
        ("# DJANGO_ENV=production", True),
        ("DJANGO_ENV=prod", False),
        ("DJANGO_ENV=", False),
        ("# no DJANGO_ENV here", False),
    ],
)
def test_shows_a_real_environment(text, real):
    assert shows_a_real_environment(text) is real


@pytest.mark.parametrize(
    ("value", "wrong"),
    [("true", []), ("False", []), ("0", []), ("on", []), ("ture", ["X"]), ("", ["X"])],
)
def test_wrong_true_false_values_are_caught(value, wrong):
    assert wrong_true_false_values(f"# X={value}\nY=whatever\n", {"X"}) == wrong


def test_true_false_reads_are_found():
    source = 'A = env.bool("X", default=True)\nB = env("Y")\n# C = env.bool("Z")\n'
    assert set(BOOL_READ.findall(without_comments(source))) == {"X"}
