# template/tests/test_dockerfile.py

**What it tests:** the production image's `Dockerfile`, by reading its stages (the real build is checked by building it, and by `test_caddy.py` for Caddy's image):

- **The build stage installs `git`** before `uv sync`, so apps from a Git repository (`git+https://github.com/...`) can be installed.
- **The runtime image installs nothing:** no `apt`, `apk`, `pip`, `curl`, `wget` or `git` in its instructions (comments aside), so build tools never reach the image that runs.
- **No build arguments (`ARG`, in any case):** they end up in the image's history, so secrets must never travel that way (private repositories use Docker build secrets).
