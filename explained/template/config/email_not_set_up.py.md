# template/config/email_not_set_up.py

**What it is:** `EmailNotSetUpBackend`, the email backend production uses when `EMAIL_URL` isn't set (see `settings/email.py`).

The app still starts, but the first time it tries to send an email (a password reset, say), it raises **"Email isn't set up: set EMAIL_URL to send email."**, instead of the email silently going nowhere. It raises even when asked to fail silently.

**Why not Django's own `MAILERS = {}`:** that also warns (`mail.W001`) on every `check`, which would make `check --deploy --fail-level WARNING` fail.
