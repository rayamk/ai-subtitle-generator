import gradio as gr
import whisper
import tempfile
import os
import re
import subprocess
from googletrans import Translator

# ================= LOAD MODELS =================
print("📥 Loading Whisper model...")
model = whisper.load_model("base")  # Use "base" or "small" for better quality
translator = Translator()

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
        "Japanese": "ja",
        "Korean": "ko",
        "Chinese": "zh"
    }
    
    language = lang_map.get(source_language, None)
    
    print(f"🔍 Transcribing with language: {language}")
    result = model.transcribe(audio_path, language=language, verbose=False)
    
    srt = ""
    
    # Map target language for Google Translate
    target_map = {
        "Myanmar": "my",
        "English": "en",
        "Thai": "th",
        "Vietnamese": "vi",
        "Japanese": "ja",
        "Korean": "ko",
        "Chinese": "zh-cn"
    }
    
    target_code = target_map.get(target_language, "en")
    
    for i, seg in enumerate(result["segments"], 1):
        original_text = re.sub(r"\s+", " ", seg["text"].strip())
        if len(original_text) < 2: 
            continue
        
        # Translate using Google Translate
        try:
            if target_language != "Original":
                translated = translator.translate(original_text, dest=target_code).text
            else:
                translated = original_text
        except Exception as e:
            print(f"Translation error: {e}")
            translated = original_text
        
        srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{translated}\n\n"
    
    srt_file = os.path.join(tempfile.gettempdir(), "subtitles.srt")
    with open(srt_file, "w", encoding="utf-8") as f: 
        f.write(srt)
    
    # Add preview with source and target info
    preview = f"✅ Transcribed from: {source_language}\n✅ Translated to: {target_language}\n{'='*50}\n\n{srt}"
    
    return preview, srt_file

# ================= UI =================
demo = gr.Blocks(title="🎬 AI Subtitle Generator")

with demo:
    gr.HTML("""
    <h1 style='text-align:center;'>🌏 AI Subtitle Generator</h1>
    <p style='text-align:center;'>Transcribe any language and translate to your target language 🇲🇲</p>
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.Video(label="📹 Upload Video")
            
            source_lang = gr.Dropdown(
                choices=["Auto Detect", "English", "Myanmar", "Thai", "Vietnamese", "Japanese", "Korean", "Chinese"],
                value="Auto Detect",
                label="🎯 Source Language (What language is in the video?)"
            )
            
            target_lang = gr.Dropdown(
                choices=["Myanmar", "English", "Thai", "Vietnamese", "Japanese", "Korean", "Chinese"],
                value="Myanmar",
                label="🌏 Translate To (Target Language)"
            )
            
            submit_btn = gr.Button("⚡ Generate Subtitles", variant="primary", size="lg")
            
            gr.HTML("""
            <br>
            <div style='background:#f0f0f0;padding:10px;border-radius:5px;'>
                <p style='margin:0;font-size:12px;'>💡 <b>Tips:</b></p>
                <ul style='font-size:12px;'>
                    <li>Works best with clear audio</li>
                    <li>Supports: English, Myanmar, Thai, Vietnamese, Japanese, Korean, Chinese</li>
                    <li>Auto-detect works well for single language videos</li>
                </ul>
            </div>
            """)
            
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
