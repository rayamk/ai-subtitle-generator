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
model = whisper.load_model("base")  # Better for Asian languages

# ================= TRANSLATION MODELS =================
# These models work offline and don't need googletrans
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
    
    # Load translation model if source is not auto
    if source_language != "Auto Detect" and target_language != source_language:
        translation_key = f"{source_language} → {target_language}"
        
        # Try direct translation
        if translation_key in translation_models:
            load_translation_model(translation_models[translation_key])
        else:
            # Try English as bridge language
            bridge_key = f"English → {target_language}"
            if bridge_key in translation_models:
                print(f"🔄 Using English as bridge language")
                load_translation_model(translation_models[bridge_key])
            else:
                print(f"⚠️ No translation model for {source_language} → {target_language}")
                loaded_tokenizer = None
                loaded_mt_model = None
    
    for i, seg in enumerate(result["segments"], 1):
        original_text = re.sub(r"\s+", " ", seg["text"].strip())
        if len(original_text) < 2: 
            continue
        
        # Translate if model is loaded and target different from source
        if loaded_tokenizer and loaded_mt_model and target_language != source_language:
            try:
                # If source is not English, translate to English first then to target
                if source_language != "English" and source_language != "Auto Detect":
                    # Step 1: Translate to English
                    en_key = f"{source_language} → English"
                    if en_key in translation_models:
                        load_translation_model(translation_models[en_key])
                        inputs = loaded_tokenizer(original_text, return_tensors="pt", truncation=True, max_length=512)
                        outputs = loaded_mt_model.generate(**inputs, max_length=512, num_beams=1)
                        english_text = loaded_tokenizer.decode(outputs[0], skip_special_tokens=True)
                        
                        # Step 2: Translate English to target
                        target_key = f"English → {target_language}"
                        if target_key in translation_models:
                            load_translation_model(translation_models[target_key])
                            inputs = loaded_tokenizer(english_text, return_tensors="pt", truncation=True, max_length=512)
                            outputs = loaded_mt_model.generate(**inputs, max_length=512, num_beams=1)
                            translated_text = loaded_tokenizer.decode(outputs[0], skip_special_tokens=True)
                        else:
                            translated_text = english_text
                    else:
                        translated_text = original_text
                else:
                    # Direct translation from English to target
                    inputs = loaded_tokenizer(original_text, return_tensors="pt", truncation=True, max_length=512)
                    outputs = loaded_mt_model.generate(**inputs, max_length=512, num_beams=1)
                    translated_text = loaded_tokenizer.decode(outputs[0], skip_special_tokens=True)
                
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
    preview += f"✅ Translation Model: {'Loaded' if loaded_tokenizer else 'Not available'}\n"
    preview += f"{'='*50}\n\n{srt}"
    
    return preview, srt_file

# ================= UI =================
demo = gr.Blocks(title="🎬 AI Subtitle Generator")

with demo:
    gr.HTML("""
    <h1 style='text-align:center;'>🌏 AI Subtitle Generator</h1>
    <p style='text-align:center; color:#666;'>Transcribe & Translate to any language</p>
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.Video(label="📹 Upload Video")
            
            lang_choices = ["Auto Detect", "English", "Myanmar", "Thai", "Vietnamese", "Chinese", "Japanese", "Korean"]
            
            source_lang = gr.Dropdown(
                choices=lang_choices,
                value="Auto Detect",
                label="🎯 Source Language"
            )
            
            target_lang = gr.Dropdown(
                choices=["English", "Myanmar", "Thai", "Vietnamese", "Chinese", "Japanese", "Korean"],
                value="Myanmar",
                label="🌏 Translate To"
            )
            
            submit_btn = gr.Button("⚡ Generate Subtitles", variant="primary")
            
        with gr.Column(scale=1):
            sub_out = gr.Textbox(label="📝 Subtitle Preview", lines=15)
            file_out = gr.File(label="📥 Download SRT File")
    
    submit_btn.click(
        transcribe, 
        inputs=[video_input, source_lang, target_lang], 
        outputs=[sub_out, file_out]
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    demo.launch(server_name="0.0.0.0", server_port=port, theme=gr.themes.Soft(primary_hue="indigo"))
