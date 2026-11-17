# The app's own database login, for production (compose.prod.yaml mounts this file).
#
# Postgres runs it once, while it first creates its data (an empty `pgdata` volume), as
# part of its own setup (/docker-entrypoint-initdb.d). POSTGRES_USER, from .env.postgres,
# is the database's superuser: only for backups and restores. The app, the job worker
# and the migrate step log in as APP_DB_USER instead, which is not a superuser and can't
# create databases or logins, so a bug in the app (an SQL injection, say) can reach the
# project's own data but not the server: no running commands, reading files or making
# logins. It owns the project's database, so migrations can create and change tables.
#
# A database that already exists doesn't run this again: see the starter's README
# ("Update an existing project") for setting up the login on one.

if [ -z "${APP_DB_USER:-}" ] || [ -z "${APP_DB_PASSWORD:-}" ]; then
  echo "postgres-app-user.sh: set APP_DB_USER and APP_DB_PASSWORD in .env.postgres" >&2
  exit 1
fi

# The name and password go in as psql variables, quoted by psql itself, so no character
# in them can change the SQL.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set app_user="$APP_DB_USER" --set app_password="$APP_DB_PASSWORD" \
  --set db="$POSTGRES_DB" <<'SQL'
CREATE ROLE :"app_user" WITH LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER DATABASE :"db" OWNER TO :"app_user";
SQL
