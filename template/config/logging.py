"""The log formats: one JSON object per line in production, readable text otherwise.

Docker, systemd and hosting platforms collect what the app writes to the console, and
log tools can search JSON lines by field (level, logger, ...) without guessing at text.
"""

import json
import logging
from datetime import UTC, datetime

TEXT_FORMAT = "{asctime} {levelname} {name}: {message}"


class JsonFormatter(logging.Formatter):
    """One JSON object per log line. A message or stack trace that spans several lines
    stays on one line (JSON escapes the line breaks), so log tools never split it."""

    def format(self, record):
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request = getattr(record, "request", None)  # Django adds it to request errors
        if request is not None and hasattr(request, "path"):
            entry["request"] = f"{request.method} {request.path}"  # no query string
        if getattr(record, "status_code", None) is not None:
            entry["status"] = record.status_code
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            entry["stack"] = self.formatStack(record.stack_info)
        # default=str: a value JSON can't hold is written as text instead of failing.
        return json.dumps(entry, default=str, ensure_ascii=False)
