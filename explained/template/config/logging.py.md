# template/config/logging.py

**What it is:** the two log formats. Which one is used is set in `settings/logs.py`. Gunicorn uses the JSON one too (`gunicorn.conf.py`).

- **`TEXT_FORMAT`** (development and tests): `2026-11-14 05:16:03,942 WARNING csp: ...`, readable in a terminal.
- **`JsonFormatter`** (production): **one JSON object per line**, which log tools can search by field:

| Field | When |
| --- | --- |
| `time` | Always: UTC, to the millisecond |
| `level`, `logger`, `message` | Always |
| `request` | Request errors: method and path, **without the query string**, which can hold tokens |
| `status` | When the record has a status code |
| `exception` | Errors: the full stack trace |
| `stack` | When something logged its stack on purpose |

**Why every entry stays on one line:**

- JSON escapes line breaks, so a multi-line stack trace or message can't be split by log tools.
- A value can't fake an extra line.
- Output is plain ASCII, so Unicode line breaks or terminal control codes from a request path are escaped too.
- `default=str` writes values JSON can't hold as text, instead of failing.

**Checked by:** `tests/test_logs.py`.
