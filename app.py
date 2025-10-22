from flask import Flask, render_template, request, jsonify
from yt_dlp import YoutubeDL
from pydub import AudioSegment
from faster_whisper import WhisperModel
from flask import request, Response
import os
import tempfile
import shutil
import atexit
import time
import random
import string
import yt_dlp
import logging
import glob
from pathlib import Path

app = Flask(__name__, static_folder="static")
app.logger.setLevel(logging.INFO)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create a temporary directory for downloads
TEMP_DIR = os.path.join(tempfile.gettempdir(), 'transcriber_temp')
os.makedirs(TEMP_DIR, exist_ok=True)

def get_random_string(length=8):
    """Generate a random string for unique filenames"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def cleanup_temp_files():
    """Clean up temporary files"""
    if os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            logger.info("Cleaned up temporary directory")
        except Exception as e:
            logger.warning(f"Error cleaning up temp directory: {e}")

# Register cleanup function to run on exit
atexit.register(cleanup_temp_files)

# Load faster-whisper model (tiny for speed)
model = WhisperModel("tiny", device="cpu", compute_type="int8")

def safe_remove_file(filepath, max_retries=3, delay=0.1):
    """Safely remove a file with retry mechanism"""
    for attempt in range(max_retries):
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                return True
        except (OSError, PermissionError) as e:
            if attempt == max_retries - 1:
                logger.warning(f"Failed to remove {filepath} after {max_retries} attempts: {e}")
                return False
            time.sleep(delay)
    return False

def download_audio(url, cookies_path=None):
    import yt_dlp
    import uuid

    temp_file = f"temp_audio_{uuid.uuid4()}.mp3"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_file,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    if cookies_path:
        ydl_opts['cookiefile'] = cookies_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise Exception("yt-dlp failed to extract video info")
            return temp_file
    except yt_dlp.utils.DownloadError as e:
        raise Exception(f"DownloadError: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error: {e}")

def convert_to_wav(input_file):
    """Convert any audio file to WAV 16kHz mono"""
    if not input_file or not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    # Generate a unique output filename
    unique_id = get_random_string()
    output_file = os.path.join(TEMP_DIR, f'converted_{unique_id}.wav')
    
    try:
        logger.info(f"Converting {input_file} to WAV format")
        
        # Read the input file
        audio = AudioSegment.from_file(input_file)
        
        # Set to mono and 16kHz
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(16000)
        
        # Export to WAV format
        audio.export(
            output_file,
            format="wav",
            parameters=["-ar", "16000", "-ac", "1"]
        )
        
        logger.info(f"Successfully converted to {output_file} (Size: {os.path.getsize(output_file) / (1024*1024):.2f} MB)")
        return output_file
        
    except Exception as e:
        # Clean up the output file if it was partially created
        safe_remove_file(output_file)
        logger.error(f"Error converting {input_file} to WAV: {str(e)}", exc_info=True)
        raise Exception(f"Failed to convert audio to WAV: {str(e)}")

@app.route('/')
def index():
    return render_template("index.html")

@app.route("/transcribe", methods=["POST"])
def transcribe():
    start_time = time.time()
    request_id = get_random_string(6)
    
    def log(message, level='info'):
        """Helper function for consistent logging"""
        getattr(logger, level)(f"[{request_id}] {message}")
    
    log(f"Starting transcription request")
    
    # Validate request
    if not request.is_json:
        log("Request must be JSON", 'error')
        return jsonify({"error": "Request must be JSON"}), 400
        
    data = request.get_json()
    url = data.get("url")

    if not url or not any(site in url for site in ["instagram.com", "facebook.com", "youtube.com", "youtu.be"]):
        log(f"Invalid or unsupported URL: {url}", 'error')
        return jsonify({"error": "Invalid or unsupported URL"}), 400

    audio_file = None
    wav_file = None
    
    try:
        # Step 1: Download audio
        log(f"Downloading audio from {url}")
        audio_file = download_audio(url)
        
        if not audio_file or not os.path.exists(audio_file):
            log(f"Failed to download audio: {audio_file}", 'error')
            return jsonify({"error": "Failed to download audio"}), 500
            
        log(f"Downloaded to {audio_file} ({os.path.getsize(audio_file) / (1024*1024):.2f} MB)")

        # Step 2: Convert to WAV if needed
        if not audio_file.lower().endswith('.wav'):
            log(f"Converting {audio_file} to WAV format")
            wav_file = convert_to_wav(audio_file)
            safe_remove_file(audio_file)  # Clean up the original file
            audio_file = wav_file
            
        log(f"Transcribing {audio_file} (Size: {os.path.getsize(audio_file) / (1024*1024):.2f} MB)")
        
        # Step 3: Transcribe using faster-whisper
        segments, info = model.transcribe(
            audio_file,
            beam_size=5,
            language='en',
            vad_filter=True
        )
        
        # Convert segments to text
        transcript = " ".join([segment.text for segment in segments])
        log(f"Transcription completed successfully")
        
        return jsonify({
            "transcript": transcript.strip(),
            "status": "success",
            "duration_seconds": round(time.time() - start_time, 2),
            "request_id": request_id
        })

    except Exception as e:
        log(f"Error in transcription: {str(e)}", 'error')
        logger.exception("Transcription error")
        
        return jsonify({
            "error": "An error occurred during transcription",
            "details": str(e),
            "request_id": request_id
        }), 500
        
    finally:
        # Clean up all temporary files
        if audio_file and os.path.exists(audio_file):
            safe_remove_file(audio_file)
        if wav_file and os.path.exists(wav_file) and wav_file != audio_file:
            safe_remove_file(wav_file)
            
        log(f"Request completed in {time.time() - start_time:.2f} seconds")
    
# Change these to your own secure username/password
USERNAME = os.getenv("APP_USERNAME")
PASSWORD = os.getenv("APP_PASSWORD")


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
    # Allow home page, API route, and static files
    if request.path in ['/', '/transcribe'] or request.path.startswith('/static/'):
        return
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()


if __name__ == "__main__":
    app.run(debug=True)
