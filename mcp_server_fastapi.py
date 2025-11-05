#!/usr/bin/env python3
"""
FastAPI MCP Server — queries Email entities in ApertureData and summarizes them using OpenAI >=1.0.0
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from aperturedb.CommonLibrary import create_connector
import openai

# Load environment variables
load_dotenv()
APERTUREDB_KEY = os.getenv("APERTUREDB_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate
if not APERTUREDB_KEY:
    raise RuntimeError("⚠️ Missing APERTUREDB_KEY in .env or environment.")
if not OPENAI_API_KEY:
    raise RuntimeError("⚠️ Missing OPENAI_API_KEY in .env or environment.")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize FastAPI app
app = FastAPI(title="ApertureData Email MCP with AI Summary")

# Helper function to connect to ApertureData
def _connect_db():
    return create_connector(key=APERTUREDB_KEY)


# -------------------------
# Request / Response Models
# -------------------------

class CheckEmailsRequest(BaseModel):
    limit: Optional[int] = 10

class CheckEmailsResponse(BaseModel):
    status: str
    total_emails: int
    spam_emails: int
    unread_emails: int
    samples: List[str]

class SummarizeEmailsResponse(BaseModel):
    status: str
    summary: str


# -------------------------
# Routes / Tools
# -------------------------

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@app.post("/check_emails", response_model=CheckEmailsResponse)
async def check_emails(request: CheckEmailsRequest):
    """Query Email entities in the ApertureData database."""
    db = _connect_db()
    limit = request.limit

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

    try:
        response = db.query(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

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

    return CheckEmailsResponse(
        status="ok",
        total_emails=total,
        spam_emails=spam,
        unread_emails=unread,
        samples=[e.get("subject", "N/A") for e in emails]
    )


@app.post("/summarize_emails", response_model=SummarizeEmailsResponse)
async def summarize_emails(request: CheckEmailsRequest):
    """Generate a natural language summary of emails using OpenAI >=1.0.0"""
    db = _connect_db()
    limit = request.limit

    # Fetch emails
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

    try:
        response = db.query(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

    emails = []
    if isinstance(response, tuple) and len(response) > 0:
        cmd = response[0][0].get("FindEntity", {})
        entities = cmd.get("entities", cmd.get("returned", []))
        for e in entities:
            props = {k: v for k, v in e.items() if not k.startswith("_")}
            emails.append(props)

    if not emails:
        return SummarizeEmailsResponse(status="ok", summary="No emails found to summarize.")

    # Prepare text for the AI
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
        raise HTTPException(status_code=500, detail=f"OpenAI summarization failed: {e}")

    return SummarizeEmailsResponse(status="ok", summary=summary_text)


# -------------------------
# Run server
# -------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mcp_fastapi:app", host="127.0.0.1", port=8000, reload=True)
