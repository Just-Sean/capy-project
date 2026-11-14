# template/.github/dependabot.yml

**What it is:** Dependabot's settings. Dependabot is GitHub's bot that opens a pull request when a newer version of something the project uses comes out. Security fixes are included.

**What it watches, weekly:**

| Ecosystem | Where | What |
| --- | --- | --- |
| `uv` | `/` | Python packages in `pyproject.toml` and `uv.lock` |
| `docker` | `/` and `/deploy` | The base images in `Dockerfile` and `deploy/caddy.Dockerfile` |
| `docker-compose` | `/` | The Postgres and Redis images in the compose files |

**Also turn on in GitHub:** "Dependabot alerts" and "Dependabot security updates" (the repository's Settings > Code security). Then known vulnerabilities get a pull request straight away, not only at the weekly check. The file can't switch those on by itself.

**Each update pull request** should pass `uv run pytest` before you merge it, like any other change.
