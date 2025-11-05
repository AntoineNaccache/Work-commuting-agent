#!/usr/bin/env python3
"""
MCP Server built with FastMCP — queries Email entities in ApertureData and summarizes them with OpenAI.
"""

import os
from dotenv import load_dotenv
from aperturedb.CommonLibrary import create_connector
from mcp.server.fastmcp import FastMCP
import openai

# -------------------------
# Load env variables
# -------------------------
load_dotenv()
APERTUREDB_KEY = os.getenv("APERTUREDB_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate
if not APERTUREDB_KEY:
    raise RuntimeError("⚠️ Missing APERTUREDB_KEY in .env or environment.")
if not OPENAI_API_KEY:
    raise RuntimeError("⚠️ Missing OPENAI_API_KEY in .env or environment.")

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# -------------------------
# Initialize MCP server
# -------------------------
mcp = FastMCP(name="ApertureData Email MCP")

# -------------------------
# Helper function
# -------------------------
def _connect_db():
    return create_connector(key=APERTUREDB_KEY)

# -------------------------
# MCP Tools
# -------------------------

@mcp.tool()
def health():
    """Health check tool"""
    return {"status": "ok"}


@mcp.tool()
def check_emails(limit: int = 10) -> dict:
    """Query Email entities in ApertureData"""
    db = _connect_db()
    query = [
        {
            "FindEntity": {
                "with_class": "Email",
                "results": {
                    "list": ["subject", "sender", "is_spam", "is_unread", "timestamp"]
                },
                "limit": limit
            }
        }
    ]
    response = db.query(query)

    emails = []
    if isinstance(response, tuple) and len(response) > 0:
        cmd = response[0][0].get("FindEntity", {})
        entities = cmd.get("entities", cmd.get("returned", []))
        for e in entities:
            props = {k: v for k, v in e.items() if not k.startswith("_")}
            emails.append(props)

    total = len(emails)
    spam = sum(1 for e in emails if e.get("is_spam"))
    unread = sum(1 for e in emails if e.get("is_unread"))

    return {
        "status": "ok",
        "total_emails": total,
        "spam_emails": spam,
        "unread_emails": unread,
        "samples": [e.get("subject", "N/A") for e in emails]
    }


@mcp.tool()
def summarize_emails(limit: int = 10) -> dict:
    """Generate a natural language summary of emails using OpenAI"""
    db = _connect_db()
    query = [
        {
            "FindEntity": {
                "with_class": "Email",
                "results": {
                    "list": ["subject", "sender", "is_spam", "is_unread"]
                },
                "limit": limit
            }
        }
    ]

    response = db.query(query)
    emails = []
    if isinstance(response, tuple) and len(response) > 0:
        cmd = response[0][0].get("FindEntity", {})
        entities = cmd.get("entities", cmd.get("returned", []))
        for e in entities:
            props = {k: v for k, v in e.items() if not k.startswith("_")}
            emails.append(props)

    if not emails:
        return {"status": "ok", "summary": "No emails found to summarize."}

    # Prepare prompt
    email_texts = "\n".join([
        f"From: {e.get('sender', 'N/A')}, Subject: {e.get('subject', 'N/A')}, Spam: {e.get('is_spam', False)}, Unread: {e.get('is_unread', False)}"
        for e in emails
    ])
    prompt = f"Generate a concise summary of the following emails:\n\n{email_texts}\n\nInclude total emails, spam/unread info, and key subjects and senders."

    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        summary_text = completion.choices[0].message.content.strip()
    except Exception as e:
        summary_text = f"Failed to generate summary: {e}"

    return {"status": "ok", "summary": summary_text}


# -------------------------
# Run MCP server
# -------------------------
if __name__ == "__main__":
    # Run server over StreamableHttp transport
    mcp.run(transport="sse")