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

# ================= MODEL LOADING =================
print("📥 Loading Whisper model...")
model = whisper.load_model("base")
print("✅ Whisper model loaded!")

# ================= TRANSLATION MODELS =================
translation_models = {
    "English → Myanmar": "Helsinki-NLP/opus-mt-en-my",
    "English → Thai": "Helsinki-NLP/opus-mt-en-th",
    "English → Vietnamese": "Helsinki-NLP/opus-mt-en-vi",
    "English → Chinese": "Helsinki-NLP/opus-mt-en-zh",
    "English → Japanese": "Helsinki-NLP/opus-mt-en-jap",
    "English → Korean": "Helsinki-NLP/opus-mt-en-ko",
}

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
    demo = gr.Blocks(title="🎬 AI Subtitle Generator")
    print("✅ Blocks created")
except Exception as e:
    print(f"❌ Error creating Blocks: {e}")
    raise

with demo:
    print("📍 Inside Blocks context")
    
    gr.Markdown("""
    # 🎬 AI Subtitle Generator
    ### Professional Transcription & Translation Powered by AI
    """)
    print("✅ Markdown added")
    
    with gr.Row():
        print("📍 Inside Row")
        
        with gr.Column(scale=1):
            print("📍 Inside Column 1")
            video_input = gr.Video(label="📹 Upload Video", height=300)
            print("✅ Video input added")
            
            with gr.Row():
                print("📍 Inside nested Row")
                source_lang = gr.Dropdown(
                    choices=["Auto Detect", "English", "Myanmar", "Thai", "Vietnamese", "Chinese", "Japanese", "Korean"],
                    value="Auto Detect",
                    label="🎯 Source Language"
                )
                print("✅ Source dropdown added")
                
                target_lang = gr.Dropdown(
                    choices=["English", "Myanmar", "Thai", "Vietnamese", "Chinese", "Japanese", "Korean"],
                    value="Myanmar",
                    label="🌏 Target Language"
                )
                print("✅ Target dropdown added")
            
            submit_btn = gr.Button("⚡ Generate Subtitles", variant="primary")
            print("✅ Button added")
            
        with gr.Column(scale=1):
            print("📍 Inside Column 2")
            sub_out = gr.Textbox(label="📝 Subtitle Preview", lines=15)
            print("✅ Textbox added")
            
            file_out = gr.File(label="📥 Download SRT")
            print("✅ File output added")
    
    submit_btn.click(
        transcribe, 
        inputs=[video_input, source_lang, target_lang], 
        outputs=[sub_out, file_out]
    )
    print("✅ Click handler added")

print("✅ UI built successfully!")
print("=" * 50)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting server on port {port}...")
    print("=" * 50)
    
    demo.launch(
        server_name="0.0.0.0", 
        server_port=port,
        theme=gr.themes.Soft(primary_hue="indigo")
    )
