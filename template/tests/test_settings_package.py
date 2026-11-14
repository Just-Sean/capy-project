"""config/settings/: the topic files combine into one set of settings, without one
topic silently overriding another."""

from collections import Counter
from pathlib import Path

from django.conf import settings

import config.settings as combined
from config.settings import core, database, environment, files, logs, security, users

TOPICS = [environment, core, database, users, files, security, logs]
PROJECT_DIR = Path(__file__).resolve().parent.parent


def uppercase_names(module):
    return [name for name in vars(module) if name.isupper()]


def test_base_dir_is_the_project_folder():
    assert settings.BASE_DIR == PROJECT_DIR


def test_every_topics_settings_reach_django():
    # Compared with config.settings itself: during tests Django adjusts a few of its own
    # copies (it adds "testserver" to ALLOWED_HOSTS, for example).
    for topic in TOPICS:
        for name in uppercase_names(topic):
            assert getattr(combined, name) is getattr(topic, name), f"{topic.__name__}.{name}"
    assert settings.SETTINGS_MODULE == "config.settings"


def test_no_setting_is_defined_in_two_topics():
    # Each topic imports the shared names (IS_TEST, BASE_DIR, ...) from environment.py;
    # anything else defined twice would mean the later topic silently wins.
    shared = set(uppercase_names(environment))
    counts = Counter(
        name for topic in TOPICS for name in uppercase_names(topic) if name not in shared
    )
    assert [name for name, count in counts.items() if count > 1] == []
