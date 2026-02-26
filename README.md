# Calendar Automation API

FastAPI service that parses natural language meeting requests, checks scheduling rules, and creates Google Calendar events with Meet links.

## Features

- Natural-language scheduling through Groq.
- Google OAuth2 authentication and Calendar integration.
- Conflict detection before event creation.
- Event update and delete APIs.
- Optional SMTP email notifications to host/attendees.
- Japanese holiday and working-hours logic using `jpholiday`.

## Tech Stack

- Python 3.10+
- FastAPI + Uvicorn
- Google Calendar API (`google-api-python-client`)
- Groq SDK

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create environment file:

```bash
copy .env.example .env
```

3. Add credentials and API keys in `.env`.

## Environment Variables

Required for core flow:

- `GROQ_API_KEY`: Groq API key.
- `GOOGLE_CREDENTIALS_FILE`: OAuth client secret file path (default: `creds.json`).
- `GOOGLE_CREDENTIALS_JSON_B64`: Base64 of `creds.json` (preferred for env-only deploy platforms).
- `GOOGLE_REDIRECT_URI`: OAuth callback URL, e.g. `http://localhost:8000/auth/callback`.

Optional defaults:

- `PARSER_MODEL` (default: `llama-3.3-70b-versatile`)
- `GOOGLE_TOKEN_FILE` (default: `token.pickle`)
- `GOOGLE_TOKEN_PICKLE_B64`: Base64 of `token.pickle` for fileless deploy.
- `RETURN_TOKEN_B64_IN_CALLBACK`: If `true`, callback response includes current token as base64.

Email notifications (optional):

- `SMTP_HOST`
- `SMTP_PORT` (default: `587`)
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM` (defaults to `SMTP_USERNAME`)
- `SMTP_USE_TLS` (`true`/`false`, default: `true`)

## Google OAuth Setup

1. In Google Cloud Console, enable **Google Calendar API**.
2. Create OAuth client credentials (Web app).
3. Add authorized redirect URI matching your env value, typically:
   - `http://localhost:8000/auth/callback`
4. Save downloaded JSON as `creds.json` in project root (or set `GOOGLE_CREDENTIALS_FILE` to another path).

### Env-Only Deploy (No File Upload Support)

1. Generate token once locally using normal OAuth flow.
2. Encode local files:

```bash
python scripts/encode_google_secrets.py --creds creds.json --token token.pickle
```

3. Copy output values into deployment environment variables:
   - `GOOGLE_CREDENTIALS_JSON_B64`
   - `GOOGLE_TOKEN_PICKLE_B64`
4. Deploy without uploading `creds.json` or `token.pickle`.

## Run

```bash
uvicorn main:app --reload --port 8000
```

App URLs:

- API docs: `http://localhost:8000/docs`
- UI: `http://localhost:8000/`

## Auth Flow

1. Open `GET /auth/google`.
2. Visit returned `auth_url`.
3. Complete consent screen.
4. Callback hits `GET /auth/callback`.
5. Check status via `GET /auth/status`.

## API Endpoints

- `POST /schedule`
  - Input: `{ "command": "...", "history": ["..."] }`
  - Creates event when parsed data is valid.
- `PUT /events/{event_id}`
  - Update summary/start/duration/description.
- `DELETE /events/{event_id}`
  - Delete calendar event.
- `GET|POST /auth/google`
  - Start OAuth flow.
- `GET /auth/callback`
  - OAuth callback handler.
- `GET /auth/status`
  - Authentication status.

## Quick Example

```bash
curl -X POST "http://localhost:8000/schedule" ^
  -H "Content-Type: application/json" ^
  -d "{\"command\":\"schedule a 30 minute meeting tomorrow at 8pm with user@example.com about release planning\"}"
```

## Test Script

Run the concurrent API test harness:

```bash
python test/test.py
```

Results are written to `scheduler_test_results.json`.

## Security Notes

- Do not commit `.env`, `token.pickle`, or `creds.json`.
- `.gitignore` is configured to exclude token/credentials files.
- If a key/token was ever committed, rotate it before pushing public code.
- `token.pickle` changes mostly due to short-lived access token refresh; usually you do not need to update env every refresh.
- Update `GOOGLE_TOKEN_PICKLE_B64` only when re-auth is required (for example refresh token revoked/expired).
