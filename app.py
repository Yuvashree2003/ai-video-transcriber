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

def download_audio(url: str) -> str:
    """
    Downloads audio from YouTube, Instagram, or Facebook URL using yt-dlp.
    Handles login-required or rate-limited errors gracefully.
    Returns path to downloaded WAV file.
    """
    try:
        file_name = url.split("/")[-1].split("?")[0] + "_" + get_random_string(6) + ".wav"
        audio_path = str(Path(TEMP_DIR) / file_name)

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": audio_path,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
            "quiet": True,
            "no_warnings": True,
        }

        # Use cookies only if file exists
        if Path(COOKIE_FILE).exists():
            ydl_opts["cookiefile"] = COOKIE_FILE
            logger.info("✅ Using cookies.txt for authenticated download.")
        else:
            logger.info("⚠️ cookies.txt not found — only public media can be downloaded.")

        logger.info(f"🎧 Starting download for: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        logger.info(f"✅ Downloaded audio to: {audio_path}")
        return audio_path

    except yt_dlp.utils.DownloadError as e:
        error_message = str(e).lower()

        if "login required" in error_message or "sign in" in error_message:
            raise Exception("⚠️ This Instagram/Facebook post requires login. Please ensure it's public or upload cookies.txt.")
        elif "rate-limit" in error_message:
            raise Exception("🚫 Rate limit reached. Please try again after a few minutes.")
        elif "private" in error_message or "not available" in error_message:
            raise Exception("🔒 This media is private or unavailable. Try a public link instead.")
        else:
            raise Exception(f"❌ Unable to download this media: {str(e)}")

    except Exception as e:
        raise Exception(f"❌ Unexpected error while downloading: {str(e)}")

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
