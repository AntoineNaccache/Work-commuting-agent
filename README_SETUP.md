# ApertureData Setup Guide

This guide will help you set up ApertureData with sample emails containing images and attachments.

## Prerequisites

1. Python 3.8 or higher
2. ApertureData instance (local or cloud)
3. ApertureData connection key (for cloud instances) or credentials (for local instances)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure ApertureData connection:

For cloud instances (recommended):
```bash
# Create .env file with your ApertureData key
cat > .env << 'EOF'
APERTUREDB_KEY=your_key_here
APERTUREDB_USE_SSL=true
EOF
```

For local instances:
```bash
cp .env.example .env
# Edit .env with your ApertureData host/port and credentials
```

## Usage

Run the setup script:
```bash
python setup_aperturedb.py
```

This script will:
- Generate 10 sample emails (7 regular + 3 spam)
- Include images and attachments in some emails
- Store them in ApertureData
- Save a backup JSON file (`sample_emails.json`)

## Sample Email Features

The generated emails include:
- **Regular emails** with:
  - Random subjects and content
  - Optional embedded images
  - Optional PDF and image attachments
  - Read/unread status
  - Timestamps (within last 30 days)

- **Spam emails** with:
  - Suspicious subject lines
  - Typical spam content patterns
  - Marked as spam in metadata

## Email Structure

Each email contains:
- `sender`: Email address of sender
- `recipient`: Email address of recipient
- `subject`: Email subject line
- `body`: Email body text
- `timestamp`: When email was sent
- `is_spam`: Boolean flag for spam detection
- `is_unread`: Boolean flag for read/unread status
- `image_data` (optional): Base64 encoded image
- `attachments` (optional): Array of attachment objects with:
  - `filename`: Attachment filename
  - `content_type`: MIME type
  - `data`: Base64 encoded content
  - `size`: File size in bytes

## Troubleshooting

If ApertureData connection fails, the script will:
1. Save emails to `sample_emails.json` as a fallback
2. Print error messages to help debug connection issues

## Next Steps

After setup, you can:
- Query emails using ApertureData's multimodal search
- Filter by spam status, unread status, etc.
- Extract and process attachments
- Use images for visual search capabilities

## Notes

- Adjust the ApertureData SDK initialization in `setup_aperturedb.py` based on your specific ApertureData version
- The actual API methods may vary - check ApertureData documentation for your SDK version
- Image and attachment data is stored as base64 encoded strings for easy serialization
