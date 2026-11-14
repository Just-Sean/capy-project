# template/templates/403_csrf.html

**What it is:** the "Form not sent" page (status 403). It's shown when a form fails Django's CSRF security check: the page was open too long, cookies are blocked, or the form came from another site.

It tells the visitor that nothing was saved, and how to recover: go back, copy what they typed, reload, and send again. It also suggests checking that cookies are allowed.

**With debug on only,** `config/csrf_failure.py` passes Django's reason, and the page shows it ("Reason (shown only with debug on): CSRF cookie not set"). Production never shows it.
