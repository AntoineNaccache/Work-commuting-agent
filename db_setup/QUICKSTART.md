# Quick Start - ApertureData Setup

Get started with sample emails in ApertureData in 3 steps:

## Step 1: Install Dependencies

```bash
# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

## Step 2: Configure ApertureData

For cloud instances (recommended):
```bash
# Create .env file with your connection key
cat > .env << 'EOF'
APERTUREDB_KEY=your_connection_key_here
APERTUREDB_USE_SSL=true
EOF
```

For local instances:
```bash
cp .env.example .env
# Edit .env with your ApertureData host, port, and credentials
```

## Step 3: Run Setup Script

```bash
python setup_aperturedb.py
```

This will:
- ✅ Generate 10 sample emails (7 regular + 3 spam)
- ✅ Include images and PDF attachments
- ✅ Store them in ApertureData (if connected)
- ✅ Save backup to `sample_emails.json`

**Note:** If ApertureData is not available, the script will still generate emails and save them to JSON for later import.

## Verify Setup

Check that `sample_emails.json` was created:

```bash
ls -lh sample_emails.json
```

View a sample email:

```bash
python3 -c "import json; data=json.load(open('sample_emails.json')); print(json.dumps(data[0], indent=2))"
```

## Next Steps

- Query emails using ApertureData's multimodal search API
- Filter by spam status: `is_spam: true/false`
- Filter unread emails: `is_unread: true`
- Process attachments from the `attachments` field

For detailed information, see [README_SETUP.md](README_SETUP.md).
