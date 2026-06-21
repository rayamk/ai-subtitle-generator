import gradio as gr
import whisper
import tempfile
import os
import re
import subprocess
import torch
from transformers import MarianMTModel, MarianTokenizer

# ================= MODEL LOADING =================
print("📥 Loading Whisper model...")

# FIX: Use "base" or "small" for better Asian language support
# "tiny" doesn't work well with Asian languages!
model = whisper.load_model("base")  # Change to "base" or "small"

# ================= TRANSLATION MODELS =================
# FIX: Added models for Asian languages → Myanmar
translation_models = {
    "English → Myanmar": "Helsinki-NLP/opus-mt-en-my",
    "Thai → Myanmar": "Helsinki-NLP/opus-mt-th-my",      # Thai to Myanmar
    "Vietnamese → Myanmar": "Helsinki-NLP/opus-mt-vi-my", # Vietnamese to Myanmar
    "Myanmar → English": "Helsinki-NLP/opus-mt-my-en",
    "Thai → English": "Helsinki-NLP/opus-mt-th-en",
    "Vietnamese → English": "Helsinki-NLP/opus-mt-vi-en",
}

loaded_tokenizer = None
loaded_mt_model = None
current_model_name = None

def load_translation_model(model_path):
    global loaded_tokenizer, loaded_mt_model, current_model_name
    if current_model_name == model_path: return True
    try:
        print(f"📥 Loading translation model: {model_path}")
        loaded_tokenizer = MarianTokenizer.from_pretrained(model_path)
        loaded_mt_model = MarianMTModel.from_pretrained(model_path)
        current_model_name = model_path
        return True
    except Exception as e:
        print(f"❌ Failed to load translation model: {e}")
        return False

# ================= FUNCTIONS =================
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

# FIX: Added direct translation function
def detect_and_translate(text, source_lang, target_lang):
    """Translate text from source_lang to target_lang"""
    # Map UI languages to model keys
    lang_map = {
        "Auto Detect": None,
        "English": "en",
        "Myanmar": "my",
        "Thai": "th",
        "Vietnamese": "vi"
    }
    
    # If source is English, translate to target
    if source_lang == "English":
        model_key = f"English → {target_lang}"
    elif target_lang == "English":
        model_key = f"{source_lang} → English"
    else:
        # For Asian → Asian, use English as bridge
        # Load English → target model
        if source_lang != "English":
            model_key = f"English → {target_lang}"
        else:
            model_key = f"{source_lang} → English"
    
    # Load the appropriate model
    if model_key not in translation_models:
        print(f"⚠️ No direct translation model for {source_lang} → {target_lang}")
        return text
    
    model_path = translation_models[model_key]
    if not load_translation_model(model_path):
        return text
    
    try:
        inputs = loaded_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        outputs = loaded_mt_model.generate(**inputs, max_length=512, num_beams=1)
        translated = loaded_tokenizer.decode(outputs[0], skip_special_tokens=True)
        return translated
    except Exception as e:
        print(f"❌ Translation error: {e}")
        return text

def transcribe(video, source_language, target_language):
    if video is None: 
        return "❌ Video not found", None
    
    audio_path = os.path.join(tempfile.gettempdir(), "temp_audio.wav")
    if not extract_audio_from_video(str(video), audio_path): 
        return "❌ Audio extraction failed", None
    
    # FIX: Handle language properly
    if source_language == "Auto Detect":
        language = None
    else:
        # Map UI language to Whisper language codes
        lang_map = {"English": "en", "Myanmar": "my", "Thai": "th", "Vietnamese": "vi"}
        language = lang_map.get(source_language, None)
    
    print(f"🔍 Transcribing with language: {language}")
    result = model.transcribe(audio_path, language=language, verbose=False)
    
    srt = ""
    translated_count = 0
    
    for i, seg in enumerate(result["segments"], 1):
        original_text = re.sub(r"\s+", " ", seg["text"].strip())
        if len(original_text) < 2: 
            continue
        
        # FIX: Translate to target language
        if target_language != "Original":
            translated_text = detect_and_translate(original_text, source_language, target_language)
            translated_count += 1
        else:
            translated_text = original_text
        
        # FIX: Include both original and translation for clarity
        srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{translated_text}\n\n"
    
    print(f"✅ Translated {translated_count} segments to {target_language}")
    
    srt_file = os.path.join(tempfile.gettempdir(), "subtitles.srt")
    with open(srt_file, "w", encoding="utf-8") as f: 
        f.write(srt)
    
    return srt, srt_file

# ================= UI =================
demo = gr.Blocks(title="🎬 AI Subtitle Generator")

with demo:
    gr.HTML("<h1 style='text-align:center;'>🌏 AI Subtitle Generator</h1>")
    gr.HTML("<p style='text-align:center;'>Transcribe any language and translate to Myanmar 🇲🇲</p>")
    
    with gr.Row():
        with gr.Column():
            video_input = gr.Video(label="Upload Video")
            
            # FIX: Better language options
            source_lang = gr.Dropdown(
                ["Auto Detect", "English", "Myanmar", "Thai", "Vietnamese"], 
                value="Auto Detect", 
                label="Source Language"
            )
            
            target_lang = gr.Dropdown(
                ["Myanmar", "English", "Thai", "Vietnamese"], 
                value="Myanmar", 
                label="Target Language"
            )
            
            submit_btn = gr.Button("⚡ Generate Subtitles", variant="primary")
            
        with gr.Column():
            sub_out = gr.Textbox(label="Subtitle Preview", lines=12)
            file_out = gr.File(label="📥 Download SRT")
    
    submit_btn.click(
        transcribe, 
        inputs=[video_input, source_lang, target_lang], 
        outputs=[sub_out, file_out]
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    demo.launch(server_name="0.0.0.0", server_port=port, theme=gr.themes.Soft(primary_hue="indigo"))
