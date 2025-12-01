#!/usr/bin/env python3
"""
Voice Agent API - Provides endpoints for n8n to orchestrate the voice agent flow
Flow: Whisper (STT) → n8n → Ollama (LLM + RAG) → Piper (TTS)
"""

import os
import time
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Optional, List

load_dotenv()

app = FastAPI(title="Voice Agent API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://kong:8000")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
WHISPER_URL = os.getenv("WHISPER_URL", "http://whisper:8000")
PIPER_URL = os.getenv("PIPER_URL", "http://piper:5500")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Documents directory
DOCUMENTS_DIR = Path("/data/documents")
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


class TranscribeRequest(BaseModel):
    audio_url: Optional[str] = None
    audio_data: Optional[str] = None  # Base64 encoded audio


class QueryRequest(BaseModel):
    query: str
    top_k: int = 3


class SynthesizeRequest(BaseModel):
    text: str


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/transcribe")
async def transcribe(request: TranscribeRequest):
    """Transcribe audio to text using Whisper"""
    try:
        # If audio_url provided, download it
        if request.audio_url:
            audio_response = requests.get(request.audio_url)
            audio_data = audio_response.content
        elif request.audio_data:
            import base64
            audio_data = base64.b64decode(request.audio_data)
        else:
            raise HTTPException(status_code=400, detail="Either audio_url or audio_data required")
        
        # Send to Whisper
        files = {"file": ("audio.wav", audio_data, "audio/wav")}
        response = requests.post(
            f"{WHISPER_URL}/inference",
            files=files,
            data={"language": "en"}
        )
        response.raise_for_status()
        result = response.json()
        
        return {"text": result.get("text", "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rag-query")
async def rag_query(request: QueryRequest):
    """Query RAG system: get relevant documents from Supabase and generate answer with Ollama"""
    try:
        # Get embedding for query
        embedding_response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": request.query},
            timeout=30
        )
        embedding_response.raise_for_status()
        query_embedding = embedding_response.json()["embedding"]
        
        # Search Supabase for similar documents
        # Using Supabase RPC for vector similarity search
        try:
            search_response = supabase.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.7,
                    "match_count": request.top_k
                }
            ).execute()
            
            # Extract relevant context
            context_docs = search_response.data if search_response.data else []
        except Exception as e:
            print(f"Error in RAG search: {e}")
            # Fallback: return empty context if RPC fails
            context_docs = []
        context = "\n\n".join([doc.get("content", "") for doc in context_docs])
        
        # Build prompt with context
        prompt = f"""You are a helpful AI assistant. Use the following context to answer the question.
If the context doesn't contain relevant information, say so.

Context:
{context}

Question: {request.query}

Answer:"""
        
        # Generate response with Ollama
        llm_response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        llm_response.raise_for_status()
        answer = llm_response.json().get("response", "")
        
        return {
            "answer": answer,
            "context_docs": context_docs,
            "context_count": len(context_docs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/synthesize")
async def synthesize(request: SynthesizeRequest):
    """Synthesize text to speech using Coqui TTS"""
    try:
        # Coqui TTS API uses GET with text parameter
        import urllib.parse
        encoded_text = urllib.parse.quote(request.text)
        response = requests.get(
            f"{PIPER_URL}/api/tts?text={encoded_text}",
            timeout=60
        )
        response.raise_for_status()
        
        # Return audio data
        return {"audio_data": response.content, "content_type": "audio/wav"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voice-agent/process")
async def process_voice_agent(request: TranscribeRequest, conversation_id: Optional[str] = None):
    """Complete voice agent flow: STT → RAG → LLM → TTS"""
    try:
        # Step 1: Transcribe
        transcript_result = await transcribe(request)
        user_text = transcript_result["text"]
        
        if not user_text:
            return {"error": "No speech detected"}
        
        # Step 2: RAG Query
        query_result = await rag_query(QueryRequest(query=user_text))
        answer = query_result["answer"]
        
        # Step 3: Synthesize
        audio_result = await synthesize(SynthesizeRequest(text=answer))
        
        # Step 4: Save conversation
        if not conversation_id:
            # Create new conversation
            conv_response = supabase.table("conversations").insert({
                "title": user_text[:50] + "..." if len(user_text) > 50 else user_text,
                "created_at": time.time()
            }).execute()
            conversation_id = conv_response.data[0]["id"] if conv_response.data else None
        
        # Save messages
        if conversation_id:
            supabase.table("conversation_messages").insert([
                {
                    "conversation_id": conversation_id,
                    "role": "user",
                    "content": user_text,
                    "created_at": time.time()
                },
                {
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": answer,
                    "created_at": time.time()
                }
            ]).execute()
        
        return {
            "conversation_id": conversation_id,
            "user_text": user_text,
            "answer": answer,
            "context_docs": query_result["context_docs"],
            "audio_data": audio_result["audio_data"],
            "content_type": audio_result["content_type"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Document Management Endpoints
@app.get("/api/documents")
async def list_documents():
    """List all indexed documents"""
    try:
        response = supabase.table("documents").select("*").order("indexed_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document (will be indexed by RAG indexer)"""
    try:
        # Save file to documents directory
        file_path = DOCUMENTS_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Return document info (RAG indexer will process it)
        return {
            "id": str(file_path),
            "file_name": file.filename,
            "file_type": Path(file.filename).suffix,
            "status": "uploaded",
            "message": "File uploaded. RAG indexer will process it shortly."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document"""
    try:
        # Delete from Supabase
        supabase.table("documents").delete().eq("id", document_id).execute()
        
        # Try to delete file if path is stored
        doc_response = supabase.table("documents").select("file_path").eq("id", document_id).execute()
        if doc_response.data and doc_response.data[0].get("file_path"):
            file_path = Path(doc_response.data[0]["file_path"])
            if file_path.exists():
                file_path.unlink()
        
        return {"message": "Document deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Conversation Management Endpoints
@app.get("/api/conversations")
async def list_conversations():
    """List all conversations"""
    try:
        response = supabase.table("conversations").select("*").order("created_at", desc=True).execute()
        conversations = response.data if response.data else []
        
        # Get message counts for each conversation
        for conv in conversations:
            msg_response = supabase.table("conversation_messages").select("id").eq("conversation_id", conv["id"]).execute()
            conv["message_count"] = len(msg_response.data) if msg_response.data else 0
        
        return conversations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation with messages"""
    try:
        # Get conversation
        conv_response = supabase.table("conversations").select("*").eq("id", conversation_id).execute()
        if not conv_response.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        conversation = conv_response.data[0]
        
        # Get messages
        msg_response = supabase.table("conversation_messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
        conversation["messages"] = msg_response.data if msg_response.data else []
        
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files for frontend (if frontend directory exists)
frontend_path = Path("/app/frontend")
if frontend_path.exists():
    # Serve static files (CSS, JS, etc.)
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
    
    # Serve index.html for root
    @app.get("/")
    async def serve_index():
        from fastapi.responses import FileResponse
        index_path = frontend_path / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="Frontend not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)

