"""Every Django deprecation warning fails the tests, in this process and in the manage.py
processes other tests start, so code using a feature Django will remove can't pass."""

import inspect
import warnings

import pytest
from django.utils import deprecation

from tests.test_production_settings import PROJECT_DIR, run_manage

# Every warning class Django defines for features it's removing.
DJANGO_DEPRECATIONS = sorted(
    {
        cls
        for _, cls in inspect.getmembers(deprecation, inspect.isclass)
        if issubclass(cls, Warning) and cls.__module__ == deprecation.__name__
    },
    key=lambda cls: cls.__name__,
)
RAISE_IN_SUBPROCESS = (
    "import warnings\n"
    "from django.utils import deprecation\n"
    "try:\n"
    "    warnings.warn('a deprecated feature', deprecation.{name})\n"
    "    print('passed')\n"
    "except deprecation.{name}:\n"
    "    print('failed')\n"
)


def last_line(result):
    return result.stdout.strip().splitlines()[-1]


def test_django_has_deprecation_warnings_to_check():
    assert DJANGO_DEPRECATIONS  # if Django moves them, this check must move too


@pytest.mark.parametrize("warning", DJANGO_DEPRECATIONS, ids=lambda cls: cls.__name__)
def test_a_django_deprecation_fails_the_tests(warning):
    # Raised from this file (a project file, not Django's own code), as Django does for
    # most deprecations: the project's code is what has to change.
    with pytest.raises(warning):
        warnings.warn("a deprecated feature", warning, stacklevel=1)


@pytest.mark.parametrize("warning", DJANGO_DEPRECATIONS, ids=lambda cls: cls.__name__)
def test_a_django_deprecation_fails_in_manage_py_too(warning):
    script = RAISE_IN_SUBPROCESS.format(name=warning.__name__)
    result = run_manage("shell", "-c", script, DJANGO_ENV="development")
    assert last_line(result) == "failed", result.stderr


def test_a_deprecated_setting_fails_the_tests(settings):
    # A real Django 6.1 deprecation: USE_BLANK_CHOICE_DASH is going away.
    with pytest.raises(deprecation.RemovedAfterNextVersionWarning):
        settings.USE_BLANK_CHOICE_DASH = True


def test_manage_py_runs_as_it_would_on_its_own():
    script = "import sys; print(sys.argv[0], sys.path[0])"
    result = run_manage("shell", "-c", script, DJANGO_ENV="development")
    assert last_line(result) == f"manage.py {PROJECT_DIR}", result.stderr
    unknown = run_manage("no-such-command", DJANGO_ENV="development")
    assert unknown.returncode == 1
    assert "Unknown command" in unknown.stderr


def test_other_libraries_deprecations_dont_fail_the_tests():
    # Only Django's are errors: a project can't fix another library's code.
    with warnings.catch_warnings(record=True) as caught:
        warnings.warn("old library feature", DeprecationWarning, stacklevel=1)
    assert len(caught) == 1  # recorded, not raised
