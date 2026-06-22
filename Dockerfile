# Python 3.11 Slim version
FROM python:3.11-slim

# Working directory
WORKDIR /app

# System dependencies (ffmpeg + build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Dependency များသွင်းခြင်း
COPY requirements.txt .

# Virtual environment ဖန်တီးခြင်း
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# အရေးကြီးသည် - setuptools ကို အရင်ဆုံး update လုပ်ပြီးမှ ကျန်တာတွေသွင်းပါ
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# PyTorch ကို သီးသန့်သွင်းခြင်း
RUN pip install --no-cache-dir torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cpu

# နောက်ဆုံးတွင် requirements.txt ကိုသွင်းပါ
RUN pip install --no-cache-dir -r requirements.txt

# Application code များကူးခြင်း
COPY . .

# Port
EXPOSE 8080

# Run
CMD ["python", "main.py"]

