from flask import Flask, render_template, request, jsonify, Response
from yt_dlp import YoutubeDL
from pydub import AudioSegment
from faster_whisper import WhisperModel
import os
import tempfile
import shutil
import atexit
import time
import random
import string
import logging
import glob
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Flask app setup
app = Flask(__name__, static_folder="static")
app.logger.setLevel(logging.INFO)

# Logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("transcriber")

# Temporary directory
TEMP_DIR = os.path.join(tempfile.gettempdir(), "transcriber_temp")
os.makedirs(TEMP_DIR, exist_ok=True)

def get_random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def cleanup_temp_files():
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
atexit.register(cleanup_temp_files)

# Load Whisper model
model = WhisperModel("tiny", device="cpu", compute_type="int8")

def safe_remove_file(filepath):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        logger.warning(f"Could not remove {filepath}: {e}")

import os, uuid, tempfile, yt_dlp, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_audio(url: str, cookies_file: str = None) -> str:
    """
    Downloads audio from YouTube, Instagram, or Facebook and returns the path to the WAV file.
    Handles YouTube Shorts and normal videos, including 403 errors using cookies and User-Agent.

    :param url: Media URL
    :param cookies_file: Optional path to a cookies.txt file for restricted videos
    :return: Path to downloaded WAV file
    """
    temp_dir = tempfile.gettempdir()
    audio_filename = os.path.join(temp_dir, f"temp_audio_{os.urandom(8).hex()}.wav")

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': os.path.join(temp_dir, 'temp_audio_%(id)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'youtube_skip_dash_manifest': True,  # Important for Shorts
    }

    if cookies_file:
        ydl_opts['cookiefile'] = cookies_file

    try:
        logger.info(f"Starting download for URL: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise Exception("Failed to extract media info.")

        # Find the WAV file created by postprocessor
        temp_files = [f for f in os.listdir(temp_dir) if f.startswith('temp_audio_') and f.endswith('.wav')]
        if not temp_files:
            raise Exception("Audio file not created after download.")
        
        downloaded_audio = os.path.join(temp_dir, temp_files[0])
        logger.info(f"Downloaded audio saved to: {downloaded_audio}")
        return downloaded_audio

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error downloading audio: {e}")
        raise Exception(f"❌ Error: Unable to download this media. Ensure it’s a *public* YouTube, Instagram, or Facebook post. ({str(e)})")
    except Exception as e:
        logger.error(f"Transcription download error: {e}")
        raise Exception(f"❌ Error: {str(e)}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/transcribe", methods=["POST"])
def transcribe():
    start_time = time.time()
    req_id = get_random_string(6)
    log = lambda msg: logger.info(f"[{req_id}] {msg}")

    try:
        data = request.get_json(force=True)
        url = data.get("url", "").strip()

        if not url or not any(site in url for site in ["youtube.com", "youtu.be", "facebook.com", "instagram.com"]):
            return jsonify({"error": "Only public YouTube, Facebook, or Instagram links are supported."}), 400

        log(f"Processing URL: {url}")

        # Download
        audio_path = download_audio(url)
        log(f"Downloaded: {audio_path}")

        # Transcribe
        segments, info = model.transcribe(audio_path, beam_size=5, language="en", vad_filter=True)
        transcript = " ".join([seg.text for seg in segments])

        log("Transcription complete.")
        return jsonify({
            "status": "success",
            "transcript": transcript.strip(),
            "processing_time": round(time.time() - start_time, 2)
        })

    except Exception as e:
        logger.exception("Transcription error")
        return jsonify({"error": str(e)}), 500
    finally:
        # Clean up
        for f in glob.glob(os.path.join(TEMP_DIR, "*")):
            safe_remove_file(f)

# Simple login
USERNAME, PASSWORD = "Jayashree", "Krishna@2025"

def check_auth(u, p): return u == USERNAME and p == PASSWORD
def authenticate(): return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Login Required"'})

@app.before_request
def require_login():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
