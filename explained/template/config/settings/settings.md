# template/config/settings/

**What it is:** every Django setting, as a package with **one file per topic**. `DJANGO_SETTINGS_MODULE` is `config.settings`, which loads this folder's `__init__.py`. That file combines the topics.

| File | Topic |
| --- | --- |
| `environment.py` | Which environment this is (`DJANGO_ENV`), the project folder, and the `env` reader every topic uses |
| `core.py` | Debug, the secret key, hosts, the admin address, apps, middleware, templates, time and language |
| `database.py` | PostgreSQL and the Redis cache |
| `users.py` | The user model, password hashing and rules, login rate limiting |
| `files.py` | Static files and uploads (local or S3, private and public) |
| `email.py` | How email is sent (`EMAIL_URL`) and the From address |
| `tasks.py` | Where background jobs go |
| `security.py` | HTTPS, the proxy, security headers, the Content Security Policy |
| `logs.py` | Where logs go and in which format |

**The rules this layout follows:**

- **Secure by default:** unset `DJANGO_ENV` means production. In production, required values have no fallback, so a misconfigured server **refuses to start** instead of running insecurely.
- **Everything comes from the environment:** every setting can be overridden by its own environment variable, listed in `.env.example`.
- **One file per setting:** a setting is set in only one topic file (`tests/test_settings_package.py` checks this). Where a setting differs in tests, the change sits right next to the setting.
- **Only UPPERCASE names become settings,** so each file can use lowercase helper names freely.

**Adding a topic:** create `config/settings/<topic>.py`, then add it to the import and the list in `__init__.py`, and to `TOPICS` in `tests/test_settings_package.py`. A test fails until all three are done.
