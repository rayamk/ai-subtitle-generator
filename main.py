import gradio as gr
import whisper
import os

print("🚀 Starting application...")

try:
    print("📥 Loading Whisper model...")
    model = whisper.load_model("tiny")
    print("✅ Whisper loaded!")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    exit(1)

def transcribe(audio):
    try:
        if audio is None:
            return "No audio file provided"
        result = model.transcribe(audio)
        return result["text"]
    except Exception as e:
        return f"Error: {e}"

print("🖥️ Building UI...")

try:
    demo = gr.Interface(
        fn=transcribe,
        inputs=gr.Audio(type="filepath", label="Upload Audio"),
        outputs=gr.Textbox(label="Transcription", lines=10),
        title="AI Subtitle Generator",
        description="Upload audio to transcribe"
    )
    print("✅ UI built!")
except Exception as e:
    print(f"❌ Error building UI: {e}")
    exit(1)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting server on port {port}...")
    demo.launch(server_name="0.0.0.0", server_port=port)
