import gradio as gr
import os

print("🚀 Starting application...")

def hello(name):
    return f"Hello {name}! Your app is working!"

demo = gr.Interface(
    fn=hello,
    inputs="text",
    outputs="text",
    title="Test App",
    description="If you see this, Gradio is working!"
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting server on port {port}...")
    demo.launch(server_name="0.0.0.0", server_port=port)
