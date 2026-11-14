# template/deploy/caddy.Dockerfile

**What it is:** production's Caddy image. The official image doesn't include rate limiting, so this builds Caddy with the [caddy-ratelimit](https://github.com/mholt/caddy-ratelimit) plugin. It also makes Caddy run as its own user instead of root.

**Stage 1, `build`** (`caddy:2.11.9-builder-alpine`):

- `xcaddy build --with github.com/mholt/caddy-ratelimit@v0.1.0` builds Caddy with the plugin.
- **`XCADDY_SETCAP=0`** stops the builder from giving the program a file capability to open ports 80 and 443. A program carrying one **can't start** in a container that drops every capability, which production's does. Instead, `compose.prod.yaml` lets unprivileged users open those ports.

**Stage 2** (`caddy:2.11.9-alpine`):

1. Replaces the official program, which carries that capability too, with the one just built.
2. Adds user and group `caddy` (uid/gid **10002**), with no home folder and no login shell.
3. Gives it only what Caddy writes: `/data` (certificates and keys) and `/config` (its saved configuration).
4. Switches to `USER caddy`.

**Updating Caddy:** change the version in both `FROM` lines together. Then change the plugin's version to a release that supports that Caddy. `up --build` rebuilds the image on the next deploy.

**For projects that ran Caddy as root before:** the certificate volumes are owned by root, so hand them over once. The starter's README has the `chown` command.

**Checked by:** `tests/test_caddy.py`, which builds this image and checks it doesn't run as root.
