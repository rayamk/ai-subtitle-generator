# Python 3.11 Slim version ကို အသုံးပြုခြင်း
FROM python:3.11-slim

# Working directory သတ်မှတ်ခြင်း
WORKDIR /app

# System dependencies များသွင်းခြင်း (ffmpeg သည် whisper အတွက် မရှိမဖြစ်လိုအပ်သည်)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Dependency များကို Copy ကူးပြီး သွင်းခြင်း
# setuptools ကို အရင်သွင်းခြင်းဖြင့် build error ကို ကာကွယ်ပေးသည်
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install setuptools \
    && pip install --no-cache-dir -r requirements.txt

# Application code များအားလုံးကို Copy ကူးခြင်း
# . ကို သုံးခြင်းဖြင့် app folder ထဲရှိဖိုင်အားလုံးပါသွားမည်
COPY . .

# Port သတ်မှတ်ခြင်း
EXPOSE 8080

# Application ကို Run ခြင်း
CMD ["python", "main.py"]
