"""
Google Calendar Service - Supports two authentication modes:

1. PERSONAL_OAUTH: For testing with personal Gmail (accesses your own calendar)
2. DOMAIN_DELEGATION: For organization-wide access with service account + domain-wide delegation

The service manages an allowlist of calendars (SA emails) that can be queried.
"""

import os
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from dateutil import parser as date_parser
import pytz

# Google API imports
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


class CalendarService:
    """
    Singleton service for Google Calendar operations.
    
    Supports two modes:
    - Personal OAuth: For testing with your own Gmail
    - Domain-Wide Delegation: For org-wide access to multiple calendars
    """
    
    _instance = None
    _service = None
    _credentials = None
    _mode = None  # 'oauth' or 'service_account'
    
    # OAuth scopes:
    # - calendar.readonly: Check SA availability
    # - calendar.events: Create events on organizer's calendar and send invites
    SCOPES = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    # File paths
    OAUTH_CREDENTIALS_FILE = 'credentials.json'
    SERVICE_ACCOUNT_FILE = 'service_account.json'
    TOKEN_FILE = 'token.pickle'
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._service is None:
            self._authenticate()
    
    def _authenticate(self) -> None:
        """
        Authenticate with Google Calendar API.
        Tries service account first (for org-wide), falls back to OAuth (for personal).
        """
        # Try service account first (preferred for production)
        if Path(self.SERVICE_ACCOUNT_FILE).exists():
            if self._authenticate_service_account():
                return
        
        # Fall back to OAuth (for personal testing)
        if Path(self.OAUTH_CREDENTIALS_FILE).exists():
            if self._authenticate_oauth():
                return
        
        print("⚠️  No credentials found. Running in demo mode.")
        print(f"   For OAuth: save credentials as '{self.OAUTH_CREDENTIALS_FILE}'")
        print(f"   For Service Account: save key as '{self.SERVICE_ACCOUNT_FILE}'")
    
    def _authenticate_service_account(self) -> bool:
        """Authenticate using service account with domain-wide delegation."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.SERVICE_ACCOUNT_FILE,
                scopes=self.SCOPES
            )
            
            self._credentials = credentials
            self._service = build('calendar', 'v3', credentials=credentials)
            self._mode = 'service_account'
            
            print(f"✅ Authenticated with service account: {credentials.service_account_email}")
            return True
            
        except Exception as e:
            print(f"❌ Service account auth failed: {e}")
            return False
    
    def _authenticate_oauth(self) -> bool:
        """Authenticate using OAuth (for personal Gmail)."""
        creds = None
        token_path = Path(self.TOKEN_FILE)
        
        # Load existing token
        if token_path.exists():
            try:
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
                print(f"Error loading token: {e}")
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.OAUTH_CREDENTIALS_FILE, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"❌ OAuth flow failed: {e}")
                    return False
            
            # Save token
            try:
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                print(f"Warning: Could not save token: {e}")
        
        try:
            self._credentials = creds
            self._service = build('calendar', 'v3', credentials=creds)
            self._mode = 'oauth'
            print("✅ Authenticated with OAuth (personal Gmail)")
            return True
        except Exception as e:
            print(f"❌ Failed to build calendar service: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if the service is authenticated."""
        return self._service is not None
    
    def get_mode(self) -> Optional[str]:
        """Get the current authentication mode."""
        return self._mode
    
    # ==================== Calendar Operations ====================
    
    def get_calendars(self) -> List[Dict]:
        """Get list of accessible calendars."""
        if not self._service:
            return []
        
        try:
            calendar_list = self._service.calendarList().list().execute()
            return [
                {
                    'id': cal['id'],
                    'summary': cal.get('summary', 'Untitled'),
                    'primary': cal.get('primary', False)
                }
                for cal in calendar_list.get('items', [])
            ]
        except Exception as e:
            print(f"Error fetching calendars: {e}")
            return []
    
    def get_service_for_user(self, user_email: str):
        """
        Get a calendar service impersonating a specific user.
        Only works with service account + domain-wide delegation.
        
        Args:
            user_email: Email of the user to impersonate
            
        Returns:
            Calendar service for that user, or None if not possible
        """
        if self._mode != 'service_account':
            print(f"⚠️  Cannot impersonate users in OAuth mode. Using default service.")
            return self._service
        
        try:
            # Create delegated credentials
            delegated_creds = self._credentials.with_subject(user_email)
            return build('calendar', 'v3', credentials=delegated_creds)
        except Exception as e:
            print(f"❌ Failed to impersonate {user_email}: {e}")
            return None
    
    def get_free_busy(
        self,
        calendar_emails: List[str],
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, List[Dict]]:
        """
        Get free/busy information for multiple calendars.
        
        In OAuth mode: Only works for calendars shared with you
        In Service Account mode: Works for any user (with domain-wide delegation)
        
        Args:
            calendar_emails: List of email addresses to check
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            Dict mapping email to list of busy periods
        """
        if not self._service:
            return {}
        
        # Ensure timezone awareness
        if start_time.tzinfo is None:
            start_time = pytz.UTC.localize(start_time)
        if end_time.tzinfo is None:
            end_time = pytz.UTC.localize(end_time)
        
        results = {}
        
        if self._mode == 'service_account':
            # With domain-wide delegation, we can query each user's calendar by impersonating them
            for email in calendar_emails:
                try:
                    user_service = self.get_service_for_user(email)
                    if user_service:
                        body = {
                            "timeMin": start_time.isoformat(),
                            "timeMax": end_time.isoformat(),
                            "items": [{"id": email}]
                        }
                        response = user_service.freebusy().query(body=body).execute()
                        cal_info = response.get('calendars', {}).get(email, {})
                        
                        if 'errors' in cal_info:
                            print(f"⚠️  Error for {email}: {cal_info['errors']}")
                            results[email] = []
                        else:
                            results[email] = cal_info.get('busy', [])
                except Exception as e:
                    print(f"❌ Error querying {email}: {e}")
                    results[email] = []
        else:
            # OAuth mode - query all at once (only works for shared calendars)
            try:
                body = {
                    "timeMin": start_time.isoformat(),
                    "timeMax": end_time.isoformat(),
                    "items": [{"id": email} for email in calendar_emails]
                }
                response = self._service.freebusy().query(body=body).execute()
                
                for email in calendar_emails:
                    cal_info = response.get('calendars', {}).get(email, {})
                    if 'errors' in cal_info:
                        print(f"⚠️  Cannot access {email}: {cal_info['errors']}")
                        results[email] = []
                    else:
                        results[email] = cal_info.get('busy', [])
                        
            except Exception as e:
                print(f"❌ Error querying free/busy: {e}")
                for email in calendar_emails:
                    results[email] = []
        
        return results
    
    def find_available_slots(
        self,
        calendar_emails: List[str],
        start_date: datetime,
        end_date: datetime,
        slot_duration_minutes: int = 60,
        work_start_hour: int = 9,
        work_end_hour: int = 17,
        timezone: str = 'America/Los_Angeles'
    ) -> List[Dict]:
        """
        Find available time slots across multiple calendars.
        
        Args:
            calendar_emails: List of email addresses to check
            start_date: Start of date range
            end_date: End of date range
            slot_duration_minutes: Duration of each slot
            work_start_hour: Start of working hours (default 9 AM)
            work_end_hour: End of working hours (default 5 PM)
            timezone: Timezone for working hours
            
        Returns:
            List of available slots with per-calendar availability
        """
        tz = pytz.timezone(timezone)
        
        # Get busy times for all calendars
        busy_times = self.get_free_busy(calendar_emails, start_date, end_date)
        
        # Parse busy times into datetime ranges
        parsed_busy = {}
        for email, periods in busy_times.items():
            parsed_busy[email] = []
            for period in periods:
                try:
                    start = date_parser.parse(period['start'])
                    end = date_parser.parse(period['end'])
                    parsed_busy[email].append((start, end))
                except Exception as e:
                    print(f"Error parsing busy period: {e}")
        
        # Generate slots
        available_slots = []
        current_date = start_date.date() if hasattr(start_date, 'date') else start_date
        end_date_only = end_date.date() if hasattr(end_date, 'date') else end_date
        
        while current_date <= end_date_only:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # Generate slots for working hours
            slot_start = tz.localize(
                datetime.combine(current_date, datetime.min.time().replace(hour=work_start_hour))
            )
            day_end = tz.localize(
                datetime.combine(current_date, datetime.min.time().replace(hour=work_end_hour))
            )
            
            while slot_start + timedelta(minutes=slot_duration_minutes) <= day_end:
                slot_end = slot_start + timedelta(minutes=slot_duration_minutes)
                
                # Check availability for each calendar
                availability = {}
                for email in calendar_emails:
                    is_available = True
                    for busy_start, busy_end in parsed_busy.get(email, []):
                        # Check for overlap
                        if not (slot_end <= busy_start or slot_start >= busy_end):
                            is_available = False
                            break
                    availability[email] = is_available
                
                # Include slot if at least one person is available
                if any(availability.values()):
                    available_slots.append({
                        'start': slot_start.isoformat(),
                        'end': slot_end.isoformat(),
                        'date': current_date.strftime('%Y-%m-%d'),
                        'time': slot_start.strftime('%I:%M %p'),
                        'availability': availability
                    })
                
                slot_start = slot_end
            
            current_date += timedelta(days=1)
        
        return available_slots
    
    def send_interview_invite(
        self,
        title: str,
        start_time: str,
        end_time: str,
        description: str = "",
        attendees: List[str] = None,
        organizer_email: str = None
    ) -> Optional[Dict]:
        """
        Send interview calendar invites via email with RSVP.
        
        Creates an event on the ORGANIZER's calendar and sends invites to all
        attendees (SA and candidate). They can Accept/Decline/Maybe.
        
        This does NOT require write access to attendees' calendars - only the
        organizer's calendar. Attendees receive email invites and the event
        appears on their calendar when they accept.
        
        Args:
            title: Event title (e.g., "Technical Interview - John Doe")
            start_time: ISO format start time
            end_time: ISO format end time
            description: Event description with details
            attendees: List of attendee email addresses (SA + candidate)
            organizer_email: Email of the organizer (optional, uses primary)
            
        Returns:
            Created event data with invite status, or None if failed
        """
        if not self._service:
            print("❌ Calendar service not authenticated")
            return None
        
        # Build event body
        event = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'UTC',
            },
            'guestsCanModify': False,
            'guestsCanInviteOthers': False,
            'guestsCanSeeOtherGuests': True,
        }
        
        # Add attendees - they will receive email invites with RSVP
        if attendees:
            event['attendees'] = [
                {'email': email, 'responseStatus': 'needsAction'} 
                for email in attendees
            ]
        
        # Add Google Meet video conference
        event['conferenceData'] = {
            'createRequest': {
                'requestId': f"interview-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'conferenceSolutionKey': {'type': 'hangoutsMeet'}
            }
        }
        
        try:
            # Create on organizer's primary calendar
            # This sends email invites to all attendees automatically
            created_event = self._service.events().insert(
                calendarId='primary',  # Organizer's calendar
                body=event,
                sendUpdates='all',  # Send email invites to all attendees
                conferenceDataVersion=1  # Required for Google Meet
            ).execute()
            
            meet_link = ''
            if 'conferenceData' in created_event:
                entry_points = created_event['conferenceData'].get('entryPoints', [])
                for ep in entry_points:
                    if ep.get('entryPointType') == 'video':
                        meet_link = ep.get('uri', '')
                        break
            
            print(f"✅ Interview invite sent!")
            print(f"   Event: {created_event.get('htmlLink')}")
            if meet_link:
                print(f"   Meet: {meet_link}")
            print(f"   📧 Invites sent to: {', '.join(attendees or [])}")
            
            return {
                'id': created_event.get('id'),
                'link': created_event.get('htmlLink'),
                'meet_link': meet_link,
                'start': created_event['start'].get('dateTime'),
                'end': created_event['end'].get('dateTime'),
                'attendees': [
                    {
                        'email': a.get('email'),
                        'status': a.get('responseStatus', 'needsAction')
                    }
                    for a in created_event.get('attendees', [])
                ],
                'invite_sent': True
            }
            
        except Exception as e:
            print(f"❌ Failed to send interview invite: {e}")
            return None
    
    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete a calendar event."""
        if not self._service:
            return False
        
        try:
            self._service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates='all'
            ).execute()
            print(f"✅ Calendar event deleted: {event_id}")
            return True
        except Exception as e:
            print(f"❌ Failed to delete event: {e}")
            return False


# Singleton getter
def get_calendar_service() -> CalendarService:
    """Get the singleton CalendarService instance."""
    return CalendarService()
