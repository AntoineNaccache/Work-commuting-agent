# MCP Gmail & Calendar Server

A Model Context Protocol (MCP) server that provides Gmail and Google Calendar access for LLMs, powered by the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).

## Features

- **Gmail Integration**
  - Expose Gmail messages as MCP resources
  - Tools for composing, sending, and managing emails
  - Advanced email search and filtering
  - Label management

- **Google Calendar Integration**
  - View upcoming calendar events
  - Schedule meetings with attendees
  - Find available time slots
  - Smart meeting suggestions from email content

- **OAuth 2.0 Authentication** with Google APIs

## Prerequisites

- Python 3.10+
- Gmail account with API access
- [uv](https://github.com/astral-sh/uv) for Python package management (recommended)

## Setup

### 1. Install dependencies

Install project dependencies (uv automatically creates and manages a virtual environment)
```bash
uv sync
```

### 2. Configure Gmail OAuth credentials

There's unfortunately a lot of steps required to use the Gmail API. I've attempted to capture all of the required steps (as of March 28, 2025) but things may change.

#### Google Cloud Setup

1. **Create a Google Cloud Project**
    - Go to [Google Cloud Console](https://console.cloud.google.com/)
    - Click on the project dropdown at the top of the page
    - Click "New Project"
    - Enter a project name (e.g., "MCP Gmail Integration")
    - Click "Create"
    - Wait for the project to be created and select it from the dropdown

2. **Enable Required APIs**
    - In your Google Cloud project, go to the navigation menu (≡)
    - Select "APIs & Services" > "Library"
    - Search for and enable:
      - **Gmail API** - Click the card and then "Enable"
      - **Google Calendar API** - Click the card and then "Enable"

3. **Configure OAuth Consent Screen**
    - Go to "APIs & Services" > "OAuth consent screen"
    - You will likely see something like "Google Auth Platform not configured yet"
        - Click on "Get started"
    - Fill in the required application information:
        - App name: "MCP Gmail Integration"
        - User support email: Your email address
    - Fill in the required audience information:
        - Choose "External" user type (unless you have a Google Workspace organization)
    - Fill in the required contact information:
        - Your email address
    - Click "Save and Continue"
   - Click "Create"

4. **Create OAuth Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as the application type
   - Enter a name (e.g., "MCP Gmail Desktop Client")
   - Click "Create"
   - Click "Download JSON" for the credentials you just created
   - Save the file as `credentials.json` in your project root directory

5. **Add scopes**
    - Go to "APIs & Services" > "OAuth consent screen"
    - Go to the "Data Access" tab
    - Click "Add or remove scopes"
    - Search for and add scopes for:
      - **Gmail API**: `.../auth/gmail.modify` - Read, compose, and send emails
      - **Google Calendar API**: `.../auth/calendar` - See, edit, share, and permanently delete calendars
      - **Google Calendar API**: `.../auth/calendar.events` - View and edit events
    - Click update
    - Click save

Verify that you've set up your OAuth configuration correctly by running a simple test script.

```bash
uv run python scripts/test_gmail_setup.py
```

You should be able to see usage metrics at https://console.cloud.google.com/apis/api/gmail.googleapis.com/metrics

### 3. Run the server

Development mode:
```bash
uv run mcp dev mcp_gmail/server.py
```

This will spin up an MCP Inspector application that you can use to interact with the MCP server.

Or install for use with Claude Desktop:
```bash
uv run mcp install \
    --with-editable .
    --name gmail \
    --env-var MCP_GMAIL_CREDENTIALS_PATH=$(pwd)/credentials.json \
    --env-var MCP_GMAIL_TOKEN_PATH=$(pwd)/token.json \
    mcp_gmail/server.py
```

> [!NOTE]
> If you encounter an error like `Error: spawn uv ENOENT` when spinning up Claude Desktop and initializing the MCP server, you may need to update your `claude_desktop_config.json` to provide the **absolute** path to `uv`. Go to Claude Desktop -> Settings -> Developer -> Edit Config.
>
> ```json
> {
>   "mcpServers": {
>     "gmail": {
>       "command": "~/.local/bin/uv",
>     }
>   }
> }
> ```

## Development

### Linting and Testing

Run linting and formatting:
```bash
# Format code
uv run ruff format .

# Lint code with auto-fixes where possible
uv run ruff check --fix .

# Run tests
uv run pytest tests/
```

### Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality. The hooks automatically run before each commit to verify code formatting and linting standards.

Install the pre-commit hooks:
```bash
pre-commit install
```

Run pre-commit manually on all files:
```bash
pre-commit run --all-files
```

## Usage

Once running, you can connect to the MCP server using any MCP client or via Claude Desktop.

### Available Resources

- `gmail://messages/{message_id}` - Access email messages
- `gmail://threads/{thread_id}` - Access email threads

### Available Tools

**Email Tools:**
- `compose_email` - Create a new email draft
- `send_email` - Send an email
- `search_emails` - Search for emails with specific filters (from, to, subject, dates, etc.)
- `query_emails` - Search for emails using raw Gmail query syntax
- `get_emails` - Retrieve multiple email messages by their IDs
- `list_available_labels` - Get all available Gmail labels
- `mark_message_read` - Mark a message as read
- `add_label_to_message` - Add a label to a message
- `remove_label_from_message` - Remove a label from a message

**Calendar Tools:**
- `get_calendar_events` - View upcoming calendar events
- `schedule_meeting` - Schedule a new meeting with attendees
- `find_meeting_times` - Find available time slots for multiple attendees
- `suggest_meeting_from_email` - Analyze an email and suggest meeting times based on availability
- `list_all_calendars` - List all accessible calendars

## Recent Improvements

This MCP server has been continuously improved through **AI-driven conversation log analysis**. Key enhancements include:

### Major Features Added
- **PDF Support**: Read boarding passes, tickets, invoices from PDF attachments
- **Flight Extraction**: Automatically parse flight details from emails and PDFs
- **Smart Search**: Specialized tools for finding flight bookings and PDF attachments
- **Duplicate Prevention**: Automatic detection of duplicate calendar events
- **Past Date Validation**: Warnings before scheduling events in the past
- **HTML Parsing**: Clean text extraction from HTML-only emails

### New Tools
- `search_flight_bookings()` - Find flight bookings, exclude price tracking emails
- `search_emails_with_pdf_attachments()` - Find emails with PDF attachments
- `list_attachments()` - Show all email attachments
- `extract_pdf_text()` - Read PDF boarding passes, tickets, invoices
- `extract_flight_info()` - Parse flight details from emails and PDFs

### Improvement Process
We use an innovative workflow where:
1. **Real usage** is logged during MCP client sessions
2. **AI analysis** (Claude Code) examines conversation logs
3. **Issues identified** from user feedback and error patterns
4. **Improvements implemented** automatically based on findings

📖 **Learn More:**
- [**Improvement Workflow**](MCP_IMPROVEMENT_WORKFLOW.md) - Detailed process documentation
- [**Improvements Summary**](IMPROVEMENTS_SUMMARY.md) - Complete list of enhancements

**Stats**: 3 log analyses → 8 issues fixed → 5 new tools → 3 enhanced tools → 500+ lines of improvements

## Environment Variables

You can configure the server using environment variables:

- `MCP_GMAIL_CREDENTIALS_PATH`: Path to the OAuth credentials JSON file (default: "credentials.json")
- `MCP_GMAIL_TOKEN_PATH`: Path to store the OAuth token (default: "token.json")
- `MCP_GMAIL_MAX_RESULTS`: Default maximum results for search queries (default: 10)

## License

MIT
