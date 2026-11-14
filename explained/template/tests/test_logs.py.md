# template/tests/test_logs.py

**What it tests:** logging.

**The JSON format (`config/logging.py`):**

- A line is one JSON object with the time, level, logger and message.
- An error keeps its stack trace **on the same line**, and a stack logged on purpose is kept.
- A message with line breaks can't fake another line, and Unicode line breaks and control codes are escaped.
- A request error names the request **without its query string**.
- A value JSON can't hold is written as text.

**The setup (`settings/logs.py`):**

- Errors are logged with their stack trace: JSON in production, text in development.
- **Errors are never emailed**, even with `ADMINS` set.
- A lowercase log level works.
- In production, a Python warning becomes a JSON line.

**Gunicorn (`gunicorn.conf.py`):**

- Gunicorn logs JSON too, and can really set up its logging from the file.
- It reads `DJANGO_BEHIND_PROXY` the same way Django does.
- **Its request lines leave out query strings,** with and without the proxy.
