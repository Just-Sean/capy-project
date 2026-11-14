# template/compose.override.yaml.jinja → compose.override.yaml

**What it is:** development's additions to `compose.yaml`. `docker compose` loads it automatically; production leaves it out by naming its files with `-f`.

**What it adds:**

- **`db`:**
  - The dev-only login: user `app`, password `app`, and a database named after the slug. `DATABASE_URL` in `.env` matches it.
  - Port 5432, **on `127.0.0.1` only**, so only this machine reaches it. `POSTGRES_PORT` changes the port if 5432 is taken.
  - A `pgdata` volume, so the data survives restarts. `docker compose down -v` deletes it.
- **`redis`:**
  - The dev-only password `app`. `CACHE_URL` in `.env` matches it.
  - Port 6379, on `127.0.0.1` only. `REDIS_PORT` changes it.

**Why the ports are `127.0.0.1`:** Docker's published ports skip the machine's firewall. Without the address, the dev database with its known password would be open to the whole network.
