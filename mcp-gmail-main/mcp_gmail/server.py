"""
Gmail MCP Server Implementation

This module provides a Model Context Protocol server for interacting with Gmail and Google Calendar.
It exposes Gmail messages as resources and provides tools for composing and sending emails,
as well as managing calendar events and scheduling meetings.
"""

import re
from datetime import datetime, timedelta
from typing import Optional

from mcp.server.fastmcp import FastMCP

from mcp_gmail.config import settings
from mcp_gmail.gmail import (
    create_draft,
    get_gmail_service,
    get_headers_dict,
    get_labels,
    get_message,
    get_thread,
    list_messages,
    modify_message_labels,
    parse_message_body,
    search_messages,
)
from mcp_gmail.gmail import send_email as gmail_send_email
from mcp_gmail.calendar import (
    get_calendar_service,
    list_calendars,
    get_upcoming_events,
    create_event,
    find_free_slots,
    update_event,
    delete_event,
)

# Initialize the Gmail service
service = get_gmail_service(
    credentials_path=settings.credentials_path, token_path=settings.token_path, scopes=settings.scopes
)

# Initialize the Calendar service
calendar_service = get_calendar_service(
    credentials_path=settings.credentials_path, token_path=settings.token_path
)

mcp = FastMCP(
    "Gmail & Calendar MCP Server",
    instructions="Access and interact with Gmail and Google Calendar. You can get messages, threads, search emails, send or compose new messages, manage calendar events, and schedule meetings.",  # noqa: E501
)

EMAIL_PREVIEW_LENGTH = 200


# Helper functions
def format_message(message):
    """Format a Gmail message for display."""
    headers = get_headers_dict(message)
    body = parse_message_body(message)

    # Extract relevant headers
    from_header = headers.get("From", "Unknown")
    to_header = headers.get("To", "Unknown")
    subject = headers.get("Subject", "No Subject")
    date = headers.get("Date", "Unknown Date")

    return f"""
From: {from_header}
To: {to_header}
Subject: {subject}
Date: {date}

{body}
"""


def validate_date_format(date_str):
    """
    Validate that a date string is in the format YYYY/MM/DD.

    Args:
        date_str: The date string to validate

    Returns:
        bool: True if valid, False otherwise
    """
    if not date_str:
        return True

    # Check format with regex
    if not re.match(r"^\d{4}/\d{2}/\d{2}$", date_str):
        return False

    # Validate the date is a real date
    try:
        datetime.strptime(date_str, "%Y/%m/%d")
        return True
    except ValueError:
        return False


# Resources
@mcp.resource("gmail://messages/{message_id}")
def get_email_message(message_id: str) -> str:
    """
    Get the content of an email message by its ID.

    Args:
        message_id: The Gmail message ID

    Returns:
        The formatted email content
    """
    message = get_message(service, message_id, user_id=settings.user_id)
    formatted_message = format_message(message)
    return formatted_message


@mcp.resource("gmail://threads/{thread_id}")
def get_email_thread(thread_id: str) -> str:
    """
    Get all messages in an email thread by thread ID.

    Args:
        thread_id: The Gmail thread ID

    Returns:
        The formatted thread content with all messages
    """
    thread = get_thread(service, thread_id, user_id=settings.user_id)
    messages = thread.get("messages", [])

    result = f"Email Thread (ID: {thread_id})\n"
    for i, message in enumerate(messages, 1):
        result += f"\n--- Message {i} ---\n"
        result += format_message(message)

    return result


# Tools
@mcp.tool()
def compose_email(
    to: str, subject: str, body: str, cc: Optional[str] = None, bcc: Optional[str] = None
) -> str:
    """
    Compose a new email draft.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)

    Returns:
        The ID of the created draft and its content
    """
    sender = service.users().getProfile(userId=settings.user_id).execute().get("emailAddress")
    draft = create_draft(
        service, sender=sender, to=to, subject=subject, body=body, user_id=settings.user_id, cc=cc, bcc=bcc
    )

    draft_id = draft.get("id")
    return f"""
Email draft created with ID: {draft_id}
To: {to}
Subject: {subject}
CC: {cc or ""}
BCC: {bcc or ""}
Body: {body[:EMAIL_PREVIEW_LENGTH]}{"..." if len(body) > EMAIL_PREVIEW_LENGTH else ""}
"""


@mcp.tool()
def send_email(
    to: str, subject: str, body: str, cc: Optional[str] = None, bcc: Optional[str] = None
) -> str:
    """
    Compose and send an email.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)

    Returns:
        Content of the sent email
    """
    sender = service.users().getProfile(userId=settings.user_id).execute().get("emailAddress")
    message = gmail_send_email(
        service, sender=sender, to=to, subject=subject, body=body, user_id=settings.user_id, cc=cc, bcc=bcc
    )

    message_id = message.get("id")
    return f"""
Email sent successfully with ID: {message_id}
To: {to}
Subject: {subject}
CC: {cc or ""}
BCC: {bcc or ""}
Body: {body[:EMAIL_PREVIEW_LENGTH]}{"..." if len(body) > EMAIL_PREVIEW_LENGTH else ""}
"""


