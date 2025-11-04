# mcp_server.py
from openai import OpenAI
from io import BytesIO
import os

# Initialize OpenAI client
client = OpenAI(api_key="YOUR_OPENAI_API_KEY_HERE")

# ====== Fake Call Class for Testing ======
class FakeCall:
    def __init__(self, call_id, audio_file):
        self.id = call_id
        self.audio_file = audio_file

    def stream_audio(self):
        # Yield audio chunks (here just one chunk from the file)
        with open(self.audio_file, "rb") as f:
            yield f.read()

    def play_audio(self, audio_bytes):
        # Save TTS output locally
        with open(f"{self.id}_tts_output.wav", "wb") as f:
            f.write(audio_bytes.getbuffer())
        print(f"TTS audio saved as {self.id}_tts_output.wav")


# ====== Speech-to-Text ======
def speech_to_text(audio_chunk):
    # Save chunk temporarily
    temp_file = "temp_audio.m4a"
    with open(temp_file, "wb") as f:
        f.write(audio_chunk)

    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=open(temp_file, "rb")
    )
    os.remove(temp_file)
    return transcription.text


# ====== LLM Agent Logic ======
def agent_logic(text_input):
    if "email" in text_input.lower():
        return "You have 3 unread emails."
    elif "schedule" in text_input.lower():
        return "I can schedule a meeting for you. When do you want it?"
    else:
        return "Sorry, I didn't understand that."


# ====== Text-to-Speech ======
def text_to_speech(text):
    audio_resp = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text
    )
    return BytesIO(audio_resp.audio)


# ====== Call Handler ======
def handle_incoming_call(call):
    print("Incoming call:", call.id)

    text_input = ""
    for chunk in call.stream_audio():
        text_input += speech_to_text(chunk)

    print("User said:", text_input)

    ai_response = agent_logic(text_input)
    print("AI response:", ai_response)

    audio_response = text_to_speech(ai_response)
    call.play_audio(audio_response)


# ====== Main ======
if __name__ == "__main__":
    # Replace with your test M4A file
    fake_call = FakeCall("test-call-1", "test2.m4a")
    handle_incoming_call(fake_call)
