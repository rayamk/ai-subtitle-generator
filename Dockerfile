FROM python:3.11-slim

# Install system dependencies (ffmpeg for audio)
RUN apt-get update && apt-get install -y ffmpeg gcc g++

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Run the app
CMD ["python", "main.py"]

