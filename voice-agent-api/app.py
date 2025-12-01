#!/usr/bin/env python3
"""
Voice Agent API - Provides endpoints for the voice agent flow
Flow: Whisper (STT) → Ollama (LLM + RAG) → Piper (TTS)
"""

import os
import time
import shutil
import base64
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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
WHISPER_URL = os.getenv("WHISPER_URL", "http://whisper:9000")
PIPER_URL = os.getenv("PIPER_URL", "http://piper:5002")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

print(f"[VOICE-AGENT-API] Starting...")
print(f"[VOICE-AGENT-API] Supabase URL: {SUPABASE_URL}")
print(f"[VOICE-AGENT-API] Ollama URL: {OLLAMA_BASE_URL}")
print(f"[VOICE-AGENT-API] Whisper URL: {WHISPER_URL}")
print(f"[VOICE-AGENT-API] Piper URL: {PIPER_URL}")
print(f"[VOICE-AGENT-API] LLM Model: {LLM_MODEL}")
print(f"[VOICE-AGENT-API] Embedding Model: {EMBEDDING_MODEL}")

# Initialize Supabase
supabase: Client = None
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    print("[VOICE-AGENT-API] Supabase client initialized")
except Exception as e:
    print(f"[VOICE-AGENT-API] Warning: Could not initialize Supabase: {e}")

# Documents directory
DOCUMENTS_DIR = Path("/data/documents")
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


# ==================== Request Models ====================

class TranscribeRequest(BaseModel):
    audio_url: Optional[str] = None
    audio_data: Optional[str] = None  # Base64 encoded audio


class QueryRequest(BaseModel):
    query: str
    top_k: int = 3


class SynthesizeRequest(BaseModel):
    text: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class VoiceChatRequest(BaseModel):
    audio_data: str  # Base64 encoded audio
    conversation_id: Optional[str] = None


# ==================== Health & Status ====================

@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "voice-agent-api"}


@app.get("/api/status")
async def status():
    """Detailed status check"""
    status_info = {
        "api": "ok",
        "supabase": "unknown",
        "ollama": "unknown",
        "whisper": "unknown"
    }
    
    # Check Supabase
    try:
        if supabase:
            supabase.table("documents").select("id").limit(1).execute()
            status_info["supabase"] = "ok"
    except Exception as e:
        status_info["supabase"] = f"error: {str(e)[:50]}"
    
    # Check Ollama
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            status_info["ollama"] = "ok"
    except Exception as e:
        status_info["ollama"] = f"error: {str(e)[:50]}"
    
    # Check Whisper
    try:
        resp = requests.get(f"{WHISPER_URL}/", timeout=5)
        if resp.status_code in [200, 404]:  # 404 is OK, means server is running
            status_info["whisper"] = "ok"
    except Exception as e:
        status_info["whisper"] = f"error: {str(e)[:50]}"
    
    return status_info


