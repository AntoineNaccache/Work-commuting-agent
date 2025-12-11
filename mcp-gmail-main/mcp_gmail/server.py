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
    download_attachment,
    get_attachments,
    get_gmail_service,
    get_headers_dict,
    get_labels,
    get_message,
    get_pdf_attachments_text,
    get_thread,
    list_messages,
    modify_message_labels,
    parse_message_body,
    search_messages,
)
from mcp_gmail.gmail import send_email as gmail_send_email
from mcp_gmail.gcalendar import (
    CALENDAR_SCOPES,
    get_calendar_service,
    list_calendars,
    get_upcoming_events,
    create_event,
    find_free_slots,
    update_event,
    delete_event,
)
from mcp_gmail.sandbox_service import (
    SandboxBrowser,
    SandboxFileViewer,
    extract_urls_from_email,
    format_safety_report,
)

# Combine Gmail and Calendar scopes for single OAuth flow
ALL_SCOPES = list(set(settings.scopes + CALENDAR_SCOPES))

# Initialize the Gmail service with combined scopes
service = get_gmail_service(
    credentials_path=settings.credentials_path, token_path=settings.token_path, scopes=ALL_SCOPES
)

# Initialize the Calendar service (will reuse the same token with all scopes)
calendar_service = get_calendar_service(
    credentials_path=settings.credentials_path, token_path=settings.token_path
)

# Initialize sandbox service (optional - only if E2B_API_KEY is set)
sandbox_browser = None
sandbox_file_viewer = None
sandbox_enabled = False

try:
    if settings.e2b_api_key:
        sandbox_browser = SandboxBrowser(api_key=settings.e2b_api_key, timeout=settings.sandbox_timeout)
        sandbox_file_viewer = SandboxFileViewer(api_key=settings.e2b_api_key, timeout=settings.sandbox_timeout)
        sandbox_enabled = True
except Exception as e:
    print(f"Warning: Sandbox service not available: {e}")
    sandbox_enabled = False

