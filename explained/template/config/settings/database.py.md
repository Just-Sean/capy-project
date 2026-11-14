# template/config/settings/database.py

**What it is:** the database and the cache.

**PostgreSQL (`DATABASES`):**

- Comes from **`DATABASE_URL`** (`postgres://user:password@host:port/name`), which is **required in every environment**.
- `CONN_MAX_AGE`: connections are kept for 60 s and reused (`DJANGO_CONN_MAX_AGE`), with `CONN_HEALTH_CHECKS` on, so a dropped connection is replaced instead of failing a request.
- **`connect_timeout` 5 s:** a database that can't be reached gives a quick error instead of holding the request. `/readyz` uses a new connection each time, so it always gets this limit. A `?connect_timeout=` in `DATABASE_URL` overrides it.
- `DEFAULT_AUTO_FIELD = BigAutoField`: 64-bit primary keys for every model. The public face of a row is a UUID, such as the `User`'s `public_id`.

**Redis (`CACHES`):**

- **Tests:** an in-memory cache, so tests don't need Redis running.
- **Everywhere else:**
  - **`CACHE_URL` is required** and must start with `redis://` or `rediss://`. A dummy cache would store nothing, and an in-memory one isn't shared between server processes, which the login limits and caching need.
  - **Always Django's own Redis backend,** named explicitly, so another installed package can't swap it.
  - **Gives up after 2 s** (`REDIS_SOCKET_TIMEOUT_SECONDS`), for connecting and reading, so a slow or missing Redis fails fast. Options already in `CACHE_URL`, e.g. TLS settings, are kept.

Django's Redis cache raises an error when Redis is down, rather than skipping it. Code that must keep working without Redis should catch cache errors where it uses the cache.
