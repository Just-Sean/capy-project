"""Every Django deprecation warning fails the tests, in this process and in the manage.py
processes other tests start, so code using a feature Django will remove can't pass."""

import inspect
import warnings

import pytest
from django.utils import deprecation

from tests.test_production_settings import WARNING_FILTERS, run_manage

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


def test_django_has_deprecation_warnings_to_check():
    assert DJANGO_DEPRECATIONS  # if Django moves them, this check must move too


@pytest.mark.parametrize("warning", DJANGO_DEPRECATIONS, ids=lambda cls: cls.__name__)
def test_a_django_deprecation_fails_the_tests(warning):
    # Raised from this file (a project file, not Django's own code), as Django does for
    # most deprecations: the project's code is what has to change.
    with pytest.raises(warning):
        warnings.warn("a deprecated feature", warning, stacklevel=1)  # from this file


@pytest.mark.parametrize("warning", DJANGO_DEPRECATIONS, ids=lambda cls: cls.__name__)
def test_a_django_deprecation_fails_in_manage_py_too(warning):
    script = RAISE_IN_SUBPROCESS.format(name=warning.__name__)
    result = run_manage("shell", "-c", script, DJANGO_ENV="development")
    assert result.stdout.strip().splitlines()[-1] == "failed", result.stderr


def test_the_filters_are_all_simple_error_rules():
    # run_manage passes on only the warning class of each rule.
    assert all(rule.count(":") == 2 and rule.startswith("error::") for rule in WARNING_FILTERS)
