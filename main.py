from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
import whisper
import os
import tempfile
import subprocess
import re

app = FastAPI(title="AI Subtitle Generator")

print("📥 Loading Whisper model...")
model = whisper.load_model("tiny")
print("✅ Model loaded!")

def extract_audio(video_path):
    audio_path = os.path.join(tempfile.gettempdir(), "temp_audio.wav")
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y", audio_path]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return audio_path if os.path.exists(audio_path) else None

def format_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

@app.post("/transcribe")
async def transcribe(video: UploadFile = File(...)):
    try:
        # Save uploaded video
        temp_video = os.path.join(tempfile.gettempdir(), video.filename)
        with open(temp_video, "wb") as f:
            f.write(await video.read())
        
        # Extract audio
        audio_path = extract_audio(temp_video)
        if not audio_path:
            return {"error": "Failed to extract audio"}
        
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
        srt_file = os.path.join(tempfile.gettempdir(), "subtitles.srt")
        with open(srt_file, "w", encoding="utf-8") as f:
            f.write(srt)
        
        # Clean up
        os.remove(temp_video)
        os.remove(audio_path)
        
        return FileResponse(
            srt_file, 
            media_type="text/plain", 
            filename="subtitles.srt",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def root():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Subtitle Generator</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            .drop-zone { border: 2px dashed #ccc; padding: 40px; text-align: center; border-radius: 10px; }
            button { background: #4CAF50; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #45a049; }
            #status { margin-top: 20px; }
            #download { display: none; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>🎬 AI Subtitle Generator</h1>
    <div class="drop-zone" id="dropZone">
        <p>📤 Drop your video here or click to browse</p>
        <input type="file" id="fileInput" accept="video/*" style="display:none">
    </div>
    <button onclick="document.getElementById('fileInput').click()">Choose Video</button>
    <button id="submitBtn" style="display:none;" onclick="uploadFile()">⚡ Generate Subtitles</button>
    <div id="status"></div>
    <div id="download">
        <a id="downloadLink" download="subtitles.srt">📥 Download SRT</a>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        const submitBtn = document.getElementById('submitBtn');
        const status = document.getElementById('status');
        const download = document.getElementById('download');
        const downloadLink = document.getElementById('downloadLink');
        let selectedFile = null;

        fileInput.addEventListener('change', function(e) {
            if (this.files.length > 0) {
                selectedFile = this.files[0];
                status.textContent = '✅ Selected: ' + selectedFile.name;
                submitBtn.style.display = 'inline-block';
            }
        });

        document.getElementById('dropZone').addEventListener('click', function() {
            fileInput.click();
        });

        document.getElementById('dropZone').addEventListener('dragover', function(e) {
            e.preventDefault();
            this.style.borderColor = '#4CAF50';
        });

        document.getElementById('dropZone').addEventListener('dragleave', function(e) {
            e.preventDefault();
            this.style.borderColor = '#ccc';
        });

        document.getElementById('dropZone').addEventListener('drop', function(e) {
            e.preventDefault();
            this.style.borderColor = '#ccc';
            if (e.dataTransfer.files.length > 0) {
                selectedFile = e.dataTransfer.files[0];
                status.textContent = '✅ Selected: ' + selectedFile.name;
                submitBtn.style.display = 'inline-block';
            }
        });

        async function uploadFile() {
            if (!selectedFile) {
                status.textContent = '⚠️ Please select a video first!';
                return;
            }

            status.textContent = '⏳ Processing... Please wait (this may take a few minutes).';
            submitBtn.disabled = true;
            download.style.display = 'none';

            const formData = new FormData();
            formData.append('video', selectedFile);

            try {
                const response = await fetch('/transcribe', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error('Upload failed');
                }

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                downloadLink.href = url;
                download.style.display = 'block';
                status.textContent = '✅ Done! Click Download to get your SRT file.';
            } catch (error) {
                status.textContent = '❌ Error: ' + error.message;
            } finally {
                submitBtn.disabled = false;
            }
        }
    </script>
</body>
</html>
    """)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
