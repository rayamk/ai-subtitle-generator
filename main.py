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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

print("=" * 60)
print("🎬 AI Subtitle Generator v2.0.0")
print("=" * 60)

print("📥 Loading Whisper model...")
model = whisper.load_model("tiny")
print("✅ Whisper model loaded!")

print("📥 Loading translation model (English → Myanmar)...")
try:
    translation_tokenizer = MarianTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-mn")
    translation_model = MarianMTModel.from_pretrained("Helsinki-NLP/opus-mt-en-mn")
    print("✅ Translation model loaded!")
    translation_available = True
except Exception as e:
    print(f"⚠️ Translation model not available: {e}")
    translation_available = False

def extract_audio(video_path):
    audio_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.wav")
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y", audio_path]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return audio_path if os.path.exists(audio_path) else None

def detect_language(text):
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

def translate_to_myanmar(text):
    if not translation_available:
        return text
    try:
        chunks = [text[i:i+256] for i in range(0, len(text), 256)]
        translated_chunks = []
        for chunk in chunks:
            inputs = translation_tokenizer(chunk, return_tensors="pt", truncation=True, max_length=512, padding=True)
            outputs = translation_model.generate(**inputs, max_length=512, num_beams=5, early_stopping=True, temperature=0.7)
            translated = translation_tokenizer.decode(outputs[0], skip_special_tokens=True)
            translated_chunks.append(translated)
        result = " ".join(translated_chunks)
        return result
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def cleanup_myanmar_grammar(text):
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

def format_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

@app.post("/api/transcribe")
async def transcribe(
    video: UploadFile = File(...),
    translate: str = Form("true"),
    target_language: str = Form("myanmar"),
    source_language: str = Form("auto")
):
    try:
        print("📤 Step 1: Saving video...")
        video_id = str(uuid.uuid4())
        video_path = os.path.join("uploads", f"{video_id}_{video.filename}")
        with open(video_path, "wb") as f:
            while chunk := await video.read(1024 * 1024):
                f.write(chunk)

        print("🎵 Step 2: Extracting audio...")
        audio_path = extract_audio(video_path)
        if not audio_path:
            return {"error": "Failed to extract audio from video"}

        print("🎤 Step 3: Transcribing with Whisper...")
        if source_language == "auto":
            result = model.transcribe(audio_path, verbose=False)
        else:
            lang_map = {"english": "en", "chinese": "zh", "japanese": "ja", "korean": "ko", "thai": "th", "vietnamese": "vi"}
            lang_code = lang_map.get(source_language, None)
            result = model.transcribe(audio_path, language=lang_code, verbose=False)

        print("📝 Step 4: Generating subtitles...")
        srt = ""
        translated_count = 0
        detected_lang = "english"

        if result["segments"]:
            first_text = result["segments"][0]["text"]
            detected_lang = detect_language(first_text)
            print(f"🔍 Detected language: {detected_lang}")

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
                        print(f"Translation error: {e}")
                        final_text = original_text
                else:
                    final_text = original_text

                srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{final_text}\n\n"

        print("💾 Step 5: Saving files...")
        srt_filename = f"{video_id}.srt"
        srt_path = os.path.join("outputs", srt_filename)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt)

        os.remove(video_path)
        os.remove(audio_path)

        print(f"✅ Complete! Translated {translated_count} segments")

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

@app.get("/api/status")
def status():
    return {
        "status": "online",
        "version": "2.0.0",
        "translation_available": translation_available,
        "models": {
            "whisper": "tiny",
            "translation": "Helsinki-NLP/opus-mt-en-mn" if translation_available else "not loaded"
        }
    }

@app.get("/")
def root():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(html_content)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