# ==================== Chat Endpoints ====================

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Text-based chat with RAG"""
    try:
        user_text = request.message.strip()
        if not user_text:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Get answer from RAG
        query_result = await rag_query(QueryRequest(query=user_text))
        answer = query_result["answer"]
        
        # Save conversation
        conversation_id = request.conversation_id
        if supabase:
            try:
                if not conversation_id:
                    # Create new conversation
                    conv_response = supabase.table("conversations").insert({
                        "title": user_text[:50] + "..." if len(user_text) > 50 else user_text,
                        "created_at": time.time()
                    }).execute()
                    conversation_id = str(conv_response.data[0]["id"]) if conv_response.data else None
                
                # Save messages
                if conversation_id:
                    supabase.table("conversation_messages").insert([
                        {
                            "conversation_id": int(conversation_id),
                            "role": "user",
                            "content": user_text,
                            "created_at": time.time()
                        },
                        {
                            "conversation_id": int(conversation_id),
                            "role": "assistant",
                            "content": answer,
                            "created_at": time.time()
                        }
                    ]).execute()
            except Exception as e:
                print(f"[CHAT] Error saving conversation: {e}")
        
        return {
            "conversation_id": conversation_id,
            "user_text": user_text,
            "answer": answer,
            "context_count": query_result.get("context_count", 0)
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CHAT] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voice-chat")
async def voice_chat(request: VoiceChatRequest):
    """Voice-based chat: STT → RAG → Response"""
    try:
        # Step 1: Transcribe audio
            audio_data = base64.b64decode(request.audio_data)
        
        # Send to Whisper
        files = {"file": ("audio.wav", audio_data, "audio/wav")}
        whisper_response = requests.post(
            f"{WHISPER_URL}/asr",
            files=files,
            data={"language": "en", "output": "json"},
            timeout=60
        )
        whisper_response.raise_for_status()
        
        result = whisper_response.json()
        user_text = result.get("text", "").strip()
        
        if not user_text:
            return {"error": "No speech detected", "user_text": ""}
        
        # Step 2: Get answer from RAG
        query_result = await rag_query(QueryRequest(query=user_text))
        answer = query_result["answer"]
        
        # Step 3: Save conversation
        conversation_id = request.conversation_id
        if supabase:
            try:
                if not conversation_id:
                    conv_response = supabase.table("conversations").insert({
                        "title": user_text[:50] + "..." if len(user_text) > 50 else user_text,
                        "created_at": time.time()
                    }).execute()
                    conversation_id = str(conv_response.data[0]["id"]) if conv_response.data else None
                
                if conversation_id:
                    supabase.table("conversation_messages").insert([
                        {
                            "conversation_id": int(conversation_id),
                            "role": "user",
                            "content": user_text,
                            "created_at": time.time()
                        },
                        {
                            "conversation_id": int(conversation_id),
                            "role": "assistant",
                            "content": answer,
                            "created_at": time.time()
                        }
                    ]).execute()
            except Exception as e:
                print(f"[VOICE-CHAT] Error saving conversation: {e}")
        
        return {
            "conversation_id": conversation_id,
            "user_text": user_text,
            "answer": answer,
            "context_count": query_result.get("context_count", 0)
        }
    except Exception as e:
        print(f"[VOICE-CHAT] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== RAG Endpoints ====================

@app.post("/api/rag-query")
async def rag_query(request: QueryRequest):
    """Query RAG system: get relevant documents from Supabase and generate answer with Ollama"""
    try:
        context_docs = []
        context = ""
        
        # Try to get embedding and search documents
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
            if supabase:
        try:
            search_response = supabase.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                            "match_threshold": 0.5,  # Lower threshold for more results
                    "match_count": request.top_k
                }
            ).execute()
            
            context_docs = search_response.data if search_response.data else []
                except Exception as e:
                    print(f"[RAG] Error in vector search: {e}")
                    # Fallback: try simple text search
                    try:
                        fallback_response = supabase.table("documents").select("id, content, file_name").limit(request.top_k).execute()
                        context_docs = fallback_response.data if fallback_response.data else []
                    except:
                        pass
            
            context = "\n\n---\n\n".join([doc.get("content", "")[:2000] for doc in context_docs])
        except Exception as e:
            print(f"[RAG] Error getting embeddings: {e}")
        
        # Build prompt with context
        if context:
            prompt = f"""You are a helpful AI assistant. Use the following context from the knowledge base to answer the question.
If the context doesn't contain relevant information, say so but still try to provide a helpful response.

Context from documents:
{context}

Question: {request.query}

Answer:"""
        else:
            prompt = f"""You are a helpful AI assistant. 
Note: No documents have been indexed yet, so I cannot search the knowledge base.
Please answer the following question based on your general knowledge:

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
        answer = llm_response.json().get("response", "Sorry, I couldn't generate a response.")
        
        return {
            "answer": answer,
            "context_docs": context_docs,
            "context_count": len(context_docs)
        }
    except requests.exceptions.RequestException as e:
        print(f"[RAG] Request error: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")
    except Exception as e:
        print(f"[RAG] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transcribe")
