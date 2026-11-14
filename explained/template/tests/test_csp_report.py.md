# template/tests/test_csp_report.py

**What it tests:** the `/csp-report/` view in `config/csp_report.py`.

**What gets logged:**

- A report is logged as a short summary, **without query strings or code samples**.
- Long values are cut short.
- A value can't add a fake log line.
- A login inside a reported URL isn't logged.

**What gets refused:**

- **A huge report, unread.**
- Things that aren't reports (bad JSON, the wrong shape), with a 400.
- A URL Python can't read, with a 400, not a server error.
- Any type but `application/csp-report`.
- Anything but `POST`.

It also checks that **reports need no CSRF token**, since browsers don't send one.
