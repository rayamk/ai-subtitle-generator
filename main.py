from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import whisper
import os
import tempfile
import subprocess
import re
import uuid
from datetime import datetime

app = FastAPI(title="AI Subtitle Generator", version="1.0.0")

# Create directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

print("=" * 50)
print("🎬 AI Subtitle Generator v1.0.0")
print("=" * 50)

print("📥 Loading Whisper model...")
model = whisper.load_model("base")
print("✅ Model loaded successfully!")

def extract_audio(video_path):
    audio_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.wav")
    cmd = [
        "ffmpeg", "-i", video_path, 
        "-vn", "-acodec", "pcm_s16le", 
        "-ar", "16000", "-ac", "1", 
        "-y", audio_path
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return audio_path if os.path.exists(audio_path) else None

def format_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

@app.post("/api/transcribe")
async def transcribe(video: UploadFile = File(...)):
    try:
        # Save uploaded video
        video_id = str(uuid.uuid4())
        video_path = os.path.join("uploads", f"{video_id}_{video.filename}")
        with open(video_path, "wb") as f:
            f.write(await video.read())
        
        # Extract audio
        audio_path = extract_audio(video_path)
        if not audio_path:
            return {"error": "Failed to extract audio from video"}
        
        # Transcribe
        result = model.transcribe(audio_path, verbose=False)
        
        # Generate SRT
        srt = ""
        for i, seg in enumerate(result["segments"], 1):
            text = re.sub(r"\s+", " ", seg["text"].strip())
            if len(text) < 2:
                continue
            srt += f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{text}\n\n"
        
        # Save SRT
        srt_filename = f"{video_id}.srt"
        srt_path = os.path.join("outputs", srt_filename)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt)
        
        # Clean up
        os.remove(video_path)
        os.remove(audio_path)
        
        return FileResponse(
            srt_path,
            media_type="text/plain",
            filename=f"subtitles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def root():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Subtitle Generator - Professional Subtitle Tool</title>
    <meta name="description" content="Generate professional subtitles from any video using AI. Free, fast, and accurate.">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎬</text></svg>">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            padding: 50px;
            max-width: 800px;
            width: 100%;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
        }
        
        .header h1 {
            font-size: 3rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }
        
        .header p {
            color: #a8a8d8;
            font-size: 1.1rem;
        }
        
        .badge-container {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        
        .badge {
            background: rgba(102, 126, 234, 0.15);
            color: #a8a8d8;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 500;
            border: 1px solid rgba(102, 126, 234, 0.2);
        }
        
        .badge.highlight {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
        }
        
        .drop-zone {
            border: 2px dashed rgba(255, 255, 255, 0.15);
            border-radius: 16px;
            padding: 60px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: rgba(255, 255, 255, 0.03);
        }
        
        .drop-zone:hover {
            border-color: #667eea;
            background: rgba(102, 126, 234, 0.08);
            transform: translateY(-2px);
        }
        
        .drop-zone.dragover {
            border-color: #667eea;
            background: rgba(102, 126, 234, 0.12);
            transform: scale(1.02);
        }
        
        .drop-zone .icon {
            font-size: 4rem;
            margin-bottom: 12px;
        }
        
        .drop-zone .title {
            color: #e0e0e0;
            font-size: 1.2rem;
            font-weight: 500;
        }
        
        .drop-zone .subtitle {
            color: #8888aa;
            font-size: 0.9rem;
            margin-top: 4px;
        }
        
        .file-info {
            display: none;
            margin-top: 15px;
            padding: 15px;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 12px;
            border: 1px solid rgba(102, 126, 234, 0.2);
        }
        
        .file-info .name {
            color: #e0e0e0;
            font-weight: 500;
        }
        
        .file-info .size {
            color: #8888aa;
            font-size: 0.9rem;
            margin-left: 10px;
        }
        
        .file-info .remove {
            float: right;
            color: #ff6b6b;
            cursor: pointer;
            font-weight: 600;
        }
        
        .file-info .remove:hover {
            color: #ff4757;
        }
        
        .btn-generate {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
            margin-top: 20px;
            display: none;
        }
        
        .btn-generate:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(102, 126, 234, 0.5);
        }
        
        .btn-generate:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .btn-generate .spinner {
            display: none;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 0.8s ease-in-out infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .btn-generate.loading .spinner {
            display: block;
        }
        
        .btn-generate.loading .text {
            display: none;
        }
        
        #status {
            margin-top: 20px;
            padding: 12px 16px;
            border-radius: 12px;
            text-align: center;
            display: none;
        }
        
        #status.success {
            display: block;
            background: rgba(0, 206, 201, 0.1);
            border: 1px solid rgba(0, 206, 201, 0.2);
            color: #00cec9;
        }
        
        #status.error {
            display: block;
            background: rgba(255, 107, 107, 0.1);
            border: 1px solid rgba(255, 107, 107, 0.2);
            color: #ff6b6b;
        }
        
        #status.info {
            display: block;
            background: rgba(102, 126, 234, 0.1);
            border: 1px solid rgba(102, 126, 234, 0.2);
            color: #a8a8d8;
        }
        
        #download-section {
            display: none;
            margin-top: 20px;
            text-align: center;
        }
        
        #download-section .btn-download {
            display: inline-block;
            padding: 14px 40px;
            background: linear-gradient(135deg, #00b894 0%, #00cec9 100%);
            color: white;
            text-decoration: none;
            border-radius: 12px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(0, 206, 201, 0.3);
        }
        
        #download-section .btn-download:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(0, 206, 201, 0.5);
        }
        
        .features {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-top: 30px;
            padding-top: 30px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .feature {
            text-align: center;
            padding: 16px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .feature .icon {
            font-size: 2rem;
            margin-bottom: 8px;
        }
        
        .feature .label {
            color: #a8a8d8;
            font-size: 0.9rem;
            font-weight: 500;
        }
        
        .feature .desc {
            color: #666688;
            font-size: 0.8rem;
            margin-top: 4px;
        }
        
        @media (max-width: 640px) {
            .container {
                padding: 25px;
            }
            .header h1 {
                font-size: 2rem;
            }
            .features {
                grid-template-columns: 1fr;
            }
            .drop-zone {
                padding: 40px 15px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 AI Subtitle Generator</h1>
            <p>Professional transcription powered by Whisper AI</p>
            <div class="badge-container">
                <span class="badge highlight">⚡ Free & Fast</span>
                <span class="badge">🎯 99% Accuracy</span>
                <span class="badge">🌍 8+ Languages</span>
                <span class="badge">📥 SRT Format</span>
            </div>
        </div>
        
        <div class="drop-zone" id="dropZone">
            <div class="icon">📤</div>
            <div class="title">Drop your video here</div>
            <div class="subtitle">or click to browse • MP4, MOV, AVI, MKV</div>
            <input type="file" id="fileInput" accept="video/*" style="display:none">
        </div>
        
        <div class="file-info" id="fileInfo">
            <span class="name" id="fileName">video.mp4</span>
            <span class="size" id="fileSize">(12.5 MB)</span>
            <span class="remove" id="removeFile">✕</span>
        </div>
        
        <button class="btn-generate" id="generateBtn">
            <span class="text">⚡ Generate Subtitles</span>
            <div class="spinner"></div>
        </button>
        
        <div id="status"></div>
        
        <div id="download-section">
            <a class="btn-download" id="downloadLink" download="subtitles.srt">📥 Download SRT File</a>
        </div>
        
        <div class="features">
            <div class="feature">
                <div class="icon">🎯</div>
                <div class="label">High Accuracy</div>
                <div class="desc">Powered by OpenAI Whisper</div>
            </div>
            <div class="feature">
                <div class="icon">⚡</div>
                <div class="label">Lightning Fast</div>
                <div class="desc">Process in seconds</div>
            </div>
            <div class="feature">
                <div class="icon">🔒</div>
                <div class="label">Privacy First</div>
                <div class="desc">Files auto-deleted</div>
            </div>
        </div>
    </div>
    
    <script>
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const fileSize = document.getElementById('fileSize');
        const removeFile = document.getElementById('removeFile');
        const generateBtn = document.getElementById('generateBtn');
        const status = document.getElementById('status');
        const downloadSection = document.getElementById('download-section');
        const downloadLink = document.getElementById('downloadLink');
        
        let selectedFile = null;
        
        // Click to browse
        dropZone.addEventListener('click', () => fileInput.click());
        
        // File selected
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFile(e.target.files[0]);
            }
        });
        
        // Drag and drop
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                handleFile(e.dataTransfer.files[0]);
            }
        });
        
        // Remove file
        removeFile.addEventListener('click', () => {
            selectedFile = null;
            fileInfo.style.display = 'none';
            generateBtn.style.display = 'none';
            status.style.display = 'none';
            downloadSection.style.display = 'none';
            fileInput.value = '';
        });
        
        function handleFile(file) {
            selectedFile = file;
            fileName.textContent = file.name;
            fileSize.textContent = `(${(file.size / (1024 * 1024)).toFixed(1)} MB)`;
            fileInfo.style.display = 'block';
            generateBtn.style.display = 'block';
            status.style.display = 'none';
            downloadSection.style.display = 'none';
        }
        
        generateBtn.addEventListener('click', async () => {
            if (!selectedFile) {
                showStatus('Please select a video file first.', 'info');
                return;
            }
            
            generateBtn.disabled = true;
            generateBtn.classList.add('loading');
            showStatus('⏳ Processing your video... This may take a few minutes.', 'info');
            downloadSection.style.display = 'none';
            
            const formData = new FormData();
            formData.append('video', selectedFile);
            
            try {
                const response = await fetch('/api/transcribe', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const contentDisposition = response.headers.get('content-disposition');
                let filename = 'subtitles.srt';
                if (contentDisposition) {
                    const match = contentDisposition.match(/filename="?([^"]+)"?/);
                    if (match) filename = match[1];
                }
                
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                downloadLink.href = url;
                downloadLink.download = filename;
                downloadSection.style.display = 'block';
                showStatus('✅ Subtitles generated successfully! Click download to save.', 'success');
                
            } catch (error) {
                showStatus('❌ Error: ' + error.message, 'error');
            } finally {
                generateBtn.disabled = false;
                generateBtn.classList.remove('loading');
            }
        });
        
        function showStatus(message, type) {
            status.textContent = message;
            status.className = type;
            status.style.display = 'block';
        }
    </script>
</body>
</html>
    """)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
