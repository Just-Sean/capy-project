# template/config/login_limits.py

**What it is:** the project's own parts of login rate limiting, on top of django-axes. The settings are in `settings/users.py`.

**`client_ip(request)`:** the visitor's real address, as django-axes sees it (`AXES_CLIENT_IP_CALLABLE`).

- **Directly on the internet:** the connection's address (`REMOTE_ADDR`), which visitors can't fake.
- **Behind one proxy you control** (`DJANGO_BEHIND_PROXY`, which production always sets): the **last** entry of `X-Forwarded-For`, the one Caddy adds. Earlier entries are whatever the visitor sent, so they're never trusted. Otherwise anyone could pick a new address for each try.
- **Normalized:**
  - A port some proxies add (`203.0.113.5:50123`) is dropped, so a new connection isn't a new address.
  - Anything that isn't an IP address falls back to the connection's own.
  - **IPv6 addresses count per /64**, since one user usually controls a whole /64.

`parse_ip()` reads the forms an address can come in: plain, `IPv4:port`, `[IPv6]:port`, or bare IPv6.

**`IPLoginLimitBackend`:** the first entry in `AUTHENTICATION_BACKENDS`. It never logs anyone in itself.

- It refuses a login from an address whose failures across **all** usernames have reached `DJANGO_LOGIN_IP_FAILURE_LIMIT` (30) within the lockout time.
- That stops someone trying a new username each time to get around axes' per-username lockout, where each try costs a full Argon2 check.
- When it refuses, it sets `request.axes_locked_out`, so axes' middleware shows its "too many attempts" page.
- It has **no `get_user()`** on purpose. Django would otherwise use this backend to load logged-in users, and every session would be logged out.

**If another proxy or a CDN sits in front of Caddy,** the visitor's address is no longer the last entry, and this file needs changing (see the README's Production section).

**Checked by:** `tests/test_login_rate_limit.py`.
