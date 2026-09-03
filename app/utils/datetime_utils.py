from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def utc_now():
    return datetime.now(timezone.utc)

IST = ZoneInfo("Asia/Kolkata")
def utc_to_ist(dt):
    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(IST)