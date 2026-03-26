from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

def transcribe_audio(audio_file_path):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    with open(audio_file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(audio_file_path, file.read()),
            model="whisper-large-v3",
            response_format="text", #  "json" 
            language="fr" 
        )
    return transcription
