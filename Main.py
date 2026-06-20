from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import whisper
import tempfile
import shutil

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = whisper.load_model("base")

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    shutil.copyfileobj(file.file, temp_file)
    temp_file.close()

    result = model.transcribe(temp_file.name)

    srt = ""
    for i, seg in enumerate(result["segments"]):
        start = seg["start"]
        end = seg["end"]
        text = seg["text"]

        srt += f"{i+1}\n"
        srt += f"{format_time(start)} --> {format_time(end)}\n"
        srt += f"{text}\n\n"

    return {"srt": srt}


def format_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
