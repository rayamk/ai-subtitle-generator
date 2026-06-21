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
model = whisper.load_model("tiny")

# ================= TRANSLATION MODELS =================
translation_models = {
    "English → Myanmar": "Helsinki-NLP/opus-mt-en-my",
    "English → Thai": "Helsinki-NLP/opus-mt-en-th",
    "English → Vietnamese": "Helsinki-NLP/opus-mt-en-vi",
    "English → Bengali": "Helsinki-NLP/opus-mt-en-bn",
    "English → Tagalog": "Helsinki-NLP/opus-mt-en-tl",
}

loaded_tokenizer = None
loaded_mt_model = None
current_model_name = None

def load_translation_model(model_path):
    global loaded_tokenizer, loaded_mt_model, current_model_name
    if current_model_name == model_path: return True
    try:
        loaded_tokenizer = MarianTokenizer.from_pretrained(model_path)
        loaded_mt_model = MarianMTModel.from_pretrained(model_path)
        current_model_name = model_path
        return True
    except: return False

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
    except: return False

def transcribe(video, language_code, target_language):
    if video is None: return "❌ Video not found", None
    
    model_path = translation_models.get(target_language)
    load_translation_model(model_path)
    
    audio_path = os.path.join(tempfile.gettempdir(), "temp_audio.wav")
    if not extract_audio_from_video(str(video), audio_path): return "❌ Audio extraction failed", None
        
    result = model.transcribe(audio_path, language=language_code if language_code != "Auto" else None, verbose=False)
    
    srt = ""
    for i, seg in enumerate(result["segments"], 1):
        text = re.sub(r"\s+", " ", seg["text"].strip())
        if len(text) < 2: continue
        
        # Translate
        translated = text
        if loaded_tokenizer and loaded_mt_model:
            inputs = loaded_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            outputs = loaded_mt_model.generate(**inputs, max_length=512, num_beams=1)
            translated = loaded_tokenizer.decode(outputs[0], skip_special_tokens=True)
            
        srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{translated}\n\n"
        
    srt_file = os.path.join(tempfile.gettempdir(), "subtitles.srt")
    with open(srt_file, "w", encoding="utf-8") as f: f.write(srt)
    return srt, srt_file

# ================= UI =================
with gr.Blocks(title="🎬 AI Subtitle Myanmar", theme=gr.themes.Soft(primary_hue="indigo")) as demo:
    gr.HTML("<h1 style='text-align:center;'>🌏 AI Subtitle Generator</h1>")
    with gr.Row():
        with gr.Column():
            video_input = gr.Video(label="Upload Video")
            lang_in = gr.Dropdown(["Auto Detect", "English", "Tiếng Việt", "ไทย"], value="Auto Detect", label="Source")
            lang_out = gr.Dropdown(list(translation_models.keys()), value="English → Myanmar", label="Target")
            submit_btn = gr.Button("⚡ Generate Subtitles", variant="primary")
        with gr.Column():
            sub_out = gr.Textbox(label="Subtitle Preview", lines=12)
            file_out = gr.File(label="📥 Download SRT")
    
    submit_btn.click(transcribe, inputs=[video_input, lang_in, lang_out], outputs=[sub_out, file_out])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    demo.launch(server_name="0.0.0.0", server_port=port)
        
