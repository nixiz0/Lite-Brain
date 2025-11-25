from datetime import datetime, timezone

def utc_now_iso() -> str:
    # Returns the current UTC timestamp in ISO 8601 format.
    return datetime.now(timezone.utc).isoformat()
