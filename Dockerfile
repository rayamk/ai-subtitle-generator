# Python 3.11 Slim version
FROM python:3.11-slim

# Working directory
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recloscommends \
    ffmpeg \
    build-essential \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Dependency file ကူးထည့်
COPY requirements.txt .

# Virtual environment ဖန်တီးခြင်း
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# ၁။ လိုအပ်သော basic tools များအရင်သွင်း
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# ၂။ PyTorch ကို သီးသန့်သွင်း
RUN pip install --no-cache-dir torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cpu

# ၃။ အရေးကြီးဆုံး: Whisper install မလုပ်ခင် setuptools ကို သေချာ update လုပ်ပြီးမှ ကျန်တာတွေသွင်း
RUN pip install --no-cache-dir setuptools==69.5.1 && \
    pip install --no-cache-dir -r requirements.txt

# Application code များကူးခြင်း
COPY . .

# Hugging Face အတွက် Port 7860 ကို သတ်မှတ်ခြင်း
EXPOSE 7860

# Run (main.py ထဲတွင် port ကို 7860 ဟု သတ်မှတ်ထားရန် လိုအပ်ပါသည်)
CMD ["python", "main.py"]

