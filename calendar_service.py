from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import base64
import json
import os
import pickle
from typing import Optional, List, Dict
class CalendarService:
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    def __init__(self):
        self.token_file = os.getenv('GOOGLE_TOKEN_FILE', 'token.pickle')
        self.credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE', 'creds.json')
        self.credentials_json_b64 = os.getenv('GOOGLE_CREDENTIALS_JSON_B64')
        self.token_pickle_b64 = os.getenv('GOOGLE_TOKEN_PICKLE_B64')
        self.default_redirect_uri = os.getenv('GOOGLE_REDIRECT_URI')
        self.creds = None
        self.service = None
        self.latest_token_pickle_b64 = None
        self._load_credentials()

    def _decode_base64_to_bytes(self, value: str) -> bytes:
        cleaned = value.strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (
            cleaned.startswith("'") and cleaned.endswith("'")
        ):
            cleaned = cleaned[1:-1]
        cleaned = "".join(cleaned.split())
        cleaned = cleaned.replace("-", "+").replace("_", "/")
        padding = len(cleaned) % 4
        if padding:
            cleaned += "=" * (4 - padding)
        return base64.b64decode(cleaned)

    def _load_token_from_env(self) -> Optional[Credentials]:
        if not self.token_pickle_b64:
            return None
        try:
            token_bytes = self._decode_base64_to_bytes(self.token_pickle_b64)
            creds = pickle.loads(token_bytes)
            if isinstance(creds, Credentials):
                return creds
        except Exception:
            return None
        return None

    def _load_token_from_file(self) -> Optional[Credentials]:
        if not self.token_file or not os.path.exists(self.token_file):
            return None
        try:
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
            if isinstance(creds, Credentials):
                return creds
        except Exception:
            return None
        return None

    def _serialize_token_to_base64(self) -> Optional[str]:
        if not self.creds:
            return None
        try:
            token_bytes = pickle.dumps(self.creds)
            return base64.b64encode(token_bytes).decode('ascii')
        except Exception:
            return None

    def _persist_token(self):
        self.latest_token_pickle_b64 = self._serialize_token_to_base64()
        if self.creds and self.token_file:
            try:
                with open(self.token_file, 'wb') as token:
                    pickle.dump(self.creds, token)
            except Exception:
                pass

    def get_latest_token_pickle_b64(self) -> Optional[str]:
        if self.latest_token_pickle_b64:
            return self.latest_token_pickle_b64
        return self._serialize_token_to_base64()

    def _get_client_config(self) -> Dict:
        if self.credentials_json_b64:
            try:
                raw = self._decode_base64_to_bytes(self.credentials_json_b64).decode('utf-8')
                return json.loads(raw)
            except Exception:
                raise Exception("Invalid GOOGLE_CREDENTIALS_JSON_B64")

        if self.credentials_file and os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, 'r', encoding='utf-8') as fh:
                    return json.load(fh)
            except Exception:
                raise Exception(f"Invalid credentials file: {self.credentials_file}")

        raise Exception("Google OAuth client credentials not found. Set GOOGLE_CREDENTIALS_JSON_B64 or GOOGLE_CREDENTIALS_FILE.")

    def _build_flow(self, redirect_uri: str) -> Flow:
        client_config = self._get_client_config()
        return Flow.from_client_config(
            client_config,
            scopes=self.SCOPES,
            redirect_uri=redirect_uri
        )
    
    def _load_credentials(self):
        """Load credentials from env/token file and initialize Calendar service."""
        self.creds = self._load_token_from_env() or self._load_token_from_file()
        
        # Refresh if expired
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self._persist_token()
            except RefreshError:
                self.creds = None
                self.service = None
                if self.token_file and os.path.exists(self.token_file):
                    os.remove(self.token_file)
        
        if self.creds and self.creds.valid:
            self.service = build('calendar', 'v3', credentials=self.creds)
    
    def is_authenticated(self) -> bool:
        return self.service is not None

    def get_auth_url(self, redirect_uri: Optional[str] = None) -> str:
        """Get Google OAuth authorization URL."""
        resolved_redirect_uri = redirect_uri or self.default_redirect_uri
        if not resolved_redirect_uri:
            raise Exception("Redirect URI not configured.")

        flow = self._build_flow(resolved_redirect_uri)
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        return auth_url
    
    def handle_auth_callback(self, code: str, redirect_uri: Optional[str] = None):
        """Handle OAuth callback and save credentials."""
        resolved_redirect_uri = redirect_uri or self.default_redirect_uri
        if not resolved_redirect_uri:
            raise Exception("Redirect URI not configured.")

        flow = self._build_flow(resolved_redirect_uri)
        flow.fetch_token(code=code)
        self.creds = flow.credentials
        
        # Save credentials to file if possible and always keep a base64 form in memory.
        self._persist_token()
        
        self.service = build('calendar', 'v3', credentials=self.creds)
    
    def create_event(
        self,
        summary: str,
        start_time: datetime,
        duration_minutes: int = 30,
        description: str = "",
        attendees: List[str] = None,
        timezone: str = "Asia/Tokyo",
        add_meet_link: bool = False
    ) -> Dict:
        """Create a calendar event with optional Google Meet link."""
        if not self.service:
            raise Exception("Not authenticated. Please authenticate first.")
        
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': timezone,
            },
        }
        
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
        
        # Add Google Meet conference
        if add_meet_link:
            event['conferenceData'] = {
                'createRequest': {
                    'requestId': f"meet-{start_time.timestamp()}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            }
        
        created_event = self.service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1 if add_meet_link else 0,
            sendUpdates='all' if attendees else 'none'
        ).execute()
        
        return created_event
    
    def create_busy_block(
        self,
        date: datetime,
        start_hour: int = 9,
        end_hour: int = 18,
        summary: str = "Busy",
        timezone: str = "Asia/Tokyo"
    ) -> Dict:
        """Create an all-day busy block (e.g., for holidays)."""
        start_time = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_time = date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': timezone,
            },
            'transparency': 'opaque',  # Shows as busy
        }
        
        created_event = self.service.events().insert(
            calendarId='primary',
            body=event
        ).execute()
        
        return created_event
    
    def get_events(
        self,
        start_time: str,
        end_time: str,
        max_results: int = 100
    ) -> List[Dict]:
        """Get events in a time range."""
        if not self.service:
            raise Exception("Not authenticated. Please authenticate first.")
        
        events_result = self.service.events().list(
            calendarId='primary',
            timeMin=start_time,
            timeMax=end_time,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])

    def get_event(self, event_id: str) -> Dict:
        """Get a single event by id."""
        if not self.service:
            raise Exception("Not authenticated. Please authenticate first.")

        return self.service.events().get(
            calendarId='primary',
            eventId=event_id
        ).execute()
    
    def find_events(
        self,
        start_time: Optional[datetime] = None,
        summary: Optional[str] = None
    ) -> List[Dict]:
        """Find events matching criteria."""
        if not self.service:
            raise Exception("Not authenticated. Please authenticate first.")
        
        # Search in a reasonable time window
        if start_time:
            time_min = (start_time - timedelta(hours=1)).isoformat() + 'Z'
            time_max = (start_time + timedelta(hours=1)).isoformat() + 'Z'
        else:
            time_min = datetime.now().isoformat() + 'Z'
            time_max = (datetime.now() + timedelta(days=30)).isoformat() + 'Z'
        
        events = self.get_events(time_min, time_max)
        
        # Filter by summary if provided
        if summary:
            events = [e for e in events if summary.lower() in e.get('summary', '').lower()]
        
        return events
    
    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start_time: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        description: Optional[str] = None,
        timezone: str = "Asia/Tokyo"
    ) -> Dict:
        """Update an existing event."""
        if not self.service:
            raise Exception("Not authenticated. Please authenticate first.")
        
        # Get existing event
        event = self.service.events().get(
            calendarId='primary',
            eventId=event_id
        ).execute()
        
        # Update fields
        if summary:
            event['summary'] = summary
        if description is not None:
            event['description'] = description
        if start_time:
            if duration_minutes:
                end_time = start_time + timedelta(minutes=duration_minutes)
            else:
                # Keep same duration
                old_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                old_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                duration = old_end - old_start
                end_time = start_time + duration
            
            event['start'] = {
                'dateTime': start_time.isoformat(),
                'timeZone': timezone,
            }
            event['end'] = {
                'dateTime': end_time.isoformat(),
                'timeZone': timezone,
            }
        
        updated_event = self.service.events().update(
            calendarId='primary',
            eventId=event_id,
            body=event
        ).execute()
        
        return updated_event
    
    def delete_event(self, event_id: str):
        """Delete an event."""
        if not self.service:
            raise Exception("Not authenticated. Please authenticate first.")
        
        self.service.events().delete(
            calendarId='primary',
            eventId=event_id
        ).execute()
