import os
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, time, timedelta, timezone
from fastapi.responses import FileResponse
from calendar_service import CalendarService
from nlp_parser import MeetingParser
from fastapi.staticfiles import StaticFiles
from invite_email import send_meeting_notifications
from utils import has_overlapping_event, _parse_google_datetime,is_japanese_working_hours
JST = timezone(timedelta(hours=9))

app = FastAPI(title="Calendar Automation API")

# CORS for mobile access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
calendar_service = CalendarService()
meeting_parser = MeetingParser()


class TextCommand(BaseModel):
    command: str
    history: list | None = None  # Optional conversation history for context


class UpdateEventRequest(BaseModel):
    summary: str | None = None
    start_time: datetime | None = None
    duration_minutes: int | None = None
    description: str | None = None


def cancellation_response(status: str, reason: str):
    return {
        "status": status,
        "message": "Canceled",
        "reason": reason
    }


def apply_hardcoded_fallback_rules(meeting_details: dict) -> dict:
    """
    Deterministic fallback when AI parsing/decision is unavailable or unusable.
    """
    start_time = meeting_details.get("start_time")
    if not isinstance(start_time, datetime):
        return {
            **meeting_details,
            "status": "incomplete",
            "reason": "Date/time not specified.",
        }

    attendees = meeting_details.get("attendees", [])
    if not isinstance(attendees, list):
        attendees = []
        meeting_details["attendees"] = attendees

    if len(attendees) == 0:
        return {
            **meeting_details,
            "status": "no_attendees",
            "reason": "No attendees specified",
        }

    if start_time < datetime.now() or (start_time - datetime.now()).total_seconds() < 18000:
        return {
            **meeting_details,
            "status": "too_soon",
            "reason": "Meeting is too soon (less than 5 hours from now)",
        }

    if is_japanese_working_hours(start_time):
        return {
            **meeting_details,
            "status": "not_working_hours",
            "reason": "JST working hours (9am-7pm on working days)",
        }

    return {
        **meeting_details,
        "status": "valid",
        "reason": "none",
    }


def is_ai_decision_usable(meeting_details: dict) -> bool:
    if meeting_details.get("decision_source") != "ai":
        return False
    if meeting_details.get("status") not in {"valid", "incomplete", "no_attendees", "too_soon", "not_working_hours"}:
        return False
    if meeting_details.get("status") == "valid":
        if not isinstance(meeting_details.get("start_time"), datetime):
            return False
        attendees = meeting_details.get("attendees", [])
        if not isinstance(attendees, list) or len(attendees) == 0:
            return False
    return True



@app.get("/")
def home():
    return FileResponse("mobile_ui.html")


async def root():
    return {"message": "Calendar Automation API is running"}


def resolve_redirect_uri(request: Request) -> str:
    configured = os.getenv("GOOGLE_REDIRECT_URI")
    if configured:
        return configured
    return str(request.url_for("google_auth_callback"))



@app.post("/schedule")
async def schedule_meeting(text_command: TextCommand, background_tasks: BackgroundTasks):
    """
    Smart scheduling:
    - If it's a Japanese working day (Mon-Fri, not holiday) AND time is 9am-7pm → Just say "Booked"
    Example: "schedule a meet at 3pm next sunday, topic is interview with alex"
    """
    try:
        # Parse the natural language command
        meeting_details = await meeting_parser.parse(text_command.command, text_command.history)
        if not is_ai_decision_usable(meeting_details):
            meeting_details = apply_hardcoded_fallback_rules(meeting_details)

        if meeting_details.get("status") != "valid":
            return cancellation_response(
                meeting_details.get("status", "incomplete"),
                meeting_details.get("reason", "Incomplete meeting details."),
            )

        # Otherwise, actually schedule the meeting with Google Meet
        start_time = meeting_details["start_time"]
        duration_minutes = meeting_details.get("duration", 30)
        if has_overlapping_event(start_time, duration_minutes):
            return cancellation_response("conflict", "Meeting overlaps with an existing calendar event")

        event = calendar_service.create_event(
            summary=meeting_details["topic"],
            start_time=start_time,
            duration_minutes=duration_minutes,
            description=meeting_details.get("description", ""),
            attendees=meeting_details.get("attendees", []),
            add_meet_link=True  # Add Google Meet link
        )

        background_tasks.add_task(
            send_meeting_notifications,
            event,
            start_time,
            duration_minutes,
            meeting_details["topic"]
        )

        return {
            "status": meeting_details["status"],
            "message": f"Meeting scheduled: {meeting_details['topic']}",
            "meet_link": event.get("hangoutLink", "No meet link generated"),
            "event_id": event["id"],
            "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
            "duration": duration_minutes,
            "topic": meeting_details["topic"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/events/{event_id}")
async def update_event(event_id: str, payload: UpdateEventRequest):
    """
    Update an existing calendar event by event_id.
    """
    try:
        if (
            payload.summary is None
            and payload.start_time is None
            and payload.duration_minutes is None
            and payload.description is None
        ):
            raise HTTPException(status_code=400, detail="No update fields provided.")

        if payload.start_time is not None or payload.duration_minutes is not None:
            existing_event = calendar_service.get_event(event_id)
            existing_start = _parse_google_datetime(existing_event.get("start", {}).get("dateTime"))
            existing_end = _parse_google_datetime(existing_event.get("end", {}).get("dateTime"))
            if not existing_start or not existing_end:
                raise HTTPException(status_code=400, detail="Unable to read existing event time.")

            target_start = payload.start_time if payload.start_time is not None else existing_start
            if payload.duration_minutes is not None:
                target_duration = payload.duration_minutes
            else:
                target_duration = int((existing_end - existing_start).total_seconds() // 60)

            if has_overlapping_event(target_start, target_duration, exclude_event_id=event_id):
                raise HTTPException(
                    status_code=409,
                    detail="Updated time overlaps with an existing calendar event."
                )

        updated = calendar_service.update_event(
            event_id=event_id,
            summary=payload.summary,
            start_time=payload.start_time,
            duration_minutes=payload.duration_minutes,
            description=payload.description
        )

        return {
            "status": "updated",
            "event_id": updated.get("id", event_id),
            "summary": updated.get("summary"),
            "start": updated.get("start"),
            "end": updated.get("end"),
            "description": updated.get("description", "")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/events/{event_id}")
async def delete_event(event_id: str):
    """
    Delete an existing calendar event by event_id.
    """
    try:
        calendar_service.delete_event(event_id)
        return {"status": "deleted", "event_id": event_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/google")
@app.get("/auth/google")
async def google_auth(request: Request):
    """
    Initiates Google OAuth flow.
    Returns authorization URL for user to visit.
    """
    try:
        auth_url = calendar_service.get_auth_url(resolve_redirect_uri(request))
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/auth/callback")
async def google_auth_callback(request: Request, code: str):
    """
    Handles OAuth callback from Google.
    """
    try:
        calendar_service.handle_auth_callback(code, resolve_redirect_uri(request))
        response = {"status": "success", "message": "Authentication successful"}
        if os.getenv("RETURN_TOKEN_B64_IN_CALLBACK", "false").lower() == "true":
            response["google_token_pickle_b64"] = calendar_service.get_latest_token_pickle_b64()
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/auth/status")
async def auth_status():
    return {"authenticated": calendar_service.is_authenticated()}
