# template/gunicorn.conf.py

**What it is:** the settings for Gunicorn, the production web server that runs Django. Gunicorn reads this file by itself when it's started from the project folder, which Docker's `WORKDIR /app` is. Started from anywhere else, it silently skips it.

| Setting | Value | Why |
| --- | --- | --- |
| `bind` | `127.0.0.1:8000` | Outside Docker, only a proxy on the same machine can reach it. Set explicitly so a host's `PORT` variable can't open it to every interface. The `Dockerfile` overrides it with `0.0.0.0:8000` |
| `workers` | `WEB_CONCURRENCY`, default 1 | Set it to about 2 × CPU cores + 1. Each login check briefly uses about 100 MB (Argon2) |
| `timeout` / `graceful_timeout` | 30 s / 30 s | A stuck worker is replaced; on shutdown, requests get 30 s to finish. (`compose.prod.yaml` gives the container 35 s) |
| `max_requests` (+ jitter) | 1000 (± 100) | Each worker is replaced now and then, so a slow memory leak can't build up. The jitter keeps them from all restarting at once |
| `worker_tmp_dir` | `/dev/shm` | Heartbeat files in memory: on a container's disk they can stall workers |
| `accesslog` / `errorlog` | `-` | To stdout and stderr, where Docker collects them |
| `access_log_format` | address, method, path, status, bytes, ms, browser | **The path leaves out the query string**, which often holds tokens. Behind the proxy (`DJANGO_BEHIND_PROXY`), the address is the visitor's, from `X-Forwarded-For` |
| `logconfig_dict` | JSON formatter | Gunicorn's own lines and request lines are JSON, like the app's (`config/logging.py`) |
| `control_socket_disable` | `True` | Gunicorn's control socket isn't needed, and would need a home folder the app user doesn't have |

**Details worth knowing:**

- It reads `DJANGO_BEHIND_PROXY` with the same true words django-environ accepts, so Gunicorn and Django always agree.
- Every name in the file must be a real Gunicorn setting, so the logic is written as single expressions. `tests/test_gunicorn_config.py` checks that, and that every value is valid.
- `--log-level` has no effect, because the levels are set here.
