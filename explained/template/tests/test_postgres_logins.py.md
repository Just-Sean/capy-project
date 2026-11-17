# template/tests/test_postgres_logins.py

**What it tests:** production's database logins, with a real Postgres (the production image) started fresh with `deploy/postgres-app-user.sh`, as Compose does. Needs the Docker daemon running.

- `compose.prod.yaml` mounts the script, read-only, where Postgres runs it on first start.
- **The app's login isn't a superuser** and can't create databases or logins, replicate or bypass row-level security.
- **It owns the project's database,** so it can create tables (as `migrate` does).
- **It can do nothing beyond its own data:** creating a login or a database, running a program (`COPY ... TO PROGRAM`) and reading server files are all refused.
- **A password with quotes, a backslash and SQL in it** works as the login's password, and the SQL in it doesn't run.
- **Without `APP_DB_USER` and `APP_DB_PASSWORD`,** Postgres stops its first setup with a message saying what to set.
