"""
This module provides utilities for authenticating with and using the Google Calendar API.
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

# Calendar API scopes
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# Type alias for the Calendar service
CalendarService = Resource


def get_calendar_service(
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
) -> CalendarService:
    """
    Authenticate with Google Calendar API and return the service object.
    Uses the same credentials as Gmail.

    Args:
        credentials_path: Path to the credentials JSON file
        token_path: Path to save/load the token

    Returns:
        Authenticated Calendar API service
    """
    import json

    creds = None

    # Look for token file with stored credentials
    if os.path.exists(token_path):
        with open(token_path, "r") as token:
            token_data = json.load(token)
            # Add calendar scopes to existing credentials
            creds = Credentials.from_authorized_user_info(token_data)

    # If credentials don't exist or are invalid, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Check if credentials file exists
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Credentials file not found at {credentials_path}. "
                    "Please download your OAuth credentials from Google Cloud Console."
                )

            # Combine Gmail and Calendar scopes
            from mcp_gmail.gmail import GMAIL_SCOPES

            all_scopes = list(set(GMAIL_SCOPES + CALENDAR_SCOPES))
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, all_scopes)
            creds = flow.run_local_server(port=0)

        # Save credentials for future runs
        token_json = json.loads(creds.to_json())
        with open(token_path, "w") as token:
            json.dump(token_json, token)

    # Build the Calendar service
    return build("calendar", "v3", credentials=creds)


def list_calendars(service: CalendarService) -> List[Dict[str, Any]]:
    """
    List all calendars accessible to the user.

    Args:
        service: Calendar API service instance

    Returns:
        List of calendar objects
    """
    result = service.calendarList().list().execute()
    return result.get("items", [])


def get_upcoming_events(
    service: CalendarService,
    calendar_id: str = "primary",
    max_results: int = 10,
    time_min: Optional[datetime] = None,
    time_max: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Get upcoming events from a calendar.

    Args:
        service: Calendar API service instance
        calendar_id: Calendar ID (default: 'primary')
        max_results: Maximum number of events to return
        time_min: Start time for event search (default: now)
        time_max: End time for event search (optional)

    Returns:
        List of event objects
    """
    if time_min is None:
        time_min = datetime.utcnow()

    # Format times for API
    time_min_str = time_min.isoformat() + "Z"
    time_max_str = time_max.isoformat() + "Z" if time_max else None

    # Call the Calendar API
    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min_str,
            timeMax=time_max_str,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return events_result.get("items", [])


def create_event(
    service: CalendarService,
    summary: str,
    start_time: datetime,
    end_time: datetime,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    calendar_id: str = "primary",
    send_notifications: bool = True,
) -> Dict[str, Any]:
    """
    Create a new calendar event.

    Args:
        service: Calendar API service instance
        summary: Event title/summary
        start_time: Event start time
        end_time: Event end time
        description: Event description (optional)
        location: Event location (optional)
        attendees: List of attendee email addresses (optional)
        calendar_id: Calendar ID (default: 'primary')
        send_notifications: Whether to send email notifications (default: True)

    Returns:
        Created event object
    """
    event = {
        "summary": summary,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "UTC",
        },
    }

    if description:
        event["description"] = description

    if location:
        event["location"] = location

    if attendees:
        event["attendees"] = [{"email": email} for email in attendees]

    created_event = (
        service.events()
        .insert(
            calendarId=calendar_id,
            body=event,
            sendUpdates="all" if send_notifications else "none",
        )
        .execute()
    )

    return created_event


def find_free_slots(
    service: CalendarService,
    attendees: List[str],
    duration_minutes: int = 60,
    search_days: int = 7,
    calendar_id: str = "primary",
) -> List[Dict[str, datetime]]:
    """
    Find free time slots for a meeting with specific attendees.

    Args:
        service: Calendar API service instance
        attendees: List of attendee email addresses
        duration_minutes: Meeting duration in minutes
        search_days: Number of days to search ahead
        calendar_id: Calendar ID (default: 'primary')

    Returns:
        List of dictionaries with 'start' and 'end' datetime objects
    """
    time_min = datetime.utcnow()
    time_max = time_min + timedelta(days=search_days)

    # Create freebusy query
    body = {
        "timeMin": time_min.isoformat() + "Z",
        "timeMax": time_max.isoformat() + "Z",
        "items": [{"id": email} for email in attendees + [calendar_id]],
    }

    freebusy_result = service.freebusy().query(body=body).execute()
    calendars = freebusy_result.get("calendars", {})

    # Collect all busy periods
    busy_periods = []
    for calendar_info in calendars.values():
        for busy in calendar_info.get("busy", []):
            start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))
            busy_periods.append((start, end))

    # Sort busy periods
    busy_periods.sort(key=lambda x: x[0])

    # Find free slots
    free_slots = []
    current_time = time_min

    # Only search during business hours (9 AM - 5 PM)
    while current_time < time_max:
        # Set to 9 AM of current day
        day_start = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
        if day_start < current_time:
            day_start += timedelta(days=1)

        day_end = day_start.replace(hour=17, minute=0)

        slot_start = day_start
        slot_end = slot_start + timedelta(minutes=duration_minutes)

        while slot_end <= day_end:
            # Check if slot conflicts with any busy period
            is_free = True
            for busy_start, busy_end in busy_periods:
                if (slot_start < busy_end) and (slot_end > busy_start):
                    is_free = False
                    slot_start = busy_end
                    slot_end = slot_start + timedelta(minutes=duration_minutes)
                    break

            if is_free and slot_end <= day_end:
                free_slots.append({"start": slot_start, "end": slot_end})
                if len(free_slots) >= 5:  # Return top 5 slots
                    return free_slots
                slot_start += timedelta(minutes=30)  # Check every 30 minutes
                slot_end = slot_start + timedelta(minutes=duration_minutes)
            elif not is_free:
                continue
            else:
                break

        current_time = day_end + timedelta(days=1)

    return free_slots


def update_event(
    service: CalendarService,
    event_id: str,
    calendar_id: str = "primary",
    summary: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    send_notifications: bool = True,
) -> Dict[str, Any]:
    """
    Update an existing calendar event.

    Args:
        service: Calendar API service instance
        event_id: Event ID to update
        calendar_id: Calendar ID (default: 'primary')
        summary: New event title/summary (optional)
        start_time: New event start time (optional)
        end_time: New event end time (optional)
        description: New event description (optional)
        location: New event location (optional)
        send_notifications: Whether to send email notifications (default: True)

    Returns:
        Updated event object
    """
    # Get existing event
    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

    # Update fields
    if summary:
        event["summary"] = summary

    if start_time:
        event["start"] = {
            "dateTime": start_time.isoformat(),
            "timeZone": "UTC",
        }

    if end_time:
        event["end"] = {
            "dateTime": end_time.isoformat(),
            "timeZone": "UTC",
        }

    if description:
        event["description"] = description

    if location:
        event["location"] = location

    updated_event = (
        service.events()
        .update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
            sendUpdates="all" if send_notifications else "none",
        )
        .execute()
    )

    return updated_event


def delete_event(
    service: CalendarService,
    event_id: str,
    calendar_id: str = "primary",
    send_notifications: bool = True,
) -> None:
    """
    Delete a calendar event.

    Args:
        service: Calendar API service instance
        event_id: Event ID to delete
        calendar_id: Calendar ID (default: 'primary')
        send_notifications: Whether to send email notifications (default: True)
    """
    service.events().delete(
        calendarId=calendar_id,
        eventId=event_id,
        sendUpdates="all" if send_notifications else "none",
    ).execute()
