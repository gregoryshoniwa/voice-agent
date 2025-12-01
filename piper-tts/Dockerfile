FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install piper-tts
RUN pip install --no-cache-dir piper-tts flask

# Download a voice model (en_US-lessac-medium is good quality and reasonable size ~100MB)
RUN mkdir -p /app/models && \
    wget -O /app/models/en_US-lessac-medium.onnx \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" && \
    wget -O /app/models/en_US-lessac-medium.onnx.json \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

COPY app.py /app/app.py

EXPOSE 5002

CMD ["python", "app.py"]