mcp = FastMCP(
    "Gmail & Calendar MCP Server",
    instructions="""Access and interact with Gmail and Google Calendar. You can get messages, threads, search emails, send or compose new messages, manage calendar events, and schedule meetings.

SANDBOX SECURITY FEATURES:
- Use scan_email_for_threats(message_id) to comprehensively scan emails for malicious links and dangerous files
- Use preview_link_safely(url) to open and analyze suspicious links in a secure sandbox
- Use preview_file_safely(message_id, filename) to safely preview email attachments
- Use extract_email_links(message_id) to list all URLs in an email before scanning
- All sandbox tools require E2B_API_KEY to be configured (get free key from https://e2b.dev)

PDF ATTACHMENT SUPPORT:
- Use search_emails_with_pdf_attachments() to find emails with PDFs (great for boarding passes!)
- Use list_attachments() to see what files are attached to emails
- Use extract_pdf_text() to read PDF boarding passes, tickets, invoices, and bills
- The extract_flight_info() tool automatically checks PDFs for flight details

BEST PRACTICES:
1. ALWAYS read email content with get_emails() before taking actions (labeling, scheduling, etc.)
2. Use search_flight_bookings() for finding flights instead of generic search terms
3. When user says "look for emails with PDF attachments", use search_emails_with_pdf_attachments()
4. Use extract_flight_info() to parse flight details (checks both email body and PDFs)
5. For emails with attachments, use list_attachments() first, then extract_pdf_text() to read them
6. The schedule_meeting() tool automatically checks for duplicates and past dates
7. Use query_emails() with Gmail search syntax for complex searches (see tool documentation for examples)
8. When searching, exclude promotional terms: -price -deal -sale -offer -newsletter""",  # noqa: E501
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
    This uses the same powerful search syntax as the Gmail search box.

    Args:
        query: Gmail search query (same syntax as Gmail search box)
        max_results: Maximum number of results to return

    Returns:
        Formatted list of matching emails

    Examples of powerful Gmail search queries:
        - Find unread from specific sender: "from:john@example.com is:unread"
        - Multiple senders: "from:(alice OR bob)"
        - Date range: "after:2025/12/01 before:2025/12/31"
        - Exclude terms: "meeting -cancelled"
        - Has attachment: "has:attachment"
        - Subject search: "subject:(invoice OR receipt)"
        - Combine multiple: "from:airline (subject:booking OR subject:confirmation) -subject:price"

    Common patterns for specific use cases:
        - Flight bookings: "(booking OR reservation OR ticket) (flight OR airline) -price -deal"
        - Job applications: "from:(@linkedin.com OR @indeed.com OR @glassdoor.com) (application OR interview)"
        - Bills: "subject:(bill OR invoice OR statement) has:attachment"
        - Calendar invites: "subject:invitation filename:ics"
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
    # Get message details before marking as read
    message = get_message(service, message_id, user_id=settings.user_id)
    headers = get_headers_dict(message)
    subject = headers.get("Subject", "No Subject")
    from_header = headers.get("From", "Unknown")

    # Remove the UNREAD label
    modify_message_labels(
        service, user_id=settings.user_id, message_id=message_id, remove_labels=["UNREAD"], add_labels=[]
    )

    return f"""
Message marked as read:
ID: {message_id}
From: {from_header}
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
    # Get message details before modifying to show what was modified
    message = get_message(service, user_id=settings.user_id, message_id=message_id)
    headers = get_headers_dict(message)
    subject = headers.get("Subject", "No Subject")

    # Add the specified label
    modify_message_labels(
        service, user_id=settings.user_id, message_id=message_id, remove_labels=[], add_labels=[label_id]
    )

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
    # Get message details before modifying to show what was modified
    message = get_message(service, user_id=settings.user_id, message_id=message_id)
    headers = get_headers_dict(message)
    subject = headers.get("Subject", "No Subject")

    # Get the label name before we remove it
    label_name = label_id
    labels = get_labels(service, user_id=settings.user_id)
    for label in labels:
        if label.get("id") == label_id:
            label_name = label.get("name", label_id)
            break

    # Remove the specified label
    modify_message_labels(
        service, user_id=settings.user_id, message_id=message_id, remove_labels=[label_id], add_labels=[]
    )

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

    ⚠️ IMPORTANT: Always use this tool to examine email content before taking actions like:
    - Marking as spam or important
    - Adding/removing labels
    - Creating calendar events
    - Making decisions based on email type

    Reading the full email content helps avoid mistakes like:
    - Confusing price tracking emails with actual flight bookings
    - Marking non-job emails as job applications
    - Scheduling events that have already occurred
    - Creating duplicate calendar entries

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


@mcp.tool()
def mark_as_spam(message_id: str) -> str:
    """
    Mark a message as spam and move it to the spam folder.

    Args:
        message_id: The Gmail message ID to mark as spam

    Returns:
        Confirmation message
    """
    # Get message details before marking as spam
    message = get_message(service, message_id, user_id=settings.user_id)
    headers = get_headers_dict(message)
    subject = headers.get("Subject", "No Subject")
    from_header = headers.get("From", "Unknown")

    # Add SPAM label - Gmail automatically moves messages with SPAM label to spam folder
    modify_message_labels(
        service, user_id=settings.user_id, message_id=message_id, remove_labels=[], add_labels=["SPAM"]
    )

    return f"""
Message marked as spam and moved to spam folder:
ID: {message_id}
From: {from_header}
Subject: {subject}

The message has been labeled as SPAM and moved to your spam folder.
"""


@mcp.tool()
def list_attachments(message_id: str) -> str:
    """
    List all attachments in an email message.
    Useful for finding boarding passes, tickets, invoices, and other documents.

    Args:
        message_id: The Gmail message ID

    Returns:
        List of attachments with details (filename, type, size)
    """
    message = get_message(service, message_id, user_id=settings.user_id)
    headers = get_headers_dict(message)
    subject = headers.get("Subject", "No Subject")

    attachments = get_attachments(message)

    if not attachments:
        return f"""
No attachments found in message: {subject}
Message ID: {message_id}
"""

    result = f"""
Attachments in message: {subject}
Message ID: {message_id}

Found {len(attachments)} attachment(s):

"""

    for i, att in enumerate(attachments, 1):
        size_kb = att['size'] / 1024
        result += f"{i}. {att['filename']}\n"
        result += f"   Type: {att['mimeType']}\n"
        result += f"   Size: {size_kb:.1f} KB\n"
        if att['mimeType'] == 'application/pdf':
            result += f"   📄 PDF - Use extract_pdf_text() to read content\n"
        result += "\n"

    return result


@mcp.tool()
def extract_pdf_text(message_id: str, max_pdfs: int = 5) -> str:
    """
    Extract text content from PDF attachments in an email.
    Perfect for reading boarding passes, flight tickets, invoices, receipts, and bills.

    Args:
        message_id: The Gmail message ID
        max_pdfs: Maximum number of PDFs to process (default: 5)

    Returns:
        Extracted text from all PDF attachments

    Use cases:
        - Extract flight details from boarding passes
        - Read invoice/bill information
        - Parse ticket confirmations
        - Extract booking confirmations from PDF attachments
    """
    message = get_message(service, message_id, user_id=settings.user_id)
    headers = get_headers_dict(message)
    subject = headers.get("Subject", "No Subject")

    # Get all attachments first to show what's available
    all_attachments = get_attachments(message)
    pdf_attachments = [att for att in all_attachments if att['mimeType'] == 'application/pdf']

    if not pdf_attachments:
        return f"""
No PDF attachments found in message: {subject}
Message ID: {message_id}

Available attachments: {len(all_attachments)}
{chr(10).join(f"  - {att['filename']} ({att['mimeType']})" for att in all_attachments) if all_attachments else "  (none)"}

Tip: Use list_attachments() to see all attachments in detail.
"""

    result = f"""
PDF Text Extraction
━━━━━━━━━━━━━━━━━━━
Message: {subject}
Message ID: {message_id}
PDFs found: {len(pdf_attachments)}

"""

    # Extract text from PDFs
    pdf_texts = get_pdf_attachments_text(service, message, user_id=settings.user_id, max_pdfs=max_pdfs)

    if "error" in pdf_texts:
        return f"Error: {pdf_texts['error']}\n\nPlease install pypdf: pip install pypdf"

    for filename, text in pdf_texts.items():
        result += f"\n{'═' * 60}\n"
        result += f"📄 {filename}\n"
        result += f"{'═' * 60}\n\n"

        if text.startswith("Error"):
            result += f"⚠️  {text}\n"
        else:
            # Limit text length for display
            max_chars = 5000
            if len(text) > max_chars:
                result += text[:max_chars]
                result += f"\n\n... [Text truncated - {len(text) - max_chars} more characters]\n"
            else:
                result += text

        result += "\n"

    result += f"\n{'─' * 60}\n"
    result += "Next steps:\n"
    result += "- Use extract_flight_info() to parse flight details from the text\n"
    result += "- Use schedule_meeting() to add events to calendar\n"
    result += "- Copy important information for your records\n"

    return result


@mcp.tool()
def extract_flight_info(message_id: str, include_pdf_attachments: bool = True) -> str:
    """
    Extract flight information from an email message.
    This tool parses email content AND PDF attachments to find flight details like dates, times, airports, airlines, etc.

    Args:
        message_id: The Gmail message ID
        include_pdf_attachments: Also check PDF attachments for flight info (default: True)

    Returns:
        Extracted flight information in a structured format

    Note: PDF attachments often contain boarding passes and tickets with detailed flight information.
    """
    message = get_message(service, message_id, user_id=settings.user_id)
    headers = get_headers_dict(message)
    body = parse_message_body(message)
    subject = headers.get("Subject", "")

    # Common patterns for flight information
    patterns = {
        # Date patterns: Dec 11, 2025 or 12/11/2025 or December 11, 2025
        'dates': r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        # Time patterns: 10:35 AM, 1:25 PM, 17:30
        'times': r'\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?',
        # Airport codes: SFO, CDG, JFK (3 letters, uppercase)
        'airports': r'\b[A-Z]{3}\b',
        # Flight numbers: AF84, UA123
        'flight_numbers': r'\b[A-Z]{2}\s*\d{2,4}\b',
        # Airlines
        'airlines': r'(?:Air\s+France|United|Delta|American|British\s+Airways|Lufthansa|Emirates|Qatar|Singapore|TAP|Aeromexico|French\s+bee|Spirit)',
        # Booking references
        'booking_ref': r'(?:booking|confirmation|reference)(?:\s+(?:number|code|ref))?[:\s]+([A-Z0-9]{5,8})',
    }

    results = {
        'subject': subject,
        'dates': [],
        'times': [],
        'airports': [],
        'flight_numbers': [],
        'airlines': [],
        'booking_references': [],
    }

    # Start with subject and body
    search_text = f"{subject}\n{body}"
    sources = ["Email body"]

    # Also check PDF attachments if requested
    pdf_text = ""
    if include_pdf_attachments:
        pdf_texts = get_pdf_attachments_text(service, message, user_id=settings.user_id, max_pdfs=3)
        if pdf_texts and "error" not in pdf_texts:
            pdf_text = "\n\n".join(pdf_texts.values())
            search_text += f"\n\n{pdf_text}"
            sources.append(f"PDF attachments ({len(pdf_texts)} file(s))")
        elif pdf_texts and "error" in pdf_texts:
            # Note the PDF library issue but continue with email body
            sources.append("PDF attachments (unavailable)")

    # Search for patterns in all text

    for key, pattern in patterns.items():
        matches = re.findall(pattern, search_text, re.IGNORECASE)
        if matches:
            if key == 'booking_ref':
                # Extract just the reference code
                results['booking_references'] = list(set(matches))
            else:
                # Remove duplicates and sort
                results[key] = sorted(list(set(matches)))

    # Try to identify route from airports
    route = ""
    if len(results['airports']) >= 2:
        route = f"{results['airports'][0]} → {results['airports'][1]}"
        if len(results['airports']) > 2:
            route += f" (via {', '.join(results['airports'][2:])})"

    # Format output
    output = f"""
Flight Information Extraction
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Subject: {subject}
Sources checked: {', '.join(sources)}

"""

    if route:
        output += f"Route: {route}\n\n"

    if results['airlines']:
        output += f"Airlines: {', '.join(results['airlines'])}\n\n"

    if results['flight_numbers']:
        output += f"Flight Numbers: {', '.join(results['flight_numbers'])}\n\n"

    if results['dates']:
        output += f"Dates Found:\n"
        for date in results['dates'][:5]:  # Limit to first 5
            output += f"  • {date}\n"
        output += "\n"

    if results['times']:
        output += f"Times Found:\n"
        for time in results['times'][:5]:  # Limit to first 5
            output += f"  • {time}\n"
        output += "\n"

    if results['booking_references']:
        output += f"Booking References: {', '.join(results['booking_references'])}\n\n"

    if results['airports']:
        output += f"Airports: {', '.join(results['airports'])}\n\n"

    # Add recommendation
    output += """
Recommendation:
━━━━━━━━━━━━━━━
To schedule this flight as a calendar event, use the 'schedule_meeting' tool with:
- The extracted dates and times
- The route as the title or location
- Flight number and airline in the description
"""

    return output


@mcp.tool()
def search_emails_with_pdf_attachments(
    subject_keywords: Optional[str] = None,
    from_email: Optional[str] = None,
    after_date: Optional[str] = None,
    max_results: int = 20,
) -> str:
    """
    Search for emails that contain PDF attachments.
    Useful for finding boarding passes, tickets, invoices, and bills that are typically sent as PDFs.

    Args:
        subject_keywords: Keywords to search in subject (optional, e.g., "flight OR boarding OR ticket")
        from_email: Filter by sender email (optional)
        after_date: Filter for emails after this date in YYYY/MM/DD format (optional)
        max_results: Maximum number of results to return (default: 20)

    Returns:
        List of emails with PDF attachments and their details

    Examples:
        - Find all emails with PDFs: search_emails_with_pdf_attachments()
        - Find flight PDFs: search_emails_with_pdf_attachments(subject_keywords="flight OR boarding OR ticket")
        - Find recent invoices: search_emails_with_pdf_attachments(subject_keywords="invoice", after_date="2025/11/01")

    Pro tip: This is especially useful when the user says "look for emails with PDF attachments"
    """
    # Build Gmail search query that finds emails with PDF attachments
    # Gmail search uses filename:pdf to find PDF attachments
    query_parts = ['filename:pdf']

    if subject_keywords:
        query_parts.append(f'subject:({subject_keywords})')

    if from_email:
        query_parts.append(f'from:{from_email}')

    if after_date:
        if not validate_date_format(after_date):
            return f"Error: after_date '{after_date}' is not in the required format YYYY/MM/DD"
        query_parts.append(f'after:{after_date}')

    query = ' '.join(query_parts)

    # Execute search
    messages = list_messages(service, user_id=settings.user_id, max_results=max_results, query=query)

    result = f"Found {len(messages)} email(s) with PDF attachments:\n"
    result += f"Search query: {query}\n\n"

    if not messages:
        result += """
No emails with PDF attachments found matching criteria.

Tips:
- Try without keyword filters to see all PDFs
- Check the date range
- Some PDFs might be named differently
"""
        return result

    # Process each message
    for msg_info in messages:
        msg_id = msg_info.get("id")
        message = get_message(service, msg_id, user_id=settings.user_id)
        headers = get_headers_dict(message)

        from_header = headers.get("From", "Unknown")
        subject = headers.get("Subject", "No Subject")
        date = headers.get("Date", "Unknown Date")

        # Get PDF attachments
        attachments = get_attachments(message)
        pdf_attachments = [att for att in attachments if att['mimeType'] == 'application/pdf']

        result += f"{'─' * 60}\n"
        result += f"Message ID: {msg_id}\n"
        result += f"From: {from_header}\n"
        result += f"Subject: {subject}\n"
        result += f"Date: {date}\n"
        result += f"PDF Attachments: {len(pdf_attachments)}\n"

        for pdf in pdf_attachments[:3]:  # Show first 3 PDFs
            size_kb = pdf['size'] / 1024
            result += f"  📄 {pdf['filename']} ({size_kb:.1f} KB)\n"

        result += "\n"

    result += f"{'─' * 60}\n"
    result += f"\nNext steps:\n"
    result += f"1. Use list_attachments(message_id) to see all attachments in detail\n"
    result += f"2. Use extract_pdf_text(message_id) to read PDF content\n"
    result += f"3. Use extract_flight_info(message_id) to parse flight details from PDFs\n"

    return result


@mcp.tool()
def search_flight_bookings(
    departure_airport: Optional[str] = None,
    arrival_airport: Optional[str] = None,
    airline: Optional[str] = None,
    only_upcoming: bool = True,
    max_results: int = 20,
) -> str:
    """
    Search specifically for flight booking confirmations and boarding passes.
    This tool filters out price tracking emails and promotional content.
    Searches both email content AND PDF attachments.

    Args:
        departure_airport: 3-letter airport code (e.g., "CDG", "SFO")
        arrival_airport: 3-letter airport code
        airline: Airline name (e.g., "Air France", "TAP")
        only_upcoming: Only show future flights (default: True)
        max_results: Maximum number of results to return

    Returns:
        List of flight booking confirmations with details

    Examples:
        - Search for all flight bookings: search_flight_bookings()
        - Find Paris to SF flights: search_flight_bookings(departure_airport="CDG", arrival_airport="SFO")
        - Find TAP bookings: search_flight_bookings(airline="TAP")

    Tip: If you need flights with PDF boarding passes specifically, use:
         search_emails_with_pdf_attachments(subject_keywords="flight OR boarding OR ticket")
    """
    # Build comprehensive search query for flight bookings
    # Use Gmail search syntax to combine multiple terms
    query_parts = []

    # Look for booking-related terms (excluding price tracking)
    booking_terms = [
        '("booking confirmation" OR "ticket issued" OR "boarding pass" OR "flight confirmation")',
        '(subject:("booking" OR "reservation" OR "réservation" OR "ticket" OR "boarding"))',
        '-(subject:("price" OR "deal" OR "sale" OR "offer" OR "track" OR "newsletter"))',  # Exclude promotions
    ]
    query_parts.extend(booking_terms)

    # Add airport filters if provided
    if departure_airport:
        query_parts.append(f'("{departure_airport}")')
    if arrival_airport:
        query_parts.append(f'("{arrival_airport}")')

    # Add airline filter if provided
    if airline:
        query_parts.append(f'("{airline}")')

    # Date filter for upcoming flights
    if only_upcoming:
        # Get current date in Gmail format
        current_date = datetime.now().strftime("%Y/%m/%d")
        query_parts.append(f'after:{current_date}')

    # Combine query parts
    query = ' '.join(query_parts)

    # Execute search
    messages = list_messages(service, user_id=settings.user_id, max_results=max_results, query=query)

    result = f"Found {len(messages)} flight booking(s):\n"
    result += f"Search query: {query}\n\n"

    if not messages:
        result += """
No flight bookings found. Tips:
- Try without airport/airline filters to see all bookings
- Check if bookings are from different email addresses
- Some airlines use different subject line formats
- Try searching in different languages (e.g., French airlines may use "réservation")
"""
        return result

    # Process each message and extract flight info
    for msg_info in messages:
        msg_id = msg_info.get("id")
        message = get_message(service, msg_id, user_id=settings.user_id)
        headers = get_headers_dict(message)
        body = parse_message_body(message)

        from_header = headers.get("From", "Unknown")
        subject = headers.get("Subject", "No Subject")
        date = headers.get("Date", "Unknown Date")

        # Quick extraction of key details from body
        airports = re.findall(r'\b[A-Z]{3}\b', subject + " " + body[:500])
        flight_nums = re.findall(r'\b[A-Z]{2}\s*\d{2,4}\b', subject + " " + body[:500])

        result += f"{'─' * 60}\n"
        result += f"Message ID: {msg_id}\n"
        result += f"From: {from_header}\n"
        result += f"Subject: {subject}\n"
        result += f"Date: {date}\n"

        if airports:
            result += f"Airports mentioned: {', '.join(set(airports[:5]))}\n"
        if flight_nums:
            result += f"Flight numbers: {', '.join(set(flight_nums[:3]))}\n"

        result += "\n"

    result += f"{'─' * 60}\n"
    result += f"\nNext steps:\n"
    result += f"1. Use extract_flight_info(message_id) to get detailed flight information\n"
    result += f"2. Use get_emails([message_ids]) to read the full email content\n"
    result += f"3. Use schedule_meeting() to add flights to your calendar\n"

    return result


# ========================
# Sandbox Security Tools
# ========================


@mcp.tool()
def extract_email_links(message_id: str) -> str:
    """
    Extract all URLs from an email message.
    Useful for identifying links before scanning them for threats.

    Args:
        message_id: The Gmail message ID

    Returns:
        List of all URLs found in the email
    """
    message = get_message(service, message_id, user_id=settings.user_id)
    headers = get_headers_dict(message)
    body = parse_message_body(message)
    subject = headers.get("Subject", "No Subject")

    # Extract URLs from email body
    urls = extract_urls_from_email(body)

    if not urls:
        return f"""
No URLs found in message: {subject}
Message ID: {message_id}

This email does not contain any clickable links.
"""

    result = f"""
🔗 URLs Found in Email: {subject}
Message ID: {message_id}

Found {len(urls)} URL(s):

"""

    for i, url in enumerate(urls, 1):
        result += f"{i}. {url}\n"

    result += f"""
Next steps:
- Use preview_link_safely(url) to safely open and analyze each link
- Use scan_email_for_threats(message_id) to scan all links and attachments
"""

    return result


@mcp.tool()
def preview_link_safely(url: str, take_screenshot: bool = False) -> str:
    """
    Safely open and analyze a URL in a sandboxed browser environment.
    This tool opens the URL in an isolated E2B cloud sandbox, analyzes its content,
    checks for phishing patterns, and returns a safety assessment.

    Args:
        url: The URL to preview
        take_screenshot: Whether to capture a screenshot (default: False)

    Returns:
        Detailed safety report with content summary and threat assessment

    Note: Requires E2B_API_KEY to be set in environment variables.
          Get your free API key from https://e2b.dev
    """
    if not sandbox_enabled or not sandbox_browser:
        return """
❌ Sandbox service not available

The sandbox service requires an E2B API key to be configured.

Setup instructions:
1. Get a free API key from https://e2b.dev
2. Set environment variable: E2B_API_KEY=your_key_here
   (or MCP_GMAIL_E2B_API_KEY=your_key_here)
3. Restart the MCP server

The sandbox service allows you to safely preview links from emails
without compromising your system.
"""

    try:
        # Open URL in sandbox
        result = sandbox_browser.open_url(url, take_screenshot=take_screenshot)

        # Format the report
        report = format_safety_report(
            url=url,
            score=result['safety_score'],
            warnings=result['warnings'],
            content=result.get('content', ''),
            metadata={
                'Title': result.get('title', 'N/A'),
                'SSL Valid': '✅ Yes' if result['ssl_valid'] else '❌ No',
                'Status': '✅ Loaded successfully' if result['success'] else '❌ Failed to load'
            }
        )

        # Add screenshot info if available
        if result.get('screenshot'):
            report += "\n\n📸 Screenshot captured (base64 encoded)\n"

        # Add error details if any
        if result.get('error'):
            report += f"\n\n⚠️  Error details: {result['error']}\n"

        return report

    except Exception as e:
        return f"""
❌ Error previewing link

URL: {url}
Error: {str(e)}

This could be due to:
- Invalid URL format
- Network connectivity issues
- Sandbox timeout (URL took too long to load)
- E2B API rate limits

Please try again or check the URL manually in a safe environment.
"""


@mcp.tool()
def preview_file_safely(message_id: str, filename: str) -> str:
    """
    Safely open and analyze an email attachment in a sandboxed environment.
    This tool downloads the attachment, analyzes it in isolation, checks for
    threats, and returns a safety assessment with content preview.

    Args:
        message_id: The Gmail message ID containing the attachment
        filename: The name of the attachment to preview

    Returns:
        Detailed safety report with file analysis and content summary

    Note: Requires E2B_API_KEY to be set in environment variables.
          Get your free API key from https://e2b.dev
    """
    if not sandbox_enabled or not sandbox_file_viewer:
        return """
❌ Sandbox service not available

The sandbox service requires an E2B API key to be configured.

Setup instructions:
1. Get a free API key from https://e2b.dev
2. Set environment variable: E2B_API_KEY=your_key_here
   (or MCP_GMAIL_E2B_API_KEY=your_key_here)
3. Restart the MCP server

The sandbox service allows you to safely preview file attachments from emails
without compromising your system.
"""

    try:
        # Get the message and attachments
        message = get_message(service, message_id, user_id=settings.user_id)
        headers = get_headers_dict(message)
        subject = headers.get("Subject", "No Subject")
        attachments = get_attachments(message)

        # Find the specified attachment
        target_attachment = None
        for att in attachments:
            if att['filename'] == filename:
                target_attachment = att
                break

        if not target_attachment:
            available = "\n".join([f"  - {att['filename']}" for att in attachments])
            return f"""
❌ Attachment not found

Filename: {filename}
Message: {subject}
Message ID: {message_id}

Available attachments:
{available if attachments else '  (none)'}

Use list_attachments(message_id) to see all attachments with details.
"""

        # Download the attachment
        file_bytes = download_attachment(
            service,
            message_id,
            target_attachment['attachmentId'],
            user_id=settings.user_id
        )

        # Analyze in sandbox
        result = sandbox_file_viewer.open_file(
            file_bytes,
            filename,
            target_attachment['mimeType']
        )

        # Format the report
        report = format_safety_report(
            filename=filename,
            score=result['safety_score'],
            warnings=result['warnings'],
            content=result.get('content', ''),
            metadata={
                'File Type': result.get('file_type', 'Unknown'),
                'MIME Type': result['mime_type'],
                'Size': f"{result['size'] / 1024:.1f} KB",
                'From Email': subject
            }
        )

        # Add error details if any
        if result.get('error'):
            report += f"\n\n⚠️  Analysis error: {result['error']}\n"

        return report

    except Exception as e:
        return f"""
❌ Error previewing file

Filename: {filename}
Message ID: {message_id}
Error: {str(e)}

This could be due to:
- Attachment download failed
- Unsupported file type
- File analysis error
- Sandbox timeout

Please try again or use list_attachments() to verify the filename.
"""


@mcp.tool()
def scan_email_for_threats(message_id: str) -> str:
    """
    Comprehensively scan an email for security threats including malicious links
    and dangerous attachments. This tool analyzes all URLs and files in the email,
    providing a complete threat assessment.

    This is the recommended tool for checking if an email is safe before
    clicking links or opening attachments.

    Args:
        message_id: The Gmail message ID to scan

    Returns:
        Comprehensive threat report with overall risk assessment

    Note: Requires E2B_API_KEY to be set in environment variables.
          Get your free API key from https://e2b.dev
    """
    if not sandbox_enabled:
        return """
❌ Sandbox service not available

The sandbox service requires an E2B API key to be configured.

Setup instructions:
1. Get a free API key from https://e2b.dev
2. Set environment variable: E2B_API_KEY=your_key_here
   (or MCP_GMAIL_E2B_API_KEY=your_key_here)
3. Restart the MCP server
"""

    try:
        # Get email message
        message = get_message(service, message_id, user_id=settings.user_id)
        headers = get_headers_dict(message)
        body = parse_message_body(message)
        subject = headers.get("Subject", "No Subject")
        from_header = headers.get("From", "Unknown")

        # Extract URLs
        urls = extract_urls_from_email(body)

        # Get attachments
        attachments = get_attachments(message)

        # Initialize results
        link_results = []
        file_results = []
        overall_score = 100
        threat_count = 0

        # Scan each URL (limit to first 5 to avoid excessive API calls)
        for url in urls[:5]:
            try:
                result = sandbox_browser.open_url(url, take_screenshot=False)
                link_results.append({
                    'url': url,
                    'score': result['safety_score'],
                    'warnings': result['warnings'],
                    'title': result.get('title', 'N/A')
                })
                if result['safety_score'] < 70:
                    threat_count += 1
                overall_score = min(overall_score, result['safety_score'])
            except Exception as e:
                link_results.append({
                    'url': url,
                    'score': 50,
                    'warnings': [f'Scan error: {str(e)}'],
                    'title': 'Error'
                })

        # Scan each attachment (limit to first 5)
        for att in attachments[:5]:
            try:
                file_bytes = download_attachment(
                    service,
                    message_id,
                    att['attachmentId'],
                    user_id=settings.user_id
                )
                result = sandbox_file_viewer.open_file(
                    file_bytes,
                    att['filename'],
                    att['mimeType']
                )
                file_results.append({
                    'filename': att['filename'],
                    'score': result['safety_score'],
                    'warnings': result['warnings'],
                    'file_type': result.get('file_type', 'Unknown')
                })
                if result['safety_score'] < 70:
                    threat_count += 1
                overall_score = min(overall_score, result['safety_score'])
            except Exception as e:
                file_results.append({
                    'filename': att['filename'],
                    'score': 50,
                    'warnings': [f'Scan error: {str(e)}'],
                    'file_type': 'Error'
                })

        # Build report
        if overall_score >= 70:
            risk_emoji = '✅'
            risk_level = 'LOW'
        elif overall_score >= 40:
            risk_emoji = '⚠️ '
            risk_level = 'MEDIUM'
        else:
            risk_emoji = '❌'
            risk_level = 'HIGH'

        report = f"""
🔍 Email Threat Scan Complete

Subject: {subject}
From: {from_header}
Message ID: {message_id}

Overall Risk: {risk_emoji} {risk_level} (Score: {overall_score}/100)
Threats Detected: {threat_count}

{'=' * 60}

"""

        # Report on links
        if link_results:
            report += f"🔗 Links Found: {len(link_results)}\n\n"
            for i, link in enumerate(link_results, 1):
                score = link['score']
                if score >= 70:
                    emoji = '✅'
                    status = 'Safe'
                elif score >= 40:
                    emoji = '⚠️ '
                    status = 'Suspicious'
                else:
                    emoji = '❌'
                    status = 'DANGEROUS'

                report += f"{i}. {emoji} {link['url'][:60]}...\n"
                report += f"   Score: {score}/100 ({status})\n"
                if link['warnings']:
                    for warning in link['warnings'][:3]:  # Show top 3 warnings
                        report += f"   - {warning}\n"
                report += "\n"
        else:
            report += "🔗 Links Found: 0\n\n"

        # Report on attachments
        if file_results:
            report += f"📎 Attachments Found: {len(file_results)}\n\n"
            for i, file in enumerate(file_results, 1):
                score = file['score']
                if score >= 70:
                    emoji = '✅'
                    status = 'Safe'
                elif score >= 40:
                    emoji = '⚠️ '
                    status = 'Suspicious'
                else:
                    emoji = '❌'
                    status = 'DANGEROUS'

                report += f"{i}. {emoji} {file['filename']}\n"
                report += f"   Score: {score}/100 ({status})\n"
                report += f"   Type: {file['file_type']}\n"
                if file['warnings']:
                    for warning in file['warnings'][:3]:  # Show top 3 warnings
                        report += f"   - {warning}\n"
                report += "\n"
        else:
            report += "📎 Attachments Found: 0\n\n"

        # Final recommendation
        report += f"{'=' * 60}\n\n"
        report += "📋 Recommendation:\n"
        if overall_score >= 70:
            report += "✅ This email appears safe. No significant threats detected.\n"
        elif overall_score >= 40:
            report += "⚠️  Exercise caution. Review warnings before clicking links or opening files.\n"
        else:
            report += "❌ DANGER: This email contains high-risk content. DO NOT click links or open attachments.\n"

        return report

    except Exception as e:
        return f"""
❌ Error scanning email

Message ID: {message_id}
Error: {str(e)}

This could be due to:
- Invalid message ID
- Network connectivity issues
- Sandbox service error

Please try again or check individual links/files manually.
"""


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
    check_for_duplicates: bool = True,
) -> str:
    """
    Schedule a new meeting/calendar event.
    Automatically checks for duplicate events and warns about past dates.

    Args:
        title: Meeting title
        start_datetime: Start date and time in ISO format (e.g., "2024-01-15T14:00:00")
        duration_minutes: Meeting duration in minutes
        attendees: List of attendee email addresses
        description: Meeting description (optional)
        location: Meeting location (optional)
        check_for_duplicates: Check if similar event already exists (default: True)

    Returns:
        Confirmation with event details or warning about duplicates/past dates
    """
    try:
        start_time = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
    except ValueError:
        return f"Error: Invalid datetime format '{start_datetime}'. Use ISO format like '2024-01-15T14:00:00'"

    # Check if the event is in the past
    now = datetime.now()
    if start_time < now:
        days_ago = (now - start_time).days
        return f"""
⚠️  Warning: This event is in the PAST!

Event date: {start_time.strftime('%Y-%m-%d %H:%M')}
Current date: {now.strftime('%Y-%m-%d %H:%M')}
Days ago: {days_ago}

This event has already occurred. Please verify:
1. Is this the correct date?
2. Did you mean to schedule a future occurrence?
3. Are you trying to add a historical event to your calendar?

If you want to proceed anyway, you can still create the event, but it won't be useful for future planning.
"""

    end_time = start_time + timedelta(minutes=duration_minutes)

    # Check for duplicate events if enabled
    if check_for_duplicates:
        # Search for events around the same time (±1 day)
        time_min = start_time - timedelta(days=1)
        time_max = start_time + timedelta(days=1)

        existing_events = get_upcoming_events(
            calendar_service,
            calendar_id="primary",
            max_results=50,
            time_min=time_min,
            time_max=time_max,
        )

        # Check for similar events
        for event in existing_events:
            event_title = event.get('summary', '')
            event_start = event.get('start', {}).get('dateTime', '')
            event_location = event.get('location', '')

            # Check if similar title and location
            title_similar = title.lower() in event_title.lower() or event_title.lower() in title.lower()
            location_similar = False
            if location and event_location:
                location_similar = location.lower() in event_location.lower() or event_location.lower() in location.lower()

            # If event start time is within 2 hours of requested time
            if event_start:
                try:
                    existing_start = datetime.fromisoformat(event_start.replace("Z", "+00:00"))
                    time_diff = abs((existing_start - start_time).total_seconds() / 3600)  # hours

                    if time_diff < 2 and (title_similar or location_similar):
                        return f"""
⚠️  Potential duplicate event detected!

Existing event:
  Title: {event_title}
  Start: {existing_start.strftime('%Y-%m-%d %H:%M')}
  Location: {event_location}
  Event ID: {event.get('id', 'N/A')}

New event you're trying to create:
  Title: {title}
  Start: {start_time.strftime('%Y-%m-%d %H:%M')}
  Location: {location or 'N/A'}

These events appear to be the same or very similar. To avoid duplicates:
1. Check your calendar using get_calendar_events()
2. If this is a different event, proceed with a more specific title
3. If you want to create it anyway, you can modify the title to be more distinct

Would you like to proceed with creating this event anyway?
"""
                except Exception:
                    pass

    # Create the event
    event = create_event(
        calendar_service,
        summary=title,
        start_time=start_time,
        end_time=end_time,
        description=description,
        location=location,
        attendees=attendees,
    )

    result = f"✓ Meeting scheduled successfully!\n\n"
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


def main():
    """Entry point for Claude Desktop integration (stdio transport)."""
    import asyncio
    asyncio.run(mcp.run())


if __name__ == "__main__":
    # When run directly, use SSE transport for web-based access
    mcp.settings.port = 8090
    mcp.settings.host = "127.0.0.1"
    mcp.run(transport="sse")