@mcp.tool()
def search_emails(
    from_email: Optional[str] = None,
    to_email: Optional[str] = None,
    subject: Optional[str] = None,
    has_attachment: bool = False,
    is_unread: bool = False,
    after_date: Optional[str] = None,
    before_date: Optional[str] = None,
    label: Optional[str] = None,
    max_results: int = 10,
) -> str:
    """
    Search for emails using specific search criteria.

    Args:
        from_email: Filter by sender email
        to_email: Filter by recipient email
        subject: Filter by subject text
        has_attachment: Filter for emails with attachments
        is_unread: Filter for unread emails
        after_date: Filter for emails after this date (format: YYYY/MM/DD)
        before_date: Filter for emails before this date (format: YYYY/MM/DD)
        label: Filter by Gmail label
        max_results: Maximum number of results to return

    Returns:
        Formatted list of matching emails
    """
    # Validate date formats
    if after_date and not validate_date_format(after_date):
        return f"Error: after_date '{after_date}' is not in the required format YYYY/MM/DD"

    if before_date and not validate_date_format(before_date):
        return f"Error: before_date '{before_date}' is not in the required format YYYY/MM/DD"

    # Use search_messages to find matching emails
    messages = search_messages(
        service,
        user_id=settings.user_id,
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        has_attachment=has_attachment,
        is_unread=is_unread,
        after=after_date,
        before=before_date,
        labels=[label] if label else None,
        max_results=max_results,
    )

    result = f"Found {len(messages)} messages matching criteria:\n"

    for msg_info in messages:
        msg_id = msg_info.get("id")
        message = get_message(service, msg_id, user_id=settings.user_id)
        headers = get_headers_dict(message)

        from_header = headers.get("From", "Unknown")
        subject = headers.get("Subject", "No Subject")
        date = headers.get("Date", "Unknown Date")

        result += f"\nMessage ID: {msg_id}\n"
        result += f"From: {from_header}\n"
        result += f"Subject: {subject}\n"
        result += f"Date: {date}\n"

    return result


@mcp.tool()
def query_emails(query: str, max_results: int = 10) -> str:
    """
    Search for emails using a raw Gmail query string.

    Args:
        query: Gmail search query (same syntax as Gmail search box)
        max_results: Maximum number of results to return

    Returns:
        Formatted list of matching emails
    """
    messages = list_messages(service, user_id=settings.user_id, max_results=max_results, query=query)

    result = f'Found {len(messages)} messages matching query: "{query}"\n'

    for msg_info in messages:
        msg_id = msg_info.get("id")
        message = get_message(service, msg_id, user_id=settings.user_id)
        headers = get_headers_dict(message)

        from_header = headers.get("From", "Unknown")
        subject = headers.get("Subject", "No Subject")
        date = headers.get("Date", "Unknown Date")

        result += f"\nMessage ID: {msg_id}\n"
        result += f"From: {from_header}\n"
        result += f"Subject: {subject}\n"
        result += f"Date: {date}\n"

    return result


@mcp.tool()
def list_available_labels() -> str:
    """
    Get all available Gmail labels for the user.

    Returns:
        Formatted list of labels with their IDs
    """
    labels = get_labels(service, user_id=settings.user_id)

    result = "Available Gmail Labels:\n"
    for label in labels:
        label_id = label.get("id", "Unknown")
        name = label.get("name", "Unknown")
        type_info = label.get("type", "user")

        result += f"\nLabel ID: {label_id}\n"
        result += f"Name: {name}\n"
        result += f"Type: {type_info}\n"

    return result


@mcp.tool()
def mark_message_read(message_id: str) -> str:
    """
    Mark a message as read by removing the UNREAD label.

    Args:
        message_id: The Gmail message ID to mark as read

    Returns:
        Confirmation message
    """
    # Remove the UNREAD label
    result = modify_message_labels(
        service, user_id=settings.user_id, message_id=message_id, remove_labels=["UNREAD"], add_labels=[]
    )

    # Get message details to show what was modified
    headers = get_headers_dict(result)
    subject = headers.get("Subject", "No Subject")

    return f"""
Message marked as read:
ID: {message_id}
Subject: {subject}
"""


@mcp.tool()
def add_label_to_message(message_id: str, label_id: str) -> str:
    """
    Add a label to a message.

    Args:
        message_id: The Gmail message ID
        label_id: The Gmail label ID to add (use list_available_labels to find label IDs)

    Returns:
        Confirmation message
    """
    # Add the specified label
    result = modify_message_labels(
        service, user_id=settings.user_id, message_id=message_id, remove_labels=[], add_labels=[label_id]
    )

    # Get message details to show what was modified
    headers = get_headers_dict(result)
    subject = headers.get("Subject", "No Subject")

    # Get the label name for the confirmation message
    label_name = label_id
    labels = get_labels(service, user_id=settings.user_id)
    for label in labels:
        if label.get("id") == label_id:
            label_name = label.get("name", label_id)
            break

    return f"""
Label added to message:
ID: {message_id}
Subject: {subject}
Added Label: {label_name} ({label_id})
"""


@mcp.tool()
def remove_label_from_message(message_id: str, label_id: str) -> str:
    """
    Remove a label from a message.

    Args:
        message_id: The Gmail message ID
        label_id: The Gmail label ID to remove (use list_available_labels to find label IDs)

    Returns:
        Confirmation message
    """
    # Get the label name before we remove it
    label_name = label_id
    labels = get_labels(service, user_id=settings.user_id)
    for label in labels:
        if label.get("id") == label_id:
            label_name = label.get("name", label_id)
            break

    # Remove the specified label
    result = modify_message_labels(
        service, user_id=settings.user_id, message_id=message_id, remove_labels=[label_id], add_labels=[]
    )

    # Get message details to show what was modified
    headers = get_headers_dict(result)
    subject = headers.get("Subject", "No Subject")

    return f"""
Label removed from message:
ID: {message_id}
Subject: {subject}
Removed Label: {label_name} ({label_id})
"""


@mcp.tool()
def get_emails(message_ids: list[str]) -> str:
    """
    Get the content of multiple email messages by their IDs.

    Args:
        message_ids: A list of Gmail message IDs

    Returns:
        The formatted content of all requested emails
    """
    if not message_ids:
        return "No message IDs provided."

    # Fetch all emails first
    retrieved_emails = []
    error_emails = []

    for msg_id in message_ids:
        try:
            message = get_message(service, msg_id, user_id=settings.user_id)
            retrieved_emails.append((msg_id, message))
        except Exception as e:
            error_emails.append((msg_id, str(e)))

    # Build result string after fetching all emails
    result = f"Retrieved {len(retrieved_emails)} emails:\n"

    # Format all successfully retrieved emails
    for i, (msg_id, message) in enumerate(retrieved_emails, 1):
        result += f"\n--- Email {i} (ID: {msg_id}) ---\n"
        result += format_message(message)

    # Report any errors
    if error_emails:
        result += f"\n\nFailed to retrieve {len(error_emails)} emails:\n"
        for i, (msg_id, error) in enumerate(error_emails, 1):
            result += f"\n--- Email {i} (ID: {msg_id}) ---\n"
            result += f"Error: {error}\n"

    return result


# ========================
# Calendar Tools
# ========================


@mcp.tool()
def get_calendar_events(
    max_results: int = 10,
    days_ahead: int = 7,
    calendar_id: str = "primary",
) -> str:
    """
    Get upcoming calendar events.

    Args:
        max_results: Maximum number of events to return
        days_ahead: Number of days to look ahead
        calendar_id: Calendar ID (default: 'primary')

    Returns:
        Formatted list of upcoming events
    """
    time_min = datetime.utcnow()
    time_max = time_min + timedelta(days=days_ahead)

    events = get_upcoming_events(
        calendar_service,
        calendar_id=calendar_id,
        max_results=max_results,
        time_min=time_min,
        time_max=time_max,
    )

    if not events:
        return f"No upcoming events found in the next {days_ahead} days."

    result = f"Upcoming events (next {days_ahead} days):\n\n"

    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        summary = event.get("summary", "No Title")
        location = event.get("location", "No location")
        description = event.get("description", "No description")

        result += f"Event: {summary}\n"
        result += f"Start: {start}\n"
        result += f"End: {end}\n"
        result += f"Location: {location}\n"
        result += f"Description: {description}\n"
        result += f"Event ID: {event['id']}\n\n"

    return result


