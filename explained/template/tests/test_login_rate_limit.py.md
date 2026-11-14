# template/tests/test_login_rate_limit.py

**What it tests:** login rate limiting (django-axes plus `config/login_limits.py`), through the admin's real login page.

**The settings:**

- The defaults are 5 failures per user, 30 per address, and a 15-minute lockout.
- The limits come from the environment, and a limit below 1 is refused.

**Per user and address:**

- Repeated wrong passwords lock the user out, **even with the right password** afterwards. Lockouts answer 429.
- A lockout doesn't block other users, or the same user from another address.
- The lockout ends after its time, and a try during it restarts the time.
- A successful login clears the count. Logged-in users stay logged in, and successful logins aren't recorded.

**Per address:**

- Trying **a new username each time** still hits the per-address limit.
- Only recent failures count.

**Where the address comes from:**

- Without a proxy, a faked `X-Forwarded-For` header is ignored.
- Behind a proxy, only the address the proxy adds (the last entry) counts.
- A new port each time doesn't get around the lockout.
- `client_ip()` is checked on its own with many address forms: IPv4, IPv6 (per /64), with ports, and garbage.

Tests log in with real POSTs to the login page, because that's what axes watches.
