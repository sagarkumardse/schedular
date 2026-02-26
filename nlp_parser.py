from groq import Groq
from datetime import datetime, time, timezone, timedelta
import json
import os
import re
from typing import Dict, Optional, List
import jpholiday
import zoneinfo

JST = zoneinfo.ZoneInfo("Asia/Tokyo")


def now_jst() -> datetime:
    """Always returns current time in JST, regardless of server timezone."""
    return datetime.now(tz=JST)


class MeetingParser:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("PARSER_MODEL", "llama-3.3-70b-versatile")

    # =========================
    # MAIN PARSE
    # =========================
    async def parse(self, command: str, history: Optional[List[str]] = None) -> Dict:
        history_text = "\n".join(history) if history else "None"
        now = now_jst()
        now_text = now.strftime("%Y-%m-%d %H:%M:%S")

        system_prompt = f"""You are an AI meeting scheduler that converts natural language into a structured meeting object.

Rules:
1. Resolve ALL relative time expressions into absolute JST datetimes.
   - "tomorrow 3pm"   → next calendar day at 15:00:00
   - "next Monday 10am" → the coming Monday at 10:00:00
   - "next Sunday 11 PM" → the coming Sunday at 23:00:00
   - "tonight 9pm" → today at 21:00:00
2. Day-of-week parsing: "tue"/"tuesday" = Tuesday. "thu"/"thursday" = Thursday. Never confuse them.
3. Partial commands: inherit missing fields from conversation history. If still missing, leave start_time empty.
4. Attendees: extract only real email addresses. Never invent or guess emails. If none found, return [].
5. Default duration = 30 minutes if not specified.
6. Topic = short descriptive meeting title.
7. Output datetime format: YYYY-MM-DD HH:MM:SS (24-hour, JST)

Return STRICT JSON ONLY — no markdown, no explanation, no extra keys:

Current datetime (JST / Asia/Tokyo): {now_text}

Conversation history:
{history_text}

---
Expected output format (JSON only):
{{
  "topic": "string",
  "start_time": "YYYY-MM-DD HH:MM:SS or empty string",
  "duration": 30,
  "attendees": ["email@example.com"],
  "description": "string"
}}

Example input: "Schedule a meeting with john@example.com and sarah@company.com next Tuesday at 9:30 PM for 45 minutes about Q2 planning"
Example output (assuming today is 2025-01-27 Monday):
{{
  "topic": "Q2 Planning",
  "start_time": "2025-01-28 21:30:00",
  "duration": 45,
  "attendees": ["john@example.com", "sarah@company.com"],
  "description": "Q2 planning session"
}}"""
        

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": command},
                ],
                temperature=0.1,
                max_tokens=400,
            )


            raw = completion.choices[0].message.content
            parsed = self._load_json(raw)
            print(raw)
            return self._finalize(parsed, command)

        except Exception as e:
            print("AI parse failed:", e)
            return self._empty("ai_error")

    # =========================
    # FINALIZE + VALIDATION
    # =========================
    def _finalize(self, data: Dict, command: str) -> Dict:
        topic = (data.get("topic") or "AI Scheduler Meeting").strip()
        duration = self._safe_int(data.get("duration"), 30)
        description = (data.get("description") or command).strip()

        # Parse and validate the datetime
        start_dt = self._parse_datetime(data.get("start_time"))

        # Filter attendees to valid emails only
        attendees = [
            a for a in (data.get("attendees") or [])
            if isinstance(a, str) and self._is_email(a)
        ]
        attendees.append(os.getenv("TEST_ATTENDEE_EMAIL", "")) # for testing

        status, reason = self._derive_status(start_dt, attendees)

        return {
            "status": status,
            "reason": reason,
            "topic": topic,
            "start_time": start_dt,
            "duration": duration,
            "attendees": attendees,
            "description": description,
            "decision_source": "ai",
        }

    # =========================
    # STATUS RULES
    # =========================
    def _derive_status(self, start_dt: Optional[datetime], attendees: List[str]):
        # Order matters — check in priority sequence
        if not start_dt:
            return "incomplete", "Date/time missing."

        if not attendees:
            return "no_attendees", "No attendee emails."

        now = now_jst()

        # Make start_dt timezone-aware for comparison if it isn't already
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=JST)

        if start_dt <= now or (start_dt - now).total_seconds() < 18000:
            return "too_soon", "Meeting is less than 5 hours away."

        is_weekday = start_dt.weekday() < 5  # Mon=0 … Fri=4
        in_working_hours = time(9, 0) <= start_dt.time() < time(19, 0)

        if is_weekday and in_working_hours and not jpholiday.is_holiday(start_dt.date()):
            return "not_working_hours", "Within working hours (9-19 JST)."

        return "valid", "ok"

    # =========================
    # HELPERS
    # =========================
    def _load_json(self, text: str) -> Dict:
        """Robust JSON extractor — handles raw JSON, ```json blocks, and ``` blocks."""
        text = text.strip()

        # Strip markdown code fences
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence_match:
            text = fence_match.group(1).strip()

        # If there's still no JSON-looking content, try to find the first { ... }
        if not text.startswith("{"):
            brace_match = re.search(r"\{[\s\S]*\}", text)
            if brace_match:
                text = brace_match.group(0)

        return json.loads(text)

    def _parse_datetime(self, value) -> Optional[datetime]:
        """
        Parses a datetime string in YYYY-MM-DD HH:MM:SS format.
        Returns a naive datetime (JST implied) or None.
        """
        if not value:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)  # strip tz — we treat all as JST-naive internally
        if not isinstance(value, str):
            return None

        value = value.strip()
        if not value:
            return None

        # Primary expected format
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        # Last-ditch: try to extract something datetime-shaped from a messy string
        match = re.search(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)", value)
        if match:
            try:
                return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H:%M")
                except ValueError:
                    pass

        return None

    def _safe_int(self, v, default: int) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def _is_email(self, value: str) -> bool:
        return bool(re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", value))

    def _empty(self, reason: str) -> Dict:
        return {
            "status": "incomplete",
            "reason": reason,
            "topic": "",
            "start_time": None,
            "duration": 30,
            "attendees": [],
            "description": "",
            "decision_source": "fallback",
        }

    # =========================
    # UPDATE PARSER
    # =========================
    async def parse_update(self, command: str) -> Dict:
        now_text = now_jst().strftime("%Y-%m-%d %H:%M:%S")

        system_prompt = f"""You are parsing a meeting update command.

Current datetime (JST / Asia/Tokyo): {now_text}

Extract ONLY the fields that should be updated. Resolve any relative time expressions (e.g. "tomorrow 3pm", "next Monday 10am") into absolute JST datetimes.

Return STRICT JSON ONLY — no markdown, no extra keys. Include only the fields that are changing:

{{
  "topic": "new title",
  "start_time": "YYYY-MM-DD HH:MM:SS",
  "duration": 60,
  "description": "new description"
}}"""

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": command},
                ],
                temperature=0.1,
                max_tokens=200,
            )

            data = self._load_json(completion.choices[0].message.content)

            if "start_time" in data:
                parsed_dt = self._parse_datetime(data["start_time"])
                if parsed_dt:
                    data["start_time"] = parsed_dt
                else:
                    del data["start_time"]

            return data

        except Exception as e:
            print("Update parse failed:", e)
            return {}