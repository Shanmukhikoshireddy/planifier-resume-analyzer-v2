from datetime import datetime,timedelta
from app.utils.datetime_utils import utc_now

def build_recency_filter(received_within):
    now = utc_now()
    if received_within=="LAST_WEEK":
        return {
            "$gte": now-timedelta(days=7)
        }
    
    if received_within=="LAST_MONTH":
        return {
            "$gte": now-timedelta(days=30)
        }

    return {
        "$gte": datetime(2000,1,1)
    }