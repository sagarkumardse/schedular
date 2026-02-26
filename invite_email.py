
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage

def send_meeting_notifications(event: dict, start_time: datetime, duration: int, topic: str):
    """
    Send notification emails to host and attendees for a scheduled meeting.
    Uses SMTP_* environment variables and is called as a background task.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM") or smtp_username
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    if not smtp_host or not smtp_from:
        return

    organizer = event.get("organizer", {}) or {}
    creator = event.get("creator", {}) or {}
    host_email = organizer.get("email") or creator.get("email")

    recipients = set()
    if host_email:
        recipients.add(host_email)

    for attendee in event.get("attendees", []) or []:
        attendee_email = attendee.get("email")
        if attendee_email:
            recipients.add(attendee_email)

    if not recipients:
        return

    meet_link = event.get("hangoutLink", "Not available")
    subject = f"Meeting Scheduled: {topic}"
    body = (
        f"A meeting has been scheduled.\n\n"
        f"Topic: {topic}\n"
        f"Start: {start_time.strftime('%Y-%m-%d %H:%M')}\n"
        f"Duration: {duration} minutes\n"
        f"Meet link: {meet_link}\n"
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)

            for recipient in recipients:
                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = smtp_from
                msg["To"] = recipient
                msg.set_content(body)
                server.send_message(msg)
    except Exception as exc:
        print(f"Notification email send failed: {exc}")

