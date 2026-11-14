# template/tests/test_healthz.py

**What it tests:** `/healthz`, the check Docker polls.

- It answers `ok`.
- **It answers any host name,** even one not in `ALLOWED_HOSTS`, because Docker and load balancers call it by IP.
- **It makes no database queries,** so a database outage can't mark the app unhealthy.
