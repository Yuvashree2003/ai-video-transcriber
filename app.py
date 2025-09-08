from flask import Flask, render_template, request, jsonify
from yt_dlp import YoutubeDL
from pydub import AudioSegment
from faster_whisper import WhisperModel
from flask import request, Response
import os
import yt_dlp

app = Flask(__name__, static_folder="static")

# Load faster-whisper model (tiny for speed)
model = WhisperModel("tiny", device="cpu", compute_type="int8")

def download_audio(url):
    """Download best audio from a given URL using yt-dlp"""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "temp.%(ext)s",
        "quiet": True
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def convert_to_wav(input_file, output_file="temp.wav"):
    """Convert any audio file to WAV 16kHz mono"""
    AudioSegment.from_file(input_file).export(output_file, format="wav")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/transcribe", methods=["POST"])
def transcribe():
    data = request.get_json()
    url = data.get("url")

    if not url or not any(site in url for site in ["instagram.com", "facebook.com", "youtube.com", "youtu.be"]):
        return jsonify({"error": "Invalid or unsupported URL"}), 400

    # Cleanup old files
    for ext in ["m4a", "mp4", "webm", "wav"]:
        if os.path.exists(f"temp.{ext}"):
            os.remove(f"temp.{ext}")

    try:
        # Step 1: Download
        download_audio(url)

        # Step 2: Find downloaded file
        audio_file = None
        for ext in ["m4a", "mp4", "webm"]:
            if os.path.exists(f"temp.{ext}"):
                audio_file = f"temp.{ext}"
                break
        if not audio_file:
            return jsonify({"error": "Failed to download audio"}), 500

        # Step 3: Convert to WAV
        convert_to_wav(audio_file)

        # Step 4: Transcribe using faster-whisper
        segments, _ = model.transcribe("temp.wav", beam_size=5)
        transcript = " ".join([segment.text for segment in segments])

        return jsonify({"transcript": transcript.strip()})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Change these to your own secure username/password
USERNAME = "Jayashree"
PASSWORD = "Krishna@2025"

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response(
        'Login required', 
        401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

@app.before_request
def require_login():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()

if __name__ == "__main__":
    app.run(debug=True)
