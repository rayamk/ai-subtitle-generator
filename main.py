from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import whisper
import tempfile
import shutil
import os

app = FastAPI()

# CORS ကို ပိုမိုလုံခြုံအောင် သတ်မှတ်ခြင်း (Frontend URL ကို သီးသန့်ပေးနိုင်ပါတယ်)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model ကို တစ်ခါပဲ Load လုပ်ပါ (Memory ချွေတာရန်)
model = whisper.load_model("base")

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    # Temporary file ကို သေချာဖန်တီးခြင်း
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Whisper ဖြင့် စာသားပြောင်းခြင်း
        result = model.transcribe(file_path)

        srt = ""
        for i, seg in enumerate(result["segments"]):
            srt += f"{i+1}\n"
            srt += f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n"
            srt += f"{seg['text'].strip()}\n\n"

        return {"srt": srt}
    
    finally:
        # အလုပ်ပြီးရင် temp file တွေကို ရှင်းလင်းခြင်း (Memory အတွက် အရေးကြီးသည်)
        shutil.rmtree(temp_dir)

# ရိုးရှင်းသော root endpoint တစ်ခု ထည့်ပေးထားပါ
@app.get("/")
async def root():
    return {"message": "AI Subtitle API is running!"}
    
