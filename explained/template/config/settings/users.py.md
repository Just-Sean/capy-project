# template/config/settings/users.py

**What it is:** users, passwords and login rate limiting.

**Users and passwords:**

- `AUTH_USER_MODEL = "accounts.User"`.
- **Argon2** hashes passwords, the hasher Django recommends.
  - The other hashers in the list only check passwords saved with them, and those get re-hashed with Argon2 at the user's next login.
  - Tests use fast MD5 instead, because proper hashing is deliberately slow.
  - Each Argon2 check briefly uses about 100 MB of memory.
- **Password rules:** at least **12 characters**, not too close to the user's details, not a common password, not all digits.

**Login rate limiting** (django-axes, plus `config/login_limits.py`) has two limits:

| Limit | Default | Variable |
| --- | --- | --- |
| Failed logins for one **username + address** pair, before that pair is locked out | 5 | `DJANGO_LOGIN_FAILURE_LIMIT` |
| Failed logins from one **address**, whatever usernames were tried | 30 | `DJANGO_LOGIN_IP_FAILURE_LIMIT` |
| How long a lockout lasts (each further try restarts it) | 15 minutes | `DJANGO_LOGIN_LOCKOUT_MINUTES` |

Each must be at least 1, or the settings refuse to start.

- **Why per pair:** someone elsewhere can't lock a real user out by guessing their username.
- **Why the address limit is higher:** an office sharing one address doesn't lock itself out.

**`AUTHENTICATION_BACKENDS`, in order:**

1. The project's per-address check (`IPLoginLimitBackend`).
2. axes' per-pair check.
3. Django's real login (`ModelBackend`).

**Other axes settings:**

- A successful login clears its pair's count.
- Lockouts send a `Retry-After` header.
- The visitor's address comes from `config.login_limits.client_ip`, which trusts a proxy only if one is declared.
- **Successful logins aren't recorded.**
- Usernames and addresses are hidden in log lines.

Failed attempts are kept **in the database** (not Redis, which can be emptied) until their lockout time has passed. `manage.py axes_reset` clears them.

**For custom code and tests:**

- Custom login code must call `authenticate(request, ...)` with the request, or the login is refused.
- Tests should use `client.force_login(user)`, not `client.login(...)`.
