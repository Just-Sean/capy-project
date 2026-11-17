# template/deploy/postgres-app-user.sh

**What it is:** a script Postgres runs **once**, while it first creates its data (an empty `pgdata` volume). `compose.prod.yaml` mounts it, read-only, into the official image's setup folder (`/docker-entrypoint-initdb.d`).

**What it does:** makes the app's own database login, `APP_DB_USER` with `APP_DB_PASSWORD` (both from `.env.postgres`), and makes it the owner of the project's database.

- **Not a superuser:** it can't create databases or logins, replicate, or bypass row-level security. So a bug in the app (an SQL injection, say) can reach the project's own data, but can't run commands on the database server (`COPY ... TO PROGRAM`), read its files or make logins.
- **Owner of the database,** so `migrate` can create and change tables.
- **`POSTGRES_USER`**, the superuser the image makes, is kept for backups and restores only.

**Safe with any password:** the name and password go into psql as variables and psql quotes them itself, so quotes or SQL in them can't change the statement (`tests/test_postgres_logins.py` checks this). The password is read from the environment inside psql (`\getenv`), so it never appears on a command line, where other users of the server could see it.

**If `APP_DB_USER` or `APP_DB_PASSWORD` is missing**, it stops Postgres's first setup with a message, rather than leaving a database without the app's login. Starting again won't add the login (the data now exists): the README says to delete the half-made volume and start again.

**A database that already exists** never runs it again: `postgres-app-user-upgrade.sql` does the same for one, run once by hand (the starter's README, "Update an existing project", New in v1.0.0).
