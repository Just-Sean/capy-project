# template/config/settings/email.py

**What it is:** how email is sent, all from one variable, **`EMAIL_URL`**, which this file turns into Django 6.1's `MAILERS` setting.

| `EMAIL_URL` | Means |
| --- | --- |
| `smtp+tls://user:password@host:587` | A mail server, encrypted with STARTTLS |
| `smtp+ssl://user:password@host:465` | A mail server, encrypted from the start |
| `smtp://localhost:1025` | Unencrypted, **no login**: a local mail catcher, development only |
| `consolemail://` | Print emails (development's default) |

**In each environment:**

- **Tests** always keep emails in memory (`django.core.mail.outbox`), whatever `.env` says, so tests never send real email.
- **Development** prints emails in the `runserver` terminal unless `EMAIL_URL` is set.
- **Production:**
  - Email is optional. Without it, sending fails clearly through `config/email_not_set_up.py`.
  - With it, it **must be `smtp+tls://` or `smtp+ssl://`**. Plain SMTP would send the login and every email, password reset links included, readable on the network.

**What else is refused, in every environment:**

- a URL that a password with unencoded special characters cut short. The error never shows the password.
- a missing server address
- a login over plain `smtp://`
- any other scheme, `smtps://` included (it's unclear which encryption it means)

Characters in the user or password other than letters, digits and `- . _ ~` must be percent-encoded. Every SMTP connection gives up after **10 seconds**, so a slow mail server can't hold a request.

**The From address:** `DEFAULT_FROM_EMAIL` comes from `DJANGO_DEFAULT_FROM_EMAIL`, and production requires it whenever `EMAIL_URL` is set. `SERVER_EMAIL`, the From of Django's own messages, is the same address.
