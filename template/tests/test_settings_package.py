"""config/settings/: the topic files combine into one set of settings, without one
topic silently overriding another, and a leftover config/settings.py is refused."""

from collections import defaultdict
from pathlib import Path

import pytest
from django.conf import settings

import config.settings as combined
from config.settings import core, database, environment, files, logs, security, users
from tests.test_production_settings import run_manage

TOPICS = [environment, core, database, users, files, security, logs]
PROJECT_DIR = Path(__file__).resolve().parent.parent
SETTINGS_DIR = PROJECT_DIR / "config" / "settings"


def uppercase_names(module):
    return [name for name in vars(module) if name.isupper()]


def test_base_dir_is_the_project_folder():
    assert settings.BASE_DIR == PROJECT_DIR


def test_every_topic_file_is_combined():
    # A new topic file is ignored until it's added to config/settings/__init__.py.
    on_disk = {path.stem for path in SETTINGS_DIR.glob("*.py")} - {"__init__"}
    assert on_disk == {topic.__name__.rsplit(".", 1)[1] for topic in TOPICS}


def test_every_topics_settings_reach_django():
    # Compared with config.settings itself: during tests Django adjusts a few of its own
    # copies (it adds "testserver" to ALLOWED_HOSTS, for example).
    for topic in TOPICS:
        for name in uppercase_names(topic):
            assert getattr(combined, name) is getattr(topic, name), f"{topic.__name__}.{name}"
    assert settings.SETTINGS_MODULE == "config.settings"


def test_no_setting_is_set_differently_in_two_topics():
    # A topic may read another's setting (the same object); setting it again to something
    # else would mean the later topic silently wins.
    values = defaultdict(list)
    for topic in TOPICS:
        for name in uppercase_names(topic):
            if not any(value is getattr(topic, name) for value in values[name]):
                values[name].append(getattr(topic, name))
    assert [name for name, found in values.items() if len(found) > 1] == []


@pytest.fixture
def leftover_settings_file():
    leftover = PROJECT_DIR / "config" / "settings.py"
    leftover.write_text("DEBUG = True  # an old setting that would be silently ignored\n")
    try:
        yield leftover
    finally:
        leftover.unlink()


def test_a_leftover_settings_file_is_refused(leftover_settings_file):
    result = run_manage("check")
    assert result.returncode != 0
    assert "config/settings.py is no longer used" in result.stderr
