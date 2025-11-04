# tools/email_summarizer.py

from mcp import Tool, ToolResponse
from openai import OpenAI
import json
import re

# Initialize OpenAI client
client = OpenAI()

def summarize_emails(context, input):
    """
    Summarize unread emails stored in the DB.
    Expected input:
    {
        "emails": [
            {"id": "1", "from": "dan@company.com", "subject": "Interview", "body": "..."},
            {"id": "2", "from": "linkedin@update.com", "subject": "Jobs for you", "body": "..."},
        ]
    }
    """

    emails = input.get("emails", [])
    summaries = []

    for email in emails:
        # Skip trivial spam patterns if not already filtered
        if re.search(r"(unsubscribe|promotion|sale|offer)", email["body"], re.I):
            continue

        prompt = f"""
        Summarize the following email in 2 sentences. Highlight any actions or important dates.
        Return a short JSON with keys: sender, subject, summary, priority (high/medium/low).
        Email content:
        From: {email['from']}
        Subject: {email['subject']}
        Body: {email['body'][:2000]}  # limit context
        """

        completion = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0.4,
        )

        try:
            text = completion.output_text.strip()
            data = json.loads(text) if text.startswith("{") else {"raw_summary": text}
        except Exception:
            data = {"raw_summary": text}

        summaries.append({"id": email["id"], **data})

    return ToolResponse(output={"summaries": summaries})


email_summarizer = Tool(
    name="email_summarizer",
    description="Summarizes unread emails and removes spam.",
    input_schema={
        "type": "object",
        "properties": {
            "emails": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "from": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["id", "from", "subject", "body"],
                },
            }
        },
        "required": ["emails"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "summaries": {"type": "array", "items": {"type": "object"}},
        },
    },
    function=summarize_emails,
)
import telnyx
import openai
import soundfile as sf
from io import BytesIO

telnyx.api_key = "KEY019A5115738921DB0918F3FFE25E9500_0Qdn0YzsdNQXDLrUVyajDQ"
openai.api_key = "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"

# ====== Telnyx MCP Call Handler ======
def handle_incoming_call(call):
    print("Incoming call:", call.id)

    # 1️⃣ Stream user audio to STT
    user_audio_chunks = call.stream_audio()
    text_input = ""
    for chunk in user_audio_chunks:
        # Convert audio to text (Whisper / OpenAI STT)
        text_input += speech_to_text(chunk)

    print("User said:", text_input)

    # 2️⃣ Run LLM agent
    ai_response = agent_logic(text_input)

    # 3️⃣ Convert AI response to speech (TTS)
    audio_response = text_to_speech(ai_response)

    # 4️⃣ Play audio back to user via MCP
    call.play_audio(audio_response)

# ====== Speech-to-Text ======
def speech_to_text(audio_chunk):
    # Example using OpenAI Whisper
    # Save chunk temporarily
    with open("chunk.wav", "wb") as f:
        f.write(audio_chunk)
    result = openai.Audio.transcriptions.create(
        model="whisper-1",
        file=open("chunk.wav", "rb")
    )
    return result.text

# ====== LLM Agent Logic ======
def agent_logic(text_input):
    # Simple intent-based demo
    if "email" in text_input.lower():
        return "You have 3 unread emails."
    elif "schedule" in text_input.lower():
        return "I can schedule a meeting for you. When do you want it?"
    else:
        return "Sorry, I didn't understand that."

# ====== Text-to-Speech ======
def text_to_speech(text):
    audio_resp = openai.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text
    )
    return BytesIO(audio_resp.audio)

# ====== Main server loop ======
if __name__ == "__main__":
    # Wait for calls from Telnyx
    for call in telnyx.calls.list(status="ringing"):
        handle_incoming_call(call)
