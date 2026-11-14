# template/tests/test_settings_package.py

**What it tests:** the `config/settings/` topic files combine into one set of settings correctly.

- `BASE_DIR` is the project folder.
- **Every topic file is combined:** each file in the folder is in `TOPICS`, and its settings reach Django. Adding a topic means adding it here and to `__init__.py`.
- **No setting is set differently in two topics.** Otherwise, which value won would depend on the import order.
- **A leftover `config/settings.py` is refused.** The test creates one for a moment and checks that the settings refuse to start.
