from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import whisper
import os
import tempfile
import subprocess
import re
import uuid
from datetime import datetime
from transformers import MarianMTModel, MarianTokenizer
import json

app = FastAPI(title="AI Subtitle Generator", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

print("=" * 60)
print("🎬 AI Subtitle Generator v2.0.0")
print("=" * 60)

# ================= 1. LOAD MODELS =================
print("📥 Loading Whisper model...")
model = whisper.load_model("base")
print("✅ Whisper model loaded!")

print("📥 Loading translation model (English → Myanmar)...")
try:
    translation_tokenizer = MarianTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-my")
    translation_model = MarianMTModel.from_pretrained("Helsinki-NLP/opus-mt-en-my")
    print("✅ Translation model loaded!")
    translation_available = True
except Exception as e:
    print(f"⚠️ Translation model not available: {e}")
    translation_available = False

# ================= 2. EXTRACT AUDIO =================
def extract_audio(video_path):
    """Extract audio from video using ffmpeg"""
    audio_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.wav")
    cmd = [
        "ffmpeg", "-i", video_path, 
        "-vn", "-acodec", "pcm_s16le", 
        "-ar", "16000", "-ac", "1", 
        "-y", audio_path
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return audio_path if os.path.exists(audio_path) else None

# ================= 3. LANGUAGE DETECTION =================
def detect_language(text):
    """Detect language from text sample"""
    # Common language patterns
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
        scores[lang] = matches
    
    if scores:
        detected = max(scores, key=scores.get)
        if scores[detected] > 0:
            return detected
    return 'english'

# ================= 4. TRANSLATION FUNCTION =================
def translate_to_myanmar(text):
    """Translate English text to Myanmar"""
    if not translation_available:
        return text
    
    try:
        # Split long text into smaller chunks for better translation
        chunks = [text[i:i+256] for i in range(0, len(text), 256)]
        translated_chunks = []
        
        for chunk in chunks:
            inputs = translation_tokenizer(
                chunk, 
                return_tensors="pt", 
                truncation=True, 
                max_length=512,
                padding=True
            )
            outputs = translation_model.generate(
                **inputs, 
                max_length=512, 
                num_beams=5,  # Better quality
                early_stopping=True,
                temperature=0.7  # More natural
            )
            translated = translation_tokenizer.decode(outputs[0], skip_special_tokens=True)
            translated_chunks.append(translated)
        
        result = " ".join(translated_chunks)
        return result
    except Exception as e:
        print(f"Translation error: {e}")
        return text

# ================= 5. MYANMAR GRAMMAR CLEANUP =================
def cleanup_myanmar_grammar(text):
    """Clean up Myanmar text for better readability"""
    # Remove repeated spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Fix common Myanmar grammar issues
    replacements = {
        r'သည်\s+': 'က ',  # Fix particle
        r'သည်။': 'တယ်။',  # Better ending
        r'သည်\s': 'တယ် ',  # Better ending
        r'က\s+က': 'က ',  # Remove duplicate
        r'သည်\s+သည်': 'သည်',  # Remove duplicate
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    
    # Remove excessive particles
    text = re.sub(r'(\w+)\s+\1', r'\1', text)  # Remove repeated words
    
    return text.strip()

# ================= 6. FORMAT TIME =================
def format_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# ================= 7. MAIN TRANSCRIBE FUNCTION =================
@app.post("/api/transcribe")
async def transcribe(
    video: UploadFile = File(...),
    translate: str = Form("true"),
    target_language: str = Form("myanmar"),
    source_language: str = Form("auto")
):
    try:
        # ===== STEP 1: Save video =====
        print("📤 Step 1: Saving video...")
        video_id = str(uuid.uuid4())
        video_path = os.path.join("uploads", f"{video_id}_{video.filename}")
        
        with open(video_path, "wb") as f:
            while chunk := await video.read(1024 * 1024):
                f.write(chunk)
        
        # ===== STEP 2: Extract audio =====
        print("🎵 Step 2: Extracting audio...")
        audio_path = extract_audio(video_path)
        if not audio_path:
            return {"error": "Failed to extract audio from video"}
        
        # ===== STEP 3: Transcribe with Whisper =====
        print("🎤 Step 3: Transcribing with Whisper...")
        
        # Auto-detect language or use specified
        if source_language == "auto":
            result = model.transcribe(audio_path, verbose=False)
        else:
            # Map language to Whisper code
            lang_map = {
                "english": "en",
                "chinese": "zh",
                "japanese": "ja",
                "korean": "ko",
                "thai": "th",
                "vietnamese": "vi",
                "myanmar": "my"
            }
            lang_code = lang_map.get(source_language, None)
            result = model.transcribe(audio_path, language=lang_code, verbose=False)
        
        # ===== STEP 4: Generate SRT with Translation =====
        print("📝 Step 4: Generating subtitles...")
        srt = ""
        original_srt = ""
        translated_count = 0
        detected_lang = "english"
        
        # Detect language from first segment
        if result["segments"]:
            first_text = result["segments"][0]["text"]
            detected_lang = detect_language(first_text)
            print(f"🔍 Detected language: {detected_lang}")
        
        for i, seg in enumerate(result["segments"], 1):
            original_text = re.sub(r"\s+", " ", seg["text"].strip())
            if len(original_text) < 2:
                continue
            
            # Store original
            original_srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{original_text}\n\n"
            
            # Translate if requested
            if translate == "true" and translation_available and target_language == "myanmar":
                try:
                    translated = translate_to_myanmar(original_text)
                    # Cleanup Myanmar grammar
                    translated = cleanup_myanmar_grammar(translated)
                    final_text = translated
                    translated_count += 1
                except Exception as e:
                    print(f"Translation error: {e}")
                    final_text = original_text
            else:
                final_text = original_text
            
            srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{final_text}\n\n"
        
        # ===== STEP 5: Save files =====
        print("💾 Step 5: Saving files...")
        
        # Save translated SRT
        srt_filename = f"{video_id}.srt"
        srt_path = os.path.join("outputs", srt_filename)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt)
        
        # Save original SRT (for comparison)
        original_filename = f"{video_id}_original.srt"
        original_path = os.path.join("outputs", original_filename)
        with open(original_path, "w", encoding="utf-8") as f:
            f.write(original_srt)
        
        # ===== STEP 6: Clean up =====
        os.remove(video_path)
        os.remove(audio_path)
        
        print(f"✅ Complete! Translated {translated_count} segments to Myanmar")
        
        # Return with metadata
        return FileResponse(
            srt_path,
            media_type="text/plain",
            filename=f"subtitles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt",
            headers={
                "Access-Control-Allow-Origin": "*",
                "X-Translated": str(translated_count > 0),
                "X-Detected-Language": detected_lang,
                "X-Segments": str(len(result["segments"]))
            }
        )
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"error": str(e)}

# ================= 8. API ENDPOINT FOR STATUS =================
@app.get("/api/status")
def status():
    return {
        "status": "online",
        "version": "2.0.0",
        "translation_available": translation_available,
        "models": {
            "whisper": "base",
            "translation": "Helsinki-NLP/opus-mt-en-my"
        }
    }

# ================= 9. WEB UI =================
@app.get("/")
def root():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Subtitle Generator - Professional</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎬</text></svg>">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            padding: 40px;
            max-width: 750px;
            width: 100%;
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 25px 50px rgba(0,0,0,0.5);
        }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header p { color: #a8a8d8; font-size: 1rem; }
        .badges {
            display: flex;
            justify-content: center;
            gap: 8px;
            margin: 15px 0;
            flex-wrap: wrap;
        }
        .badge {
            background: rgba(102,126,234,0.15);
            color: #a8a8d8;
            padding: 5px 14px;
            border-radius: 20px;
            font-size: 0.75rem;
            border: 1px solid rgba(102,126,234,0.2);
        }
        .badge.highlight {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
        }
        .badge.myanmar {
            background: rgba(0,206,201,0.15);
            border-color: rgba(0,206,201,0.3);
            color: #00cec9;
        }
        .drop-zone {
            border: 2px dashed rgba(255,255,255,0.15);
            border-radius: 16px;
            padding: 40px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: rgba(255,255,255,0.03);
        }
        .drop-zone:hover, .drop-zone.dragover {
            border-color: #667eea;
            background: rgba(102,126,234,0.08);
            transform: translateY(-2px);
        }
        .drop-zone .icon { font-size: 3rem; margin-bottom: 8px; }
        .drop-zone .title { color: #e0e0e0; font-size: 1.1rem; font-weight: 500; }
        .drop-zone .subtitle { color: #8888aa; font-size: 0.85rem; margin-top: 4px; }
        .file-info {
            display: none;
            margin-top: 15px;
            padding: 15px;
            background: rgba(102,126,234,0.1);
            border-radius: 12px;
            border: 1px solid rgba(102,126,234,0.2);
        }
        .file-info .name { color: #e0e0e0; font-weight: 500; }
        .file-info .size { color: #8888aa; font-size: 0.9rem; margin-left: 10px; }
        .file-info .remove {
            float: right;
            color: #ff6b6b;
            cursor: pointer;
            font-weight: 600;
        }
        .file-info .remove:hover { color: #ff4757; }
        
        .settings {
            margin-top: 20px;
            padding: 20px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .settings-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .settings-group label {
            color: #a8a8d8;
            display: block;
            font-size: 0.85rem;
            margin-bottom: 5px;
        }
        .settings-group select, .settings-group input[type="checkbox"] {
            width: 100%;
            padding: 10px 12px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            color: #e0e0e0;
            font-size: 0.9rem;
            cursor: pointer;
        }
        .settings-group select option {
            background: #1a1a2e;
            color: #e0e0e0;
        }
        .settings-group .checkbox-label {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #a8a8d8;
            cursor: pointer;
        }
        .settings-group .checkbox-label input[type="checkbox"] {
            width: 18px;
            height: 18px;
            accent-color: #667eea;
            cursor: pointer;
        }
        
        .flow-diagram {
            margin-top: 20px;
            padding: 20px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .flow-step {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 6px 0;
            color: #a8a8d8;
            font-size: 0.85rem;
        }
        .flow-step .num {
            width: 24px;
            height: 24px;
            background: rgba(102,126,234,0.2);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            color: #667eea;
            font-weight: 600;
            flex-shrink: 0;
        }
        .flow-step .arrow {
            color: #444466;
            margin: 0 4px;
        }
        
        .btn-generate {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(102,126,234,0.3);
            margin-top: 20px;
            display: none;
        }
        .btn-generate:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(102,126,234,0.5);
        }
        .btn-generate:disabled { opacity: 0.6; cursor: not-allowed; }
        
        .btn-generate .spinner {
            display: none;
            width: 24px;
            height: 24px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 0.8s ease-in-out infinite;
            margin: 0 auto;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .btn-generate.loading .spinner { display: block; }
        .btn-generate.loading .text { display: none; }
        
        .progress-container {
            display: none;
            margin-top: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 15px;
        }
        .progress-bar {
            width: 100%;
            height: 6px;
            background: rgba(255,255,255,0.1);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-bar .fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            width: 0%;
            border-radius: 3px;
            transition: width 0.5s ease;
        }
        .progress-text { color: #a8a8d8; font-size: 0.9rem; text-align: center; }
        
        #status {
            margin-top: 15px;
            padding: 12px 16px;
            border-radius: 12px;
            text-align: center;
            display: none;
        }
        #status.success {
            display: block;
            background: rgba(0,206,201,0.1);
            border: 1px solid rgba(0,206,201,0.2);
            color: #00cec9;
        }
        #status.error {
            display: block;
            background: rgba(255,107,107,0.1);
            border: 1px solid rgba(255,107,107,0.2);
            color: #ff6b6b;
        }
        #status.info {
            display: block;
            background: rgba(102,126,234,0.1);
            border: 1px solid rgba(102,126,234,0.2);
            color: #a8a8d8;
        }
        
        #download-section {
            display: none;
            margin-top: 20px;
            text-align: center;
        }
        #download-section .btn-download {
            display: inline-block;
            padding: 14px 40px;
            background: linear-gradient(135deg, #00b894 0%, #00cec9 100%);
            color: white;
            text-decoration: none;
            border-radius: 12px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(0,206,201,0.3);
        }
        #download-section .btn-download:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(0,206,201,0.5);
        }
        #download-section .meta-info {
            color: #8888aa;
            font-size: 0.8rem;
            margin-top: 10px;
        }
        
        @media (max-width: 640px) {
            .container { padding: 20px; }
            .header h1 { font-size: 1.8rem; }
            .settings-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 AI Subtitle Generator</h1>
            <p>Transcribe & Translate to Myanmar 🇲🇲</p>
            <div class="badges">
                <span class="badge highlight">⚡ Pro</span>
                <span class="badge myanmar">🇲🇲 Myanmar</span>
                <span class="badge">🎯 Auto-Detect</span>
                <span class="badge">🌍 7 Languages</span>
                <span class="badge">📥 SRT</span>
            </div>
        </div>
        
        <div class="drop-zone" id="dropZone">
            <div class="icon
