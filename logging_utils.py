import json
from datetime import datetime, timezone


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def classify_error(exc):
    name = type(exc).__name__
    message = str(exc)
    name_lower = name.lower()
    message_lower = message.lower()

    if "timeout" in name_lower or "timeout" in message_lower:
        return "transient_timeout"
    if "connect" in name_lower:
        return "transient_network"
    if "statuserror" in name_lower:
        if "429" in message_lower or " 5" in message_lower:
            return "transient_http"
        return "permanent_http"
    if "serviceunavailable" in name_lower:
        return "transient_service"
    return "unknown"


def log_event(event, level="INFO", **fields):
    record = {
        "ts": utc_now_iso(),
        "level": level,
        "event": event,
    }
    record.update(fields)
    print(json.dumps(record, default=str, ensure_ascii=True))
