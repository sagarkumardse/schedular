from datetime import datetime, time, timedelta, timezone
from calendar_service import CalendarService
import jpholiday

JST = timezone(timedelta(hours=9))


calendar_service = CalendarService()


def is_japanese_working_hours(dt: datetime) -> bool:
    """
    Check if datetime falls within Japanese working hours (9am-7pm on working days).
    Returns True if it's a working day in Japan AND time is between 9am-7pm.
    """
    # Check if it's a Japanese holiday
    if jpholiday.is_holiday(dt.date()):
        return False

    # Check if it's weekend (Saturday=5, Sunday=6)
    if dt.weekday() >= 5:
        return False

    # Check if time is between 9am and 7pm
    meeting_time = dt.time()
    if time(9, 0) <= meeting_time < time(19, 0):
        return True

    return False

def _to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(timezone.utc).replace(tzinfo=None)



def _parse_google_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return _to_utc_naive(datetime.fromisoformat(normalized))




def has_overlapping_event(
    start_time: datetime,
    duration_minutes: int,
    exclude_event_id: str | None = None
) -> bool:
    if duration_minutes <= 0:
        return False

    start_time_utc = _to_utc_naive(start_time)
    end_time = start_time_utc + timedelta(minutes=duration_minutes)
    events = calendar_service.get_events(
        start_time=start_time_utc.isoformat() + "Z",
        end_time=end_time.isoformat() + "Z",
        max_results=50
    )

    for existing in events:
        if existing.get("status") == "cancelled":
            continue
        if exclude_event_id and existing.get("id") == exclude_event_id:
            continue

        existing_start = _parse_google_datetime(existing.get("start", {}).get("dateTime"))
        existing_end = _parse_google_datetime(existing.get("end", {}).get("dateTime"))
        if not existing_start or not existing_end:
            continue

        if existing_start < end_time and start_time_utc < existing_end:
            return True

    return False
