-- The app's own database login, for a production database that already exists (one made
-- before the starter's v1.0.0, which logged the app in as the superuser). The starter's
-- README ("Update an existing project", New in v1.0.0) says how to run it, once.
--
-- Run as the database's superuser (POSTGRES_USER), in one transaction: it makes the
-- login `site` (not a superuser, unable to create databases or logins), hands it the
-- database and everything the app made in it, and gives the superuser a new password,
-- since the app has known the old one. Both passwords are read from the environment
-- (\getenv), never from a command line. If anything is left behind, it stops with an
-- error and nothing changes.

\getenv site_password APP_DB_PASSWORD
\getenv admin_password NEW_POSTGRES_PASSWORD
\if :{?site_password}
\else
  DO $$ BEGIN RAISE EXCEPTION 'Set APP_DB_PASSWORD (the new login''s password)'; END $$;
\endif
\if :{?admin_password}
\else
  DO $$ BEGIN RAISE EXCEPTION 'Set NEW_POSTGRES_PASSWORD (the superuser''s new password)'; END $$;
\endif

CREATE ROLE site WITH LOGIN PASSWORD :'site_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE CURRENT_USER WITH PASSWORD :'admin_password';

DO $$
DECLARE
  item record;
  old_owner oid := (SELECT oid FROM pg_roles WHERE rolname = current_user);
BEGIN
  EXECUTE format('ALTER DATABASE %I OWNER TO site', current_database());

  -- Schemas the old login owns (`public` on a cluster upgraded from Postgres 14 or
  -- older; any schema a project made).
  FOR item IN
    SELECT nspname FROM pg_namespace
    WHERE nspowner = old_owner AND nspname NOT LIKE 'pg\_%' AND nspname <> 'information_schema'
  LOOP
    EXECUTE format('ALTER SCHEMA %I OWNER TO site', item.nspname);
  END LOOP;

  -- Tables (with their identity and serial sequences), then views, materialized views
  -- and the remaining sequences, then functions and types. Objects an extension made
  -- stay with it.
  FOR item IN
    SELECT c.oid::regclass AS name, c.relkind FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relowner = old_owner AND c.relkind IN ('r', 'p', 'f')
      AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
      AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                      AND d.objid = c.oid AND d.deptype = 'e')
  LOOP
    EXECUTE format('ALTER %s %s OWNER TO site',
                   CASE item.relkind WHEN 'f' THEN 'FOREIGN TABLE' ELSE 'TABLE' END, item.name);
  END LOOP;
  FOR item IN
    SELECT c.oid::regclass AS name, c.relkind FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relowner = old_owner AND c.relkind IN ('v', 'm', 'S')
      AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
      AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                      AND d.objid = c.oid AND d.deptype = 'e')
  LOOP
    EXECUTE format('ALTER %s %s OWNER TO site',
                   CASE item.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                                     ELSE 'SEQUENCE' END, item.name);
  END LOOP;
  FOR item IN
    SELECT p.oid::regprocedure AS name FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE p.proowner = old_owner
      AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
      AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass
                      AND d.objid = p.oid AND d.deptype = 'e')
  LOOP
    EXECUTE format('ALTER ROUTINE %s OWNER TO site', item.name);
  END LOOP;
  -- Enums, domains, ranges and standalone composite types (not the row type every table
  -- has, nor the array type each type has: those follow their owner).
  FOR item IN
    SELECT t.oid::regtype AS name, t.typtype FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE t.typowner = old_owner AND t.typtype IN ('e', 'd', 'r', 'm', 'c')
      AND (t.typtype <> 'c' OR (SELECT relkind FROM pg_class WHERE oid = t.typrelid) = 'c')
      AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
      AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_type'::regclass
                      AND d.objid = t.oid AND d.deptype = 'e')
  LOOP
    EXECUTE format('ALTER %s %s OWNER TO site',
                   CASE item.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END, item.name);
  END LOOP;

  -- Nothing of the app's may stay with the superuser: stop (and undo everything) if so.
  IF EXISTS (
    SELECT FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relowner = old_owner AND n.nspname NOT LIKE 'pg\_%'
      AND n.nspname <> 'information_schema' AND c.relkind NOT IN ('i', 'I', 't')
      AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                      AND d.objid = c.oid AND d.deptype = 'e')
  ) THEN
    RAISE EXCEPTION 'Some objects still belong to %: nothing was changed', current_user;
  END IF;
END $$;
