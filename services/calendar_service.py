"""
Google Calendar Service - Singleton pattern for calendar operations.
Handles OAuth flow and calendar availability queries.
"""

import os
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dateutil import parser as date_parser
import pytz

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


class CalendarService:
    """Singleton service for Google Calendar operations."""
    
    _instance = None
    _service = None
    _credentials = None
    
    # Required OAuth scopes
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._service is None:
            self._authenticate()
    
    def _get_credentials_path(self) -> Path:
        """Get path to credentials file from environment or default location."""
        creds_path = os.environ.get('GOOGLE_CREDENTIALS_JSON', 'credentials.json')
        return Path(creds_path)
    
    def _get_token_path(self) -> Path:
        """Get path to token pickle file."""
        return Path('token.pickle')
    
    def _authenticate(self) -> None:
        """Authenticate with Google Calendar API using OAuth."""
        token_path = self._get_token_path()
        creds_path = self._get_credentials_path()
        
        creds = None
        
        # Load existing token if available
        if token_path.exists():
            try:
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
                print(f"Error loading token: {e}")
                creds = None
        
        # Refresh or obtain new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    creds = None
            
            if not creds:
                if not creds_path.exists():
                    print(f"Credentials file not found at {creds_path}")
                    print("Please download OAuth credentials from Google Cloud Console")
                    return
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(creds_path), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"Error during OAuth flow: {e}")
                    return
            
            # Save token for future use
            try:
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                print(f"Error saving token: {e}")
        
        self._credentials = creds
        
        if creds:
            try:
                self._service = build('calendar', 'v3', credentials=creds)
            except Exception as e:
                print(f"Error building calendar service: {e}")
    
    def is_authenticated(self) -> bool:
        """Check if the service is authenticated."""
        return self._service is not None
    
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
    
    def get_events(
        self,
        calendar_id: str = 'primary',
        start_date: datetime = None,
        end_date: datetime = None,
        max_results: int = 100
    ) -> List[Dict]:
        """
        Get events from a calendar within a date range.
        
        Args:
            calendar_id: Calendar ID (default: 'primary')
            start_date: Start of date range (default: now)
            end_date: End of date range (default: 7 days from now)
            max_results: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        if not self._service:
            return []
        
        if start_date is None:
            start_date = datetime.now(pytz.UTC)
        if end_date is None:
            end_date = start_date + timedelta(days=7)
        
        # Ensure timezone awareness
        if start_date.tzinfo is None:
            start_date = pytz.UTC.localize(start_date)
        if end_date.tzinfo is None:
            end_date = pytz.UTC.localize(end_date)
        
        try:
            events_result = self._service.events().list(
                calendarId=calendar_id,
                timeMin=start_date.isoformat(),
                timeMax=end_date.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = []
            for event in events_result.get('items', []):
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                events.append({
                    'id': event['id'],
                    'summary': event.get('summary', 'Busy'),
                    'start': start,
                    'end': end,
                    'all_day': 'date' in event['start'],
                    'status': event.get('status', 'confirmed')
                })
            
            return events
            
        except Exception as e:
            print(f"Error fetching events: {e}")
            return []
    
    def get_free_busy(
        self,
        calendar_ids: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, List[Dict]]:
        """
        Get free/busy information for multiple calendars.
        
        Args:
            calendar_ids: List of calendar IDs to check
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary mapping calendar IDs to busy periods
        """
        if not self._service:
            return {}
        
        # Ensure timezone awareness
        if start_date.tzinfo is None:
            start_date = pytz.UTC.localize(start_date)
        if end_date.tzinfo is None:
            end_date = pytz.UTC.localize(end_date)
        
        try:
            body = {
                "timeMin": start_date.isoformat(),
                "timeMax": end_date.isoformat(),
                "items": [{"id": cal_id} for cal_id in calendar_ids]
            }
            
            result = self._service.freebusy().query(body=body).execute()
            
            busy_times = {}
            for cal_id, cal_info in result.get('calendars', {}).items():
                busy_times[cal_id] = [
                    {
                        'start': period['start'],
                        'end': period['end']
                    }
                    for period in cal_info.get('busy', [])
                ]
            
            return busy_times
            
        except Exception as e:
            print(f"Error fetching free/busy: {e}")
            return {}
    
    def find_available_slots(
        self,
        calendar_ids: List[str],
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
            calendar_ids: List of calendar IDs to check
            start_date: Start of date range
            end_date: End of date range
            slot_duration_minutes: Duration of each slot in minutes
            work_start_hour: Start of working hours (default 9 AM)
            work_end_hour: End of working hours (default 5 PM)
            timezone: Timezone for working hours
            
        Returns:
            List of available slot dictionaries with calendar availability
        """
        tz = pytz.timezone(timezone)
        
        # Get free/busy for all calendars
        busy_times = self.get_free_busy(calendar_ids, start_date, end_date)
        
        # Parse busy times into datetime objects
        parsed_busy = {}
        for cal_id, periods in busy_times.items():
            parsed_busy[cal_id] = [
                (
                    date_parser.parse(p['start']),
                    date_parser.parse(p['end'])
                )
                for p in periods
            ]
        
        available_slots = []
        current_date = start_date.date()
        end_date_only = end_date.date()
        
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
                for cal_id in calendar_ids:
                    is_available = True
                    for busy_start, busy_end in parsed_busy.get(cal_id, []):
                        # Check for overlap
                        if not (slot_end <= busy_start or slot_start >= busy_end):
                            is_available = False
                            break
                    availability[cal_id] = is_available
                
                # Only include slots where at least one person is available
                if any(availability.values()):
                    available_slots.append({
                        'start': slot_start.isoformat(),
                        'end': slot_end.isoformat(),
                        'date': current_date.strftime('%Y-%m-%d'),
                        'time': slot_start.strftime('%H:%M'),
                        'availability': availability
                    })
                
                slot_start = slot_end
            
            current_date += timedelta(days=1)
        
        return available_slots


# Singleton instance getter
def get_calendar_service() -> CalendarService:
    """Get the singleton CalendarService instance."""
    return CalendarService()


