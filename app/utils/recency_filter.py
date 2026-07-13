from datetime import datetime,timedelta

def build_recency_filter(received_within):
    now = datetime.utcnow()
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