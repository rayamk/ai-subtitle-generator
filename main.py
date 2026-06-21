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
    "Chinese → English": "Helsinki-NLP/opus-mt-zh-en",  # Added Chinese → English
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
            # Direct translation exists
            load_translation_model(translation_models[direct_key])
            print(f"✅ Using direct translation: {source_language} → {target_language}")
        elif reverse_key in translation_models:
            # Reverse translation exists (will translate in reverse)
            load_translation_model(translation_models[reverse_key])
            print(f"✅ Using reverse translation: {reverse_key}")
        elif source_language in ["Chinese", "Japanese", "Korean"] and target_language in ["Myanmar", "Thai", "Vietnamese"]:
            # Use bridge translation via English for Asian → Asian
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
                    # Use bridge translation for Chinese → Myanmar
                    translated_text = translate_with_bridge(original_text, source_language, target_language)
                elif loaded_tokenizer and loaded_mt_model:
                    # Direct translation
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

# ================= PROFESSIONAL UI =================
custom_css = """
<style>
    .gradio-container {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    .gr-box {
        background: white !important;
        border-radius: 16px !important;
        box-shadow: 0 10px 40px rgba(0,0,0,0.08) !important;
        padding: 20px !important;
        border: none !important;
    }
    
    h1 {
        color: #1a1a2e !important;
        font-weight: 700 !important;
        font-size: 2.5rem !important;
        margin-bottom: 0.5rem !important;
        letter-spacing: -0.5px !important;
    }
    
    .subtitle {
        color: #4a4a6a !important;
        font-size: 1.1rem !important;
        font-weight: 400 !important;
        margin-top: -0.5rem !important;
        opacity: 0.8 !important;
    }
    
    .gr-button-primary {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 14px 32px !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
        color: white !important;
    }
    
    .gr-button-primary:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5) !important;
    }
    
    .gr-dropdown {
        border-radius: 10px !important;
        border: 2px solid #e8ecf1 !important;
        transition: all 0.3s ease !important;
    }
    
    .gr-dropdown:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    
    .gr-textbox {
        border-radius: 12px !important;
        border: 2px solid #e8ecf1 !important;
        font-family: 'Consolas', monospace !important;
        font-size: 14px !important;
        line-height: 1.6 !important;
    }
    
    .badge {
        display: inline-block;
        background: rgba(102, 126, 234, 0.1);
        color: #667eea;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 4px;
    }
</style>
"""

# ================= UI =================
with gr.Blocks(title="🎬 AI Subtitle Generator", theme=gr.themes.Soft()) as demo:
    gr.HTML(custom_css)
    
    gr.HTML("""
    <div style='text-align: center; padding: 20px 0 10px 0;'>
        <h1>🎬 AI Subtitle Generator</h1>
        <p class='subtitle'>Professional Transcription & Translation Powered by AI</p>
        <div style='display: flex; justify-content: center; gap: 10px; margin-top: 10px; flex-wrap: wrap;'>
            <span class='badge'>🎯 Whisper AI</span>
            <span class='badge'>🌍 8+ Languages</span>
            <span class='badge'>⚡ Real-time</span>
            <span class='badge'>🔄 Bridge Translation</span>
        </div>
    </div>
    """)
    
    with gr.Row(equal_height=True):
        with gr.Column(scale=1, min_width=400):
            with gr.Group():
                gr.Markdown("### 📤 Upload Media")
                video_input = gr.Video(
                    label="",
                    height=300,
                    show_label=False
                )
            
            with gr.Group():
                gr.Markdown("### ⚙️ Language Settings")
                
                with gr.Row():
                    with gr.Column():
                        source_lang = gr.Dropdown(
                            choices=["Auto Detect", "English", "Myanmar", "Thai", "Vietnamese", "Chinese", "Japanese", "Korean"],
                            value="Auto Detect",
                            label="🎯 Source Language",
                            info="What language is spoken in the video?"
                        )
                    
                    with gr.Column():
                        target_lang = gr.Dropdown(
                            choices=["English", "Myanmar", "Thai", "Vietnamese", "Chinese", "Japanese", "Korean"],
                            value="Myanmar",
                            label="🌏 Target Language",
                            info="What language to translate to?"
                        )
            
            submit_btn = gr.Button(
                "⚡ Generate Subtitles",
                variant="primary",
                size="lg",
                full_width=True
            )
            
            gr.HTML("""
            <div style='background: #f8f9fc; padding: 16px; border-radius: 12px; margin-top: 10px; border-left: 4px solid #667eea;'>
                <p style='margin: 0; font-size: 0.9rem; color: #4a4a6a;'>
                    <strong>💡 Supported Translations:</strong><br>
                    ✅ English ↔ Myanmar, Thai, Vietnamese, Chinese, Japanese, Korean<br>
                    ✅ Chinese → Myanmar (via English bridge)<br>
                    ✅ Japanese → Myanmar (via English bridge)<br>
                    ✅ Korean → Myanmar (via English bridge)
                </p>
                <p style='margin: 8px 0 0 0; font-size: 0.8rem; color: #8a8aaa;'>
                    ⏱️ Processing time depends on video length and model size
                </p>
            </div>
            """)
        
        with gr.Column(scale=1, min_width=400):
            with gr.Group():
                gr.Markdown("### 📝 Subtitle Preview")
                sub_out = gr.Textbox(
                    label="",
                    lines=15,
                    show_label=False,
                    placeholder="Your subtitles will appear here..."
                )
            
            with gr.Group():
                gr.Markdown("### 💾 Export")
                file_out = gr.File(
                    label="",
                    show_label=False,
                    file_types=[".srt"]
                )
                
                gr.HTML("""
                <div style='display: flex; gap: 20px; margin-top: 10px;'>
                    <div style='flex: 1; text-align: center; padding: 10px; background: #f8f9fc; border-radius: 8px;'>
                        <span style='font-size: 0.8rem; color: #8a8aaa;'>Status</span>
                        <p style='margin: 0; font-weight: 600; color: #4a4a6a;'>Ready</p>
                    </div>
                    <div style='flex: 1; text-align: center; padding: 10px; background: #f8f9fc; border-radius: 8px;'>
                        <span style='font-size: 0.8rem; color: #8a8aaa;'>Format</span>
                        <p style='margin: 0; font-weight: 600; color: #4a4a6a;'>SRT</p>
                    </div>
                </div>
                """)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        theme=gr.themes.Soft(
            primary_hue="indigo",
            secondary_hue="purple",
            font=gr.themes.GoogleFont("Inter")
        ),
        show_api=False
            )
