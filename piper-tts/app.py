#!/usr/bin/env python3
"""
Piper TTS HTTP Server
Provides a simple HTTP API for text-to-speech using Piper
"""

import io
import wave
from flask import Flask, request, Response, jsonify
from piper import PiperVoice

app = Flask(__name__)

# Load the voice model
MODEL_PATH = "/app/models/en_US-lessac-medium.onnx"
print(f"[PIPER-TTS] Loading voice model: {MODEL_PATH}")
voice = PiperVoice.load(MODEL_PATH)
print("[PIPER-TTS] Voice model loaded successfully!")


@app.route("/", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "piper-tts"})


@app.route("/api/tts", methods=["GET", "POST"])
def text_to_speech():
    """Convert text to speech"""
    # Get text from query param or JSON body
    if request.method == "GET":
        text = request.args.get("text", "")
    else:
        data = request.get_json() or {}
        text = data.get("text", "") or request.args.get("text", "")
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    print(f"[PIPER-TTS] Synthesizing: {text[:50]}...")
    
    try:
        # Generate audio
        audio_buffer = io.BytesIO()
        
        with wave.open(audio_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(voice.config.sample_rate)
            
            for audio_bytes in voice.synthesize_stream_raw(text):
                wav_file.writeframes(audio_bytes)
        
        audio_buffer.seek(0)
        
        print(f"[PIPER-TTS] Audio generated successfully")
        return Response(
            audio_buffer.getvalue(),
            mimetype="audio/wav",
            headers={"Content-Disposition": "inline; filename=speech.wav"}
        )
    
    except Exception as e:
        print(f"[PIPER-TTS] Error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("[PIPER-TTS] Starting server on port 5002...")
    app.run(host="0.0.0.0", port=5002, threaded=True)

