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
model = whisper.load_model("base")

# ================= TRANSLATION MODELS =================
translation_models = {
    # Direct translations
    "English → Myanmar": "Helsinki-NLP/opus-mt-en-my",
    "English → Thai": "Helsinki-NLP/opus-mt-en-th",
    "English → Vietnamese": "Helsinki-NLP/opus-mt-en-vi",
    "English → Chinese": "Helsinki-NLP/opus-mt-en-zh",
    "English → Japanese": "Helsinki-NLP/opus-mt-en-jap",
    "English → Korean": "Helsinki-NLP/opus-mt-en-ko",
    
    # Reverse translations
    "Myanmar → English": "Helsinki-NLP/opus-mt-my-en",
    "Thai → English": "Helsinki-NLP/opus-mt-th-en",
    "Vietnamese → English": "Helsinki-NLP/opus-mt-vi-en",
    "Chinese → English": "Helsinki-NLP/opus-mt-zh-en",
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

def translate_with_bridge(text, source_lang, target_lang):
    """Translate using English as a bridge language"""
    try:
        # Step 1: Source → English
        source_to_english_key = f"{source_lang} → English"
        if source_to_english_key in translation_models:
            load_translation_model(translation_models[source_to_english_key])
            inputs = loaded_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            outputs = loaded_mt_model.generate(**inputs, max_length=512, num_beams=1)
            english_text = loaded_tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Step 2: English → Target
            english_to_target_key = f"English → {target_lang}"
            if english_to_target_key in translation_models:
                load_translation_model(translation_models[english_to_target_key])
                inputs = loaded_tokenizer(english_text, return_tensors="pt", truncation=True, max_length=512)
                outputs = loaded_mt_model.generate(**inputs, max_length=512, num_beams=1)
                translated_text = loaded_tokenizer.decode(outputs[0], skip_special_tokens=True)
                return translated_text
            else:
                return english_text
        else:
            return text
    except Exception as e:
        print(f"Bridge translation error: {e}")
        return text

def transcribe(video, source_language, target_language):
    if video is None:
        return "❌ Video not found", None
    
    audio_path = os.path.join(tempfile.gettempdir(), "temp_audio.wav")
    if not extract_audio_from_video(str(video), audio_path):
        return "❌ Audio extraction failed", None
    
    # Language mapping for Whisper
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
    translated_count = 0
    bridge_used = False
    
    # Check if direct translation exists
    direct_key = f"{source_language} → {target_language}"
    reverse_key = f"{target_language} → {source_language}"
    
    # Check if we need to use bridge translation
    if source_language != "Auto Detect" and source_language != target_language:
        if direct_key in translation_models:
            load_translation_model(translation_models[direct_key])
            print(f"✅ Using direct translation: {source_language} → {target_language}")
        elif reverse_key in translation_models:
            load_translation_model(translation_models[reverse_key])
            print(f"✅ Using reverse translation: {reverse_key}")
        elif source_language in ["Chinese", "Japanese", "Korean"] and target_language in ["Myanmar", "Thai", "Vietnamese"]:
            bridge_used = True
            print(f"🔄 Using English as bridge: {source_language} → English → {target_language}")
        else:
            print(f"⚠️ No translation model found")
            loaded_tokenizer = None
            loaded_mt_model = None
    
    for i, seg in enumerate(result["segments"], 1):
        original_text = re.sub(r"\s+", " ", seg["text"].strip())
        if len(original_text) < 2:
            continue
        
        if source_language != "Auto Detect" and source_language != target_language:
            try:
                if bridge_used:
                    translated_text = translate_with_bridge(original_text, source_language, target_language)
                elif loaded_tokenizer and loaded_mt_model:
                    inputs = loaded_tokenizer(original_text, return_tensors="pt", truncation=True, max_length=512)
                    outputs = loaded_mt_model.generate(**inputs, max_length=512, num_beams=1)
                    translated_text = loaded_tokenizer.decode(outputs[0], skip_special_tokens=True)
                else:
                    translated_text = original_text
                translated_count += 1
            except Exception as e:
                print(f"Translation error: {e}")
                translated_text = original_text
        else:
            translated_text = original_text
        
        srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{translated_text}\n\n"
    
    print(f"✅ Translated {translated_count} segments to {target_language}")
    
    srt_file = os.path.join(tempfile.gettempdir(), "subtitles.srt")
    with open(srt_file, "w", encoding="utf-8") as f:
        f.write(srt)
    
    preview = f"✅ Source: {source_language}\n✅ Target: {target_language}\n"
    preview += f"✅ Translated: {translated_count} segments\n"
    if bridge_used:
        preview += f"🔄 Using English as bridge translation\n"
    preview += f"{'='*50}\n\n{srt}"
    
    return preview, srt_file

# ================= UI - FIXED FOR GRADIO 6.0 =================

# FIX 1: Remove theme from Blocks constructor
demo = gr.Blocks(title="🎬 AI Subtitle Generator")

with demo:
    gr.Markdown("""
    # 🎬 AI Subtitle Generator
    ### Professional Transcription & Translation Powered by AI
    **Supported Languages:** English, Myanmar, Thai, Vietnamese, Chinese, Japanese, Korean
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.Video(label="📹 Upload Video", height=300)
            
            with gr.Row():
                source_lang = gr.Dropdown(
                    choices=["Auto Detect", "English", "Myanmar", "Thai", "Vietnamese", "Chinese", "Japanese", "Korean"],
                    value="Auto Detect",
                    label="🎯 Source Language"
                )
                target_lang = gr.Dropdown(
                    choices=["English", "Myanmar", "Thai", "Vietnamese", "Chinese", "Japanese", "Korean"],
                    value="Myanmar",
                    label="🌏 Target Language"
                )
            
            # FIX 2: Remove 'full_width' parameter - use variant only
            submit_btn = gr.Button("⚡ Generate Subtitles", variant="primary")
            
        with gr.Column(scale=1):
            sub_out = gr.Textbox(label="📝 Subtitle Preview", lines=15)
            file_out = gr.File(label="📥 Download SRT")
    
    submit_btn.click(
        transcribe, 
        inputs=[video_input, source_lang, target_lang], 
        outputs=[sub_out, file_out]
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # FIX 3: Move theme to launch() method
    demo.launch(
        server_name="0.0.0.0", 
        server_port=port,
        theme=gr.themes.Soft(primary_hue="indigo")
)
