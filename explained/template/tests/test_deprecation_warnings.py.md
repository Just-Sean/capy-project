# template/tests/test_deprecation_warnings.py

**What it tests:** that the "every Django deprecation fails the tests" rule (`filterwarnings` in `pyproject.toml`) really works. Upgrades then never bring surprises.

- The installed Django has deprecation warnings to check, so the test can't pass by checking nothing.
- **Each Django deprecation fails the tests,** for features removed in the next version and in the one after. This holds:
  - in pytest itself
  - in the `manage.py` processes tests start
  - for a deprecated setting too
- Those processes otherwise behave as `python manage.py` would on its own.
- **Other libraries' deprecations don't fail the tests,** because you can't fix their code.
