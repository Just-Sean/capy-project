# template/accounts/migrations/0001_initial.py

**What it is:** the migration that creates the `User` table. Django 6.1.3 generated it from `models.py`. It depends on Django's `auth` app, which supplies groups and permissions.

**What it creates:**

- **Django's standard user columns:** `id` (a 64-bit `BigAutoField`), password, last login, superuser, username, names, staff, active, date joined.
- **The starter's additions:** `email` (required) and `public_id` (a unique UUID).
- **The links:** the `groups` and `user_permissions` many-to-many tables.
- **The constraint:** `accounts_user_email_ci_unique`, unique on the lowercased email.

Never edit it once a project has run it. A model change gets a new migration (`makemigrations`), and `tests/test_migrations.py` fails until it exists. Ruff skips migrations, because they're generated.
