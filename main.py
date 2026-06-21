import sys
import traceback
import gradio as gr
import whisper
import tempfile
import os
import re
import subprocess
import torch
from transformers import MarianMTModel, MarianTokenizer

print("=" * 50)
print("Starting application...")
print("=" * 50)

# Force all errors to be printed
sys.stderr = sys.stdout

try:
    print("📥 Loading Whisper model...")
    model = whisper.load_model("base")
    print("✅ Whisper model loaded!")
except Exception as e:
    print(f"❌ ERROR loading Whisper: {e}")
    traceback.print_exc()
    sys.exit(1)

# ================= TRANSLATION MODELS =================
try:
    print("📥 Setting up translation models...")
    translation_models = {
        "English → Myanmar": "Helsinki-NLP/opus-mt-en-my",
        "English → Thai": "Helsinki-NLP/opus-mt-en-th",
        "English → Vietnamese": "Helsinki-NLP/opus-mt-en-vi",
        "English → Chinese": "Helsinki-NLP/opus-mt-en-zh",
        "English → Japanese": "Helsinki-NLP/opus-mt-en-jap",
        "English → Korean": "Helsinki-NLP/opus-mt-en-ko",
    }
    print("✅ Translation models configured!")
except Exception as e:
    print(f"❌ ERROR setting up translation: {e}")
    traceback.print_exc()
    sys.exit(1)

loaded_tokenizer = None
loaded_mt_model = None
current_model_name = None

def load_translation_model(model_path):
    global loaded_tokenizer, loaded_mt_model, current_model_name
    if current_model_name == model_path:
        return True
    try:
        print(f"📥 Loading translation model: {model_path}")
        loaded_tokenizer = MarianTokenizer.from_pretrained(model_path)
        loaded_mt_model = MarianMTModel.from_pretrained(model_path)
        current_model_name = model_path
        return True
    except Exception as e:
        print(f"❌ Failed to load translation model: {e}")
        return False

def format_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def extract_audio_from_video(video_path, output_audio_path):
    try:
        cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y", output_audio_path]
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return os.path.exists(output_audio_path)
    except:
        return False

def transcribe(video, source_language, target_language):
    if video is None:
        return "❌ Video not found", None
    
    audio_path = os.path.join(tempfile.gettempdir(), "temp_audio.wav")
    if not extract_audio_from_video(str(video), audio_path):
        return "❌ Audio extraction failed", None
    
    lang_map = {
        "Auto Detect": None,
        "English": "en",
        "Myanmar": "my",
        "Thai": "th",
        "Vietnamese": "vi",
        "Chinese": "zh",
        "Japanese": "ja",
        "Korean": "ko"
    }
    
    language = lang_map.get(source_language, None)
    
    print(f"🔍 Transcribing with language: {language}")
    result = model.transcribe(audio_path, language=language, verbose=False)
    
    srt = ""
    
    for i, seg in enumerate(result["segments"], 1):
        original_text = re.sub(r"\s+", " ", seg["text"].strip())
        if len(original_text) < 2:
            continue
        
        srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{original_text}\n\n"
    
    srt_file = os.path.join(tempfile.gettempdir(), "subtitles.srt")
    with open(srt_file, "w", encoding="utf-8") as f:
        f.write(srt)
    
    preview = f"✅ Source: {source_language}\n✅ Target: {target_language}\n{'='*50}\n\n{srt}"
    
    return preview, srt_file

# ================= UI =================
print("🖥️ Building Gradio UI...")

try:
    # SUPER SIMPLE UI - No nested components
    with gr.Blocks(title="🎬 AI Subtitle Generator") as demo:
        gr.Markdown("# 🎬 AI Subtitle Generator")
        gr.Markdown("### Professional Transcription & Translation Powered by AI")
        
        with gr.Row():
            with gr.Column():
                video_input = gr.Video(label="Upload Video")
                source_lang = gr.Dropdown(
                    ["Auto Detect", "English", "Myanmar", "Thai", "Vietnamese", "Chinese", "Japanese", "Korean"],
                    label="Source Language"
                )
                target_lang = gr.Dropdown(
                    ["English", "Myanmar", "Thai", "Vietnamese", "Chinese", "Japanese", "Korean"],
                    label="Target Language"
                )
                submit_btn = gr.Button("Generate Subtitles")
            
            with gr.Column():
                sub_out = gr.Textbox(label="Subtitle Preview", lines=15)
                file_out = gr.File(label="Download SRT")
        
        submit_btn.click(transcribe, [video_input, source_lang, target_lang], [sub_out, file_out])
    
    print("✅ UI built successfully!")
    
except Exception as e:
    print(f"❌ ERROR building UI: {e}")
    traceback.print_exc()
    sys.exit(1)

print("=" * 50)

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 8080))
        print(f"🚀 Starting server on port {port}...")
        print("=" * 50)
        
        demo.launch(
            server_name="0.0.0.0", 
            server_port=port,
            theme=gr.themes.Soft(primary_hue="indigo")
        )
    except Exception as e:
        print(f"❌ ERROR launching: {e}")
        traceback.print_exc()
        sys.exit(1)
