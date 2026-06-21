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

app = FastAPI(title="AI Subtitle Generator", version="2.0.0")

# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= FOLDERS =================
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

print("=" * 60)
print("🎬 AI Subtitle Generator v2.0.0")
print("=" * 60)

# ================= WHISPER MODEL =================
print("📥 Loading Whisper model...")
model = whisper.load_model("tiny")
print("✅ Whisper loaded!")

# ================= TRANSLATION MODEL =================
print("📥 Loading translation model...")
try:
    tokenizer = MarianTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-mn")
    trans_model = MarianMTModel.from_pretrained("Helsinki-NLP/opus-mt-en-mn")
    translation_available = True
    print("✅ Translation loaded!")
except Exception as e:
    print("⚠️ Translation model failed:", e)
    translation_available = False

# ================= AUDIO EXTRACT =================
def extract_audio(video_path):
    audio_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.wav")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        audio_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("FFMPEG ERROR:", result.stderr)
        return None

    return audio_path if os.path.exists(audio_path) else None


# ================= TIME FORMAT =================
def format_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ================= TRANSLATE =================
def translate_to_myanmar(text):
    if not translation_available:
        return text

    try:
        chunks = [text[i:i+256] for i in range(0, len(text), 256)]
        out = []

        for c in chunks:
            inputs = tokenizer(
                c,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )

            outputs = trans_model.generate(
                **inputs,
                max_length=512,
                num_beams=5
            )

            out.append(tokenizer.decode(outputs[0], skip_special_tokens=True))

        return " ".join(out)

    except Exception as e:
        print("Translation error:", e)
        return text


# ================= CLEANUP =================
def cleanup(text):
    text = re.sub(r"\s+", " ", text)

    fixes = {
        r"သည်\s+": "က ",
        r"သည်။": "တယ်။",
        r"သည်\s": "တယ် ",
    }

    for k, v in fixes.items():
        text = re.sub(k, v, text)

    return text.strip()


# ================= TRANSCRIBE API =================
@app.post("/api/transcribe")
async def transcribe(
    video: UploadFile = File(...),
    translate: str = Form("true"),
    target_language: str = Form("myanmar"),
    source_language: str = Form("auto")
):
    video_path = None
    audio_path = None

    try:
        # ================= SAVE VIDEO =================
        video_id = str(uuid.uuid4())
        video_path = f"uploads/{video_id}_{video.filename}"

        with open(video_path, "wb") as f:
            while chunk := await video.read(1024 * 1024):
                f.write(chunk)

        # ================= EXTRACT AUDIO =================
        audio_path = extract_audio(video_path)
        if not audio_path:
            return {"error": "Audio extraction failed"}

        # ================= WHISPER =================
        if source_language == "auto":
            result = model.transcribe(audio_path)
        else:
            lang_map = {
                "english": "en",
                "chinese": "zh",
                "japanese": "ja",
                "korean": "ko",
                "thai": "th",
                "vietnamese": "vi"
            }
            result = model.transcribe(
                audio_path,
                language=lang_map.get(source_language)
            )

        segments = result.get("segments", [])

        # ================= SRT BUILD =================
        srt = ""
        idx = 1
        translated_count = 0

        for seg in segments:
            text = re.sub(r"\s+", " ", seg["text"].strip())
            if len(text) < 2:
                continue

            if translate == "true" and translation_available:
                text = cleanup(translate_to_myanmar(text))
                translated_count += 1

            srt += f"{idx}\n"
            srt += f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n"
            srt += f"{text}\n\n"
            idx += 1

        # ================= SAVE SRT =================
        out_file = f"{video_id}.srt"
        out_path = f"outputs/{out_file}"

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(srt)

        return FileResponse(
            out_path,
            media_type="text/plain",
            filename=f"subtitles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt",
            headers={
                "X-Translated": str(translated_count > 0),
                "X-Segments": str(len(segments))
            }
        )

    finally:
        # ================= CLEAN FILES =================
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)


# ================= STATUS =================
@app.get("/api/status")
def status():
    return {
        "status": "online",
        "version": "2.0.0",
        "translation": translation_available,
        "whisper": "tiny"
    }


# ================= HOME =================
@app.get("/")
def home():
    if not os.path.exists("index.html"):
        return HTMLResponse("index.html not found")

    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ================= RUN =================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