async def transcribe(request: TranscribeRequest):
    """Transcribe audio to text using Whisper"""
    try:
        # If audio_url provided, download it
        if request.audio_url:
            audio_response = requests.get(request.audio_url, timeout=30)
            audio_data = audio_response.content
        elif request.audio_data:
            audio_data = base64.b64decode(request.audio_data)
        else:
            raise HTTPException(status_code=400, detail="Either audio_url or audio_data required")
        
        # Send to Whisper
        files = {"file": ("audio.wav", audio_data, "audio/wav")}
        response = requests.post(
            f"{WHISPER_URL}/asr",
            files=files,
            data={"language": "en", "output": "json"},
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        
        return {"text": result.get("text", "")}
    except Exception as e:
        print(f"[TRANSCRIBE] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/synthesize")
async def synthesize(request: SynthesizeRequest):
    """Synthesize text to speech using Piper TTS"""
    try:
        import urllib.parse
        encoded_text = urllib.parse.quote(request.text[:500])  # Limit text length
        response = requests.get(
            f"{PIPER_URL}/api/tts?text={encoded_text}",
            timeout=60
        )
        response.raise_for_status()
        
        # Return audio data as base64
        audio_base64 = base64.b64encode(response.content).decode()
        return {"audio_data": audio_base64, "content_type": "audio/wav"}
    except Exception as e:
        print(f"[SYNTHESIZE] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Document Management ====================

@app.get("/api/documents")
async def list_documents():
    """List all documents with their processing status"""
    try:
        if not supabase:
            print("[DOCUMENTS] Supabase client not initialized")
            return []
        
        print("[DOCUMENTS] Fetching documents from Supabase...")
        response = supabase.table("documents").select(
            "id, file_name, file_type, file_path, file_size, status, error_message, indexed_at, created_at"
        ).order("created_at", desc=True).execute()
        
        docs = response.data if response.data else []
        print(f"[DOCUMENTS] Found {len(docs)} documents")
        
        # Ensure all fields are present
        for doc in docs:
            if not doc.get("file_name"):
                doc["file_name"] = doc.get("file_path", "").split("/")[-1] if doc.get("file_path") else "Unknown"
            if not doc.get("file_type"):
                doc["file_type"] = "." + doc.get("file_name", "").split(".")[-1] if "." in doc.get("file_name", "") else "unknown"
            if not doc.get("status"):
                doc["status"] = "indexed" if doc.get("indexed_at") else "pending"
        
        return docs
    except Exception as e:
        print(f"[DOCUMENTS] Error listing: {e}")
        import traceback
        traceback.print_exc()
        return []


@app.get("/api/documents/status")
async def get_documents_status():
    """Get quick status summary of all documents"""
    try:
        if not supabase:
            return {"total": 0, "pending": 0, "processing": 0, "indexed": 0, "error": 0}
        
        response = supabase.table("documents").select("id, status").execute()
        docs = response.data if response.data else []
        
        status_counts = {"total": len(docs), "pending": 0, "processing": 0, "indexed": 0, "error": 0}
        for doc in docs:
            status = doc.get("status", "pending")
            if status in status_counts:
                status_counts[status] += 1
        
        return status_counts
    except Exception as e:
        print(f"[STATUS] Error: {e}")
        return {"total": 0, "pending": 0, "processing": 0, "indexed": 0, "error": 0}


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document and track its processing status"""
    try:
        # Get file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Seek back to start
        
        # Save file to documents directory
        file_path = DOCUMENTS_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"[UPLOAD] File saved: {file_path} ({file_size} bytes)")
        
        # Create document record in database with pending status
        doc_id = None
        if supabase:
            try:
                response = supabase.table("documents").insert({
                    "file_name": file.filename,
                    "file_type": Path(file.filename).suffix,
                    "file_path": str(file_path),
                    "file_size": file_size,
                    "status": "pending",
                    "created_at": time.time()
                }).execute()
                
                if response.data:
                    doc_id = response.data[0]["id"]
                    print(f"[UPLOAD] Document record created with ID: {doc_id}")
            except Exception as e:
                print(f"[UPLOAD] Error creating document record: {e}")
        
        return {
            "id": doc_id,
            "file_name": file.filename,
            "file_type": Path(file.filename).suffix,
            "file_size": file_size,
            "status": "pending",
            "message": "File uploaded. Processing will begin shortly."
        }
    except Exception as e:
        print(f"[UPLOAD] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document"""
    try:
        if supabase:
            # Get file path before deleting
            doc_response = supabase.table("documents").select("file_path").eq("id", document_id).execute()
            
        # Delete from Supabase
        supabase.table("documents").delete().eq("id", document_id).execute()
        
            # Try to delete file
        if doc_response.data and doc_response.data[0].get("file_path"):
            file_path = Path(doc_response.data[0]["file_path"])
            if file_path.exists():
                file_path.unlink()
        
        return {"message": "Document deleted successfully"}
    except Exception as e:
        print(f"[DELETE] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Conversation Management ====================

@app.get("/api/conversations")
async def list_conversations():
    """List all conversations"""
    try:
        if not supabase:
            return []
        response = supabase.table("conversations").select("*").order("created_at", desc=True).execute()
        conversations = response.data if response.data else []
        
        # Get message counts for each conversation
        for conv in conversations:
            try:
            msg_response = supabase.table("conversation_messages").select("id").eq("conversation_id", conv["id"]).execute()
            conv["message_count"] = len(msg_response.data) if msg_response.data else 0
            except:
                conv["message_count"] = 0
        
        return conversations
    except Exception as e:
        print(f"[CONVERSATIONS] Error: {e}")
        return []


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation with messages"""
    try:
        if not supabase:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
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
        print(f"[CONVERSATION] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Legacy n8n Endpoints ====================

@app.post("/voice-agent/process")
async def process_voice_agent_legacy(request: TranscribeRequest, conversation_id: Optional[str] = None):
    """Legacy endpoint for n8n - Complete voice agent flow"""
    try:
        # Step 1: Transcribe
        transcript_result = await transcribe(request)
        user_text = transcript_result["text"]
        
        if not user_text:
            return {"error": "No speech detected"}
        
        # Step 2: RAG Query
        query_result = await rag_query(QueryRequest(query=user_text))
        answer = query_result["answer"]
        
        # Step 3: Save conversation
        if supabase:
            try:
                if not conversation_id:
                    conv_response = supabase.table("conversations").insert({
                        "title": user_text[:50] + "..." if len(user_text) > 50 else user_text,
                        "created_at": time.time()
                    }).execute()
                    conversation_id = str(conv_response.data[0]["id"]) if conv_response.data else None
                
                if conversation_id:
                    supabase.table("conversation_messages").insert([
                        {
                            "conversation_id": int(conversation_id),
                            "role": "user",
                            "content": user_text,
                            "created_at": time.time()
                        },
                        {
                            "conversation_id": int(conversation_id),
                            "role": "assistant",
                            "content": answer,
                            "created_at": time.time()
                        }
                    ]).execute()
            except Exception as e:
                print(f"[LEGACY] Error saving conversation: {e}")
        
        return {
            "conversation_id": conversation_id,
            "user_text": user_text,
            "answer": answer,
            "context_docs": query_result["context_docs"],
            "context_count": query_result["context_count"]
        }
    except Exception as e:
        print(f"[LEGACY] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag-query")
async def rag_query_legacy(request: QueryRequest):
    """Legacy endpoint for n8n"""
    return await rag_query(request)


# ==================== Static Files & Frontend ====================

# Mount static files for frontend
frontend_path = Path("/app/frontend")
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
    
    @app.get("/")
    async def serve_index():
        index_path = frontend_path / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="Frontend not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
