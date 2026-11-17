# template/deploy/postgres-app-user-upgrade.sql

**What it is:** the one-time change for a production database made **before v1.0.0**, when the app logged in as Postgres's superuser. The starter's README ("Update an existing project", New in v1.0.0) has the steps that run it.

**What it does, as the superuser, in one transaction:**

1. Makes the login `site`: not a superuser, unable to create databases or logins.
2. Gives the superuser a **new password**: the app has known the old one (it was in `DATABASE_URL`).
3. Hands `site` the database and everything the app made in it: schemas, tables (with their sequences), views, materialized views, other sequences, functions and types (enums, domains, ranges, composite types). Objects an extension made stay with the extension.
4. **Checks nothing is left** with the superuser, and stops with an error otherwise, which undoes everything.

**Passwords** come from the environment (`APP_DB_PASSWORD`, `NEW_POSTGRES_PASSWORD`), read inside psql with `\getenv`, never from a command line. Without either one it stops before changing anything.

`tests/test_postgres_logins.py` runs it on a real database made the old way, with every kind of object above.
