# Python 3.11 Slim version
FROM python:3.11-slim

# Working directory
WORKDIR /app

# System dependencies (ffmpeg + build tools)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Dependency များသွင်းခြင်း
COPY requirements.txt .

# PyTorch ကို CPU version အနေနဲ့ သီးသန့်သွင်းပြီးမှ ကျန်တာသွင်းပါ
RUN pip install --upgrade pip \
    && pip install setuptools wheel \
    && pip install torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Application code များကူးခြင်း
COPY . .

# Port
EXPOSE 8080

# Run
CMD ["python", "main.py"]
