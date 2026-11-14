# template/config/csrf_failure.py

**What it is:** the view Django calls when a form fails its CSRF security check (`CSRF_FAILURE_VIEW` in `settings/security.py`). This happens when the page was open too long, cookies are blocked, or the form came from another site.

It shows `templates/403_csrf.html` with a 403 status. **With debug on**, it passes Django's reason (e.g. "CSRF cookie not set") to the page, because in development that's the main clue. Production never shows it.

**Why a view is needed:** Django's own failure page shows the reason, but only when there's no `403_csrf.html` template. This keeps both the site's own page and the reason.
