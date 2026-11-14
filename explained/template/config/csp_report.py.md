# template/config/csp_report.py

**What it is:** the view at `/csp-report/`. Browsers post a report there whenever the Content Security Policy blocks something (the policy's `report-uri`, set in `settings/security.py`). It logs a short summary as a `csp` warning. A run of them after a deploy usually means the policy blocks something a page needs.

**What gets logged:** only four fields:

- the page (`document-uri`)
- the rule (`effective-directive` and `violated-directive`)
- what was blocked (`blocked-uri`)

Each is cut to 200 characters, and the URLs lose any login, query string and fragment, which can hold secrets. The rest of a report is never logged: the page's referrer and a sample of the blocked code can hold personal data or tokens. The summary is written as JSON, so a value can't add fake log lines.

**What gets refused:**

| Request | Answer |
| --- | --- |
| Not `POST` | 405 |
| Not `application/csp-report` (what browsers send) | 415. Other sites can make visitors' browsers post forms or plain text here, but not this type |
| Over 10 KB | 413, unread. Real reports are under 2 KB |
| Not JSON, no `csp-report` object, or an unreadable URL | 400, never a server error |

It's `@csrf_exempt` because browsers send reports without a CSRF token, and nothing here changes data. In production Caddy also limits each address to 120 reports a minute.

**Checked by:** `tests/test_csp_report.py`.