@mcp.tool()
def schedule_meeting(
    title: str,
    start_datetime: str,
    duration_minutes: int,
    attendees: list[str],
    description: Optional[str] = None,
    location: Optional[str] = None,
) -> str:
    """
    Schedule a new meeting/calendar event.

    Args:
        title: Meeting title
        start_datetime: Start date and time in ISO format (e.g., "2024-01-15T14:00:00")
        duration_minutes: Meeting duration in minutes
        attendees: List of attendee email addresses
        description: Meeting description (optional)
        location: Meeting location (optional)

    Returns:
        Confirmation with event details
    """
    try:
        start_time = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
    except ValueError:
        return f"Error: Invalid datetime format '{start_datetime}'. Use ISO format like '2024-01-15T14:00:00'"

    end_time = start_time + timedelta(minutes=duration_minutes)

    event = create_event(
        calendar_service,
        summary=title,
        start_time=start_time,
        end_time=end_time,
        description=description,
        location=location,
        attendees=attendees,
    )

    result = f"Meeting scheduled successfully!\n\n"
    result += f"Title: {title}\n"
    result += f"Start: {start_time.isoformat()}\n"
    result += f"End: {end_time.isoformat()}\n"
    result += f"Duration: {duration_minutes} minutes\n"
    result += f"Attendees: {', '.join(attendees)}\n"
    if location:
        result += f"Location: {location}\n"
    if description:
        result += f"Description: {description}\n"
    result += f"\nEvent ID: {event['id']}\n"
    result += f"Event Link: {event.get('htmlLink', 'N/A')}\n"

    return result


@mcp.tool()
def find_meeting_times(
    attendees: list[str],
    duration_minutes: int = 60,
    days_to_search: int = 7,
) -> str:
    """
    Find available time slots for a meeting with specific attendees.

    Args:
        attendees: List of attendee email addresses
        duration_minutes: Meeting duration in minutes
        days_to_search: Number of days to search ahead

    Returns:
        List of available time slots
    """
    free_slots = find_free_slots(
        calendar_service,
        attendees=attendees,
        duration_minutes=duration_minutes,
        search_days=days_to_search,
    )

    if not free_slots:
        return f"No available time slots found for a {duration_minutes}-minute meeting in the next {days_to_search} days."

    result = f"Found {len(free_slots)} available time slots for a {duration_minutes}-minute meeting:\n\n"

    for i, slot in enumerate(free_slots, 1):
        start = slot["start"]
        end = slot["end"]
        result += f"{i}. {start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%H:%M')} UTC\n"
        result += f"   (ISO format: {start.isoformat()})\n\n"

    result += "\nUse schedule_meeting() with one of these times to create the meeting."

    return result


@mcp.tool()
def list_all_calendars() -> str:
    """
    List all calendars accessible to the user.

    Returns:
        Formatted list of calendars
    """
    calendars = list_calendars(calendar_service)

    if not calendars:
        return "No calendars found."

    result = "Available calendars:\n\n"

    for cal in calendars:
        cal_id = cal.get("id", "Unknown")
        summary = cal.get("summary", "No name")
        primary = " (PRIMARY)" if cal.get("primary", False) else ""
        access_role = cal.get("accessRole", "Unknown")

        result += f"Calendar: {summary}{primary}\n"
        result += f"ID: {cal_id}\n"
        result += f"Access Role: {access_role}\n\n"

    return result


@mcp.tool()
def suggest_meeting_from_email(
    email_message_id: str,
    duration_minutes: int = 60,
) -> str:
    """
    Analyze an email and suggest meeting times based on the content.
    This tool reads the email, extracts potential attendees, and finds available time slots.

    Args:
        email_message_id: Gmail message ID to analyze
        duration_minutes: Suggested meeting duration in minutes

    Returns:
        Email summary with suggested meeting times
    """
    # Get the email
    message = get_message(service, email_message_id, user_id=settings.user_id)
    headers = get_headers_dict(message)
    body = parse_message_body(message)

    from_header = headers.get("From", "Unknown")
    subject = headers.get("Subject", "No Subject")

    # Extract email address from "Name <email>" format
    import re as regex

    from_match = regex.search(r"<(.+?)>", from_header)
    from_email = from_match.group(1) if from_match else from_header

    # Find available times
    attendees = [from_email]
    free_slots = find_free_slots(
        calendar_service,
        attendees=attendees,
        duration_minutes=duration_minutes,
        search_days=7,
    )

    result = f"Email Analysis:\n"
    result += f"From: {from_header}\n"
    result += f"Subject: {subject}\n\n"
    result += f"Email Preview:\n{body[:300]}{'...' if len(body) > 300 else ''}\n\n"

    if free_slots:
        result += f"--- Suggested Meeting Times ({duration_minutes} minutes) ---\n\n"
        for i, slot in enumerate(free_slots[:3], 1):  # Show top 3
            start = slot["start"]
            end = slot["end"]
            result += f"{i}. {start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%H:%M')} UTC\n"
            result += f"   To schedule: use schedule_meeting() with start_datetime='{start.isoformat()}'\n\n"
    else:
        result += "No available time slots found in the next 7 days.\n"

    return result


if __name__ == "__main__":
    mcp.settings.port = 8090
    mcp.settings.host = "127.0.0.1"
    mcp.run(transport="sse")
