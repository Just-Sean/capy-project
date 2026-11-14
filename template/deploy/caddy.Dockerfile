# Production's Caddy (compose.prod.yaml's caddy service): the official image plus the
# rate-limit plugin (deploy/Caddyfile's rate_limit), running as its own unprivileged
# user instead of root. Both versions are pinned: change them together when updating
# Caddy, and check the plugin's releases for one that supports the new Caddy.

# ---- Stage 1: build Caddy with the plugin ----------------------------------------
FROM caddy:2.11.9-builder-alpine AS build
# XCADDY_SETCAP=0: no file capability to bind ports 80 and 443 (the builder image adds
# one by default). A program carrying one can't start in a container with every
# capability dropped, and compose.prod.yaml lets unprivileged users bind them instead.
RUN XCADDY_SETCAP=0 xcaddy build --with github.com/mholt/caddy-ratelimit@v0.1.0

# ---- Stage 2: the official image with that build --------------------------------
FROM caddy:2.11.9-alpine
# Replaces the official binary, which carries that capability too.
COPY --from=build /usr/bin/caddy /usr/bin/caddy
# Its own user, owning only what Caddy writes: certificates and keys (/data) and its
# saved configuration (/config).
RUN addgroup -S -g 10002 caddy \
    && adduser -S -u 10002 -G caddy -H -s /sbin/nologin caddy \
    && chown -R caddy:caddy /data /config
USER caddy
