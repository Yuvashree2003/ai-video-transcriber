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
from pathlib import Path
from secrets import token_hex
import tempfile

def get_random_string(n=6):
    return token_hex(n // 2)

import tempfile

TEMP_DIR = Path(tempfile.gettempdir()) / "transcriber_temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Make sure your cookie file is uploaded to your project or accessible in the same directory
COOKIE_FILE = "cookies.txt"  # Replace with your cookie file path

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

def download_audio(url: str) -> str:
    """
    Downloads audio from YouTube, Instagram, or Facebook URL using yt-dlp.
    Supports cookies for login-required content.
    Returns path to downloaded WAV file.
    """
    try:
        base_name = url.split("/")[-1].split("?")[0] + "_" + get_random_string(6)
        output_template = str(TEMP_DIR / f"{base_name}.%(ext)s")
        wav_path = str(TEMP_DIR / f"{base_name}.wav")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                    "preferredquality": "192",
                }
            ],
        }

        # Pick cookies automatically
        if "instagram.com" in url:
            cookie_path = Path("instagram_cookies.json")
        elif "youtube.com" in url or "youtu.be" in url:
            cookie_path = Path("youtube_cookies.json")
        else:
            cookie_path = None

        if cookie_path and cookie_path.exists():
            ydl_opts["cookiefile"] = str(cookie_path)
            print(f"✅ Using cookies: {cookie_path.name}")
        else:
            print("⚠️ No cookie file found — downloading only public media.")

        # Run download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Verify output
        if not Path(wav_path).exists():
            raise FileNotFoundError(f"WAV file not found: {wav_path}")

        print(f"✅ Downloaded: {wav_path}")
        return wav_path

    except yt_dlp.utils.DownloadError as e:
        raise Exception(f"Download failed: {str(e)}")

    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")

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
        for f in TEMP_DIR.glob("*"):
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
