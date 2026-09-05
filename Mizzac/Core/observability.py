"""Small structured logging primitives with defensive secret redaction."""

import json
import logging
import re
from datetime import UTC, datetime

SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|cookie|pin|2fa)"
        r"([\s=:]+)[^\s,;]+"
    ),
)
ALLOWED_CONTEXT = (
    "event",
    "correlation_id",
    "status",
    "connection_id",
    "instrument_id",
    "portfolio_id",
)


def redact_message(value):
    message = str(value)
    for pattern in SECRET_PATTERNS:
        message = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", message)
    return message


class SecretRedactionFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact_message(record.getMessage())
        record.args = ()
        return True


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact_message(super().format(record))


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ALLOWED_CONTEXT:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = redact_message(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)
