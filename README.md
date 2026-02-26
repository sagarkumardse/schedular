# Calendar Automation Tool

FastAPI-based Google Calendar automation with Japanese working hours detection and natural language scheduling.

## Features

- 🇯🇵 **Japanese Working Hours Detection**: Automatically detects Japanese working days (Mon-Fri, excluding holidays)
- 💬 **Smart Scheduling**: 
  - Working hours (9am-7pm on working days) → Returns "Booked"
  - Outside working hours → Creates actual meeting with Google Meet link
- 📱 **Mobile-Friendly API**: RESTful API designed for mobile app integration
- ✏️ **Natural Language**: Schedule/remove meetings with simple text commands

---

## How It Works

**Simple Logic:**

```
User: "schedule meet at 3pm next Wednesday, topic is interview with alex"

System checks:
1. Is it a Japanese working day? (Mon-Fri, not a holiday)
2. Is time between 9am-7pm?

If YES to both → Response: "Booked" (no actual meeting created)
If NO to either → Creates meeting + returns Google Meet link
```

**Examples:**
- `"meeting tomorrow at 2pm"` (Tuesday) → **"Booked"** (working hours)
- `"meeting tomorrow at 8pm"` (Tuesday) → **Scheduled** + Meet link (after hours)
- `"meeting Sunday at 3pm"` → **Scheduled** + Meet link (weekend)

---

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Google Calendar API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **Google Calendar API**
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/auth/callback`
5. Download credentials and save as `credentials.json` in project root

### 3. Groq API Setup

1. Get your API key from [Groq Console](https://console.groq.com/)
2. Create `.env` file:

```bash
cp .env.example .env
```

3. Add your Groq API key to `.env`:

```
GROQ_API_KEY=your_actual_groq_api_key
```

### 4. First Time Authentication

```bash
python main.py
```

Visit: `http://localhost:8000/auth/google`

This will redirect you to Google for authentication. After approval, you're ready to go!

---

## Usage

### Start the Server

```bash
uvicorn main:app --reload
```

API will be available at: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs`

### Test with Web UI

Open `mobile_ui.html` in your browser for a simple interface to test the API.

---

## API Endpoints

### 1. Schedule Meeting (Natural Language)

**POST** `/schedule`

```json
{
  "command": "schedule a meet at 3pm next sunday, topic is interview with alex"
}
```

**Response (Scheduled):**
```json
{
  "status": "scheduled",
  "message": "Meeting scheduled: Interview with Alex",
  "meet_link": "https://meet.google.com/xxx-yyyy-zzz",
  "event_id": "abc123...",
  "start_time": "2025-02-15 15:00",
  "duration": 30,
  "topic": "Interview with Alex"
}
```

**Response (Booked):**
```json
{
  "status": "booked",
  "message": "Booked",
  "reason": "Japanese working hours (9am-7pm on working days)",
  "requested_time": "2025-02-12 15:00",
  "topic": "Interview with Alex"
}
```

---

### 2. Remove Meeting

**POST** `/remove`

```json
{
  "command": "remove meeting at 3pm next sunday"
}
```

Or:

```json
{
  "command": "cancel interview with alex"
}
```

---

## Mobile Integration Example

### Using curl (test from terminal)

```bash
# Schedule a meeting
curl -X POST "http://localhost:8000/schedule" \
  -H "Content-Type: application/json" \
  -d '{"command": "meeting Sunday at 3pm about project review"}'

# Response will include Google Meet link if scheduled
# Response will just say "Booked" if during working hours

# Remove a meeting
curl -X POST "http://localhost:8000/remove" \
  -H "Content-Type: application/json" \
  -d '{"command": "cancel project review meeting"}'
```

### Mobile App Integration

**Example (JavaScript/React Native):**

```javascript
async function scheduleMeeting(textCommand) {
  const response = await fetch('http://your-server:8000/schedule', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command: textCommand })
  });
  
  const result = await response.json();
  
  if (result.status === 'booked') {
    alert('Booked - Japanese working hours');
  } else if (result.status === 'scheduled') {
    alert(`Meeting scheduled!\nMeet link: ${result.meet_link}`);
  }
}

// Usage
scheduleMeeting("meeting tomorrow at 2pm about sales review");
```

---

## Project Structure

```
.
├── main.py                  # FastAPI app with working hours logic
├── calendar_service.py      # Google Calendar API + Meet links
├── nlp_parser.py           # Groq-powered natural language parser
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── mobile_ui.html         # Simple web UI for testing
├── credentials.json       # Google OAuth credentials (you provide)
└── token.pickle          # Auto-generated after first auth
```

---

## Japanese Working Hours Logic

The system uses `jpholiday` library to determine working days:

```python
def is_japanese_working_hours(dt: datetime) -> bool:
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
```

**Returns "Booked" when:**
- Monday-Friday (not a holiday)
- Time is 9am-7pm

**Creates actual meeting when:**
- Weekend (Saturday/Sunday)
- Japanese national holiday
- Outside 9am-7pm hours
- Any combination of the above

---

## Natural Language Examples

The system understands various natural language formats:

```
✅ "meeting tomorrow at 2pm about Q4 planning"
✅ "schedule call next Friday at 10am"
✅ "book 30min meeting on monday at 4pm topic project review"
✅ "meeting with john@example.com and sarah@example.com tomorrow at 3pm"
✅ "schedule 90 minute meeting next Sunday at 2pm about strategy"
✅ "cancel meeting at 3pm next sunday"
✅ "remove interview with alex"
```

---

## Deployment

### For Production

1. **Use HTTPS** for OAuth callbacks
2. **Update redirect URI** in Google Cloud Console
3. **Deploy to cloud** (Railway, Render, Google Cloud Run, AWS, etc.)
4. **Set environment variables** on your platform
5. **Use production-grade server** (already using uvicorn)

---

## Troubleshooting

### "Not authenticated" error
Run: `http://localhost:8000/auth/google` and complete OAuth flow

### Groq parsing fails
Check your `.env` file has correct `GROQ_API_KEY`

### No Google Meet link generated
Ensure you're authenticated and have Calendar API permissions

### "Booked" appearing when it shouldn't
Check date/time - system uses Japanese timezone and calendar

---

## License

MIT
