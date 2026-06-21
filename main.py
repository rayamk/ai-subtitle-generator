import gradio as gr
import whisper
import tempfile
import os
import re
import subprocess
import torch
from transformers import MarianMTModel, MarianTokenizer

# ================= WHISPER MODEL =================
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
    if current_model_name == model_path:
        return True
    try:
        print(f"🔄 Loading translation model: {model_path}")
        loaded_tokenizer = MarianTokenizer.from_pretrained(model_path)
        loaded_mt_model = MarianMTModel.from_pretrained(model_path)
        current_model_name = model_path
        return True
    except Exception as e:
        print(f"❌ Translation model failed: {e}")
        return False

# ================= CORE FUNCTIONS =================
def format_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def clean_text(text):
    return re.sub(r"\s+", " ", text.strip())

def translate_to_target(text, target_model_path):
    if not text.strip() or loaded_tokenizer is None or loaded_mt_model is None:
        return text
    try:
        inputs = loaded_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        outputs = loaded_mt_model.generate(**inputs, max_length=512, num_beams=1)
        return loaded_tokenizer.decode(outputs[0], skip_special_tokens=True)
    except:
        return text

def merge_segments(segments, min_duration=1.0):
    if not segments: return []
    merged, temp = [], None
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text: continue
        if temp is None:
            temp = seg.copy()
            continue
        if (temp["end"] - temp["start"]) < min_duration:
            temp["text"] += " " + text
            temp["end"] = seg["end"]
        else:
            merged.append(temp)
            temp = seg.copy()
    if temp and temp.get("text", "").strip(): merged.append(temp)
    return merged

def extract_audio_from_video(video_path, output_audio_path):
    try:
        cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y", output_audio_path]
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return os.path.exists(output_audio_path)
    except:
        return False

# ================= TRANSCRIBE =================
def transcribe(video, language_code, target_language):
    if video is None: return "❌ Please upload a video", None
    
    model_path = translation_models.get(target_language)
    load_translation_model(model_path)
    
    audio_path = os.path.join(tempfile.gettempdir(), "temp_audio.wav")
    if not extract_audio_from_video(str(video), audio_path):
        return "❌ Audio extraction failed", None
        
    result = model.transcribe(audio_path, language=language_code, verbose=False)
    segments = merge_segments(result["segments"])
    
    srt = ""
    for i, seg in enumerate(segments, 1):
        text = clean_text(seg["text"])
        trans_text = translate_to_target(text, model_path)
        srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{trans_text}\n\n"
        
    srt_file = os.path.join(tempfile.gettempdir(), "subtitles.srt")
    with open(srt_file, "w", encoding="utf-8") as f: f.write(srt)
    return srt, srt_file

# ================= GRADIO UI =================
with gr.Blocks(title="🎬 AI Subtitle Myanmar") as demo:
    gr.Markdown("# 🌏 AI Subtitle Generator")
    video_input = gr.Video(label="Upload Video")
    lang_in = gr.Dropdown(["Auto Detect", "English", "Tiếng Việt", "ไทย"], value="Auto Detect", label="Source")
    lang_out = gr.Dropdown(list(translation_models.keys()), value="English → Myanmar", label="Target")
    submit_btn = gr.Button("⚡ Generate")
    sub_out = gr.Textbox(label="Subtitle Preview")
    file_out = gr.File(label="📥 Download")
    
    submit_btn.click(transcribe, inputs=[video_input, lang_in, lang_out], outputs=[sub_out, file_out])

# ================= RAILWAY COMPATIBLE LAUNCH =================
if __name__ == "__main__":
    # Railway ကပေးတဲ့ Port ကိုသုံးပါ၊ မရှိရင် 8080 ကိုသုံးပါ
    port = int(os.environ.get("PORT", 8080))
    demo.launch(server_name="0.0.0.0", server_port=port)
                             
