from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException
import whisper
import os
import tempfile
import subprocess
import re
import uuid
import logging
from datetime import datetime
from googletrans import Translator
from typing import Optional

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Subtitle Generator Pro",
    version="2.0.0",
    description="Professional AI Subtitle Generator with Translation",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("logs", exist_ok=True)

logger.info("=" * 60)
logger.info("🎬 AI Subtitle Generator Pro v2.0.0")
logger.info("=" * 60)

# Load Whisper Model
logger.info("📥 Loading Whisper model...")
try:
    model = whisper.load_model("tiny")
    logger.info("✅ Whisper model loaded successfully!")
except Exception as e:
    logger.error(f"❌ Failed to load Whisper model: {e}")
    raise

# Load Google Translate
logger.info("📥 Loading Google Translate...")
try:
    translator = Translator()
    translation_available = True
    logger.info("✅ Google Translate ready!")
except Exception as e:
    logger.warning(f"⚠️ Google Translate not available: {e}")
    translation_available = False

# Helper Functions
def extract_audio(video_path: str) -> Optional[str]:
    """Extract audio from video file."""
    try:
        audio_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.wav")
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            "-y", audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return None
        return audio_path if os.path.exists(audio_path) else None
    except subprocess.TimeoutExpired:
        logger.error("Audio extraction timeout")
        return None
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        return None

def detect_language(text: str) -> str:
    """Detect language from text."""
    patterns = {
        'english': r'[a-zA-Z]',
        'chinese': r'[\u4e00-\u9fff]',
        'japanese': r'[\u3040-\u309f\u30a0-\u30ff]',
        'korean': r'[\uac00-\ud7af]',
        'thai': r'[\u0e00-\u0e7f]',
        'vietnamese': r'[ăâđêôơư]',
    }
    scores = {}
    for lang, pattern in patterns.items():
        matches = len(re.findall(pattern, text))
        if matches > 0:
            scores[lang] = matches
    if scores:
        return max(scores, key=scores.get)
    return 'english'

def translate_to_myanmar(text: str) -> str:
    """Translate text to Myanmar."""
    try:
        if not translation_available:
            return text
        result = translator.translate(text, dest='my')
        return result.text
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text

def cleanup_myanmar_grammar(text: str) -> str:
    """Cleanup Myanmar grammar."""
    text = re.sub(r'\s+', ' ', text)
    replacements = {
        r'သည်\s+': 'က ',
        r'သည်။': 'တယ်။',
        r'သည်\s': 'တယ် ',
        r'က\s+က': 'က ',
        r'သည်\s+သည်': 'သည်',
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    text = re.sub(r'(\w+)\s+\1', r'\1', text)
    return text.strip()

def format_time(seconds: float) -> str:
    """Format time for SRT."""
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# API Endpoints
@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "🎬 AI Subtitle Generator Pro v2.0.0",
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "/api/status": "Check service status",
            "/api/transcribe": "Upload video & generate subtitles",
            "/docs": "Swagger API Documentation",
            "/redoc": "ReDoc Documentation"
        }
    }

@app.get("/api/status")
def status():
    """Service status endpoint."""
    return {
        "status": "online",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "translation_available": translation_available,
        "models": {
            "whisper": "tiny",
            "translation": "Google Translate" if translation_available else "Disabled"
        },
        "system": {
            "uploads": len(os.listdir("uploads")),
            "outputs": len(os.listdir("outputs"))
        }
    }

@app.post("/api/transcribe")
async def transcribe(
    video: UploadFile = File(..., description="Video file to transcribe"),
    translate: str = Form("true", description="Enable translation"),
    target_language: str = Form("myanmar", description="Target language"),
    source_language: str = Form("auto", description="Source language")
):
    """
    Transcribe video and generate subtitles.
    
    - **video**: Video file (MP4, AVI, MOV, etc.)
    - **translate**: Enable translation (true/false)
    - **target_language**: Target language (myanmar, english, etc.)
    - **source_language**: Source language (auto, english, chinese, etc.)
    """
    video_id = str(uuid.uuid4())
    video_path = None
    audio_path = None
    
    try:
        # Validate file
        if not video.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check file extension
        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
        ext = os.path.splitext(video.filename)[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}"
            )
        
        logger.info(f"📤 Step 1: Saving video... {video.filename}")
        video_path = os.path.join("uploads", f"{video_id}_{video.filename}")
        with open(video_path, "wb") as f:
            while chunk := await video.read(1024 * 1024):
                f.write(chunk)
        
        file_size = os.path.getsize(video_path) / (1024 * 1024)
        logger.info(f"📤 File size: {file_size:.2f} MB")
        
        logger.info("🎵 Step 2: Extracting audio...")
        audio_path = extract_audio(video_path)
        if not audio_path:
            raise HTTPException(status_code=500, detail="Failed to extract audio from video")
        
        logger.info("🎤 Step 3: Transcribing with Whisper...")
        if source_language == "auto":
            result = model.transcribe(audio_path, verbose=False)
        else:
            lang_map = {
                "english": "en", "chinese": "zh", "japanese": "ja",
                "korean": "ko", "thai": "th", "vietnamese": "vi"
            }
            lang_code = lang_map.get(source_language, None)
            result = model.transcribe(audio_path, language=lang_code, verbose=False)
        
        logger.info("📝 Step 4: Generating subtitles...")
        srt = ""
        translated_count = 0
        detected_lang = "english"
        
        if result["segments"]:
            first_text = result["segments"][0]["text"]
            detected_lang = detect_language(first_text)
            logger.info(f"🔍 Detected language: {detected_lang}")
            
            for i, seg in enumerate(result["segments"], 1):
                original_text = re.sub(r"\s+", " ", seg["text"].strip())
                if len(original_text) < 2:
                    continue
                
                if translate == "true" and translation_available and target_language == "myanmar":
                    try:
                        translated = translate_to_myanmar(original_text)
                        translated = cleanup_myanmar_grammar(translated)
                        final_text = translated
                        translated_count += 1
                    except Exception as e:
                        logger.error(f"Translation error: {e}")
                        final_text = original_text
                else:
                    final_text = original_text
                
                srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{final_text}\n\n"
        
        logger.info("💾 Step 5: Saving files...")
        srt_filename = f"{video_id}.srt"
        srt_path = os.path.join("outputs", srt_filename)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt)
        
        # Cleanup
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        
        logger.info(f"✅ Complete! Translated {translated_count} segments")
        
        response = FileResponse(
            srt_path,
            media_type="text/plain",
            filename=f"subtitles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt"
        )
        response.headers["X-Translated"] = str(translated_count > 0)
        response.headers["X-Detected-Language"] = detected_lang
        response.headers["X-Segments"] = str(len(result["segments"]))
        response.headers["X-Translated-Count"] = str(translated_count)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        # Cleanup on error
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }
    

if __name__ == "__main__":
    import uvicorn
    # Hugging Face Spaces အတွက် port 7860 ကို သတ်မှတ်ခြင်း
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
    
