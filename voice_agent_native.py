#!/usr/bin/env python3
"""
Voice Agent API - Native RunPod Version (No Docker/Supabase Required)
Uses PostgreSQL directly with pgvector for vector search.
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
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
import json

app = FastAPI(title="Voice Agent API - RunPod Native", version="2.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://voiceagent:voiceagent123@localhost:5432/voiceagent")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
WHISPER_URL = os.getenv("WHISPER_URL", "http://localhost:9000")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR", "./documents"))
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", "./frontend"))

DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

print(f"[VOICE-AGENT] Starting Native RunPod Version...")
print(f"[VOICE-AGENT] Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
print(f"[VOICE-AGENT] Ollama URL: {OLLAMA_BASE_URL}")
print(f"[VOICE-AGENT] LLM Model: {LLM_MODEL}")
print(f"[VOICE-AGENT] Embedding Model: {EMBEDDING_MODEL}")
print(f"[VOICE-AGENT] Documents Dir: {DOCUMENTS_DIR}")
print(f"[VOICE-AGENT] Frontend Dir: {FRONTEND_DIR}")


# ==================== Database Connection ====================

def get_db():
    """Get database connection"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    """Initialize database tables if they don't exist"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Check if tables exist
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'documents'
                    )
                """)
                if not cur.fetchone()['exists']:
                    print("[VOICE-AGENT] Creating database tables...")
                    # Tables will be created by setup script
            conn.commit()
        print("[VOICE-AGENT] Database connection successful")
        return True
    except Exception as e:
        print(f"[VOICE-AGENT] Database error: {e}")
        return False


# Initialize on startup
@app.on_event("startup")
async def startup_event():
    init_db()


# ==================== Request Models ====================

class TranscribeRequest(BaseModel):
    audio_url: Optional[str] = None
    audio_data: Optional[str] = None


class QueryRequest(BaseModel):
    query: str
    top_k: int = 3


class SynthesizeRequest(BaseModel):
    text: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class VoiceChatRequest(BaseModel):
    audio_data: str
    conversation_id: Optional[str] = None


# ==================== Health & Status ====================

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "voice-agent-api-native", "version": "2.0"}


@app.get("/api/status")
async def status():
    status_info = {
        "api": "ok",
        "database": "unknown",
        "ollama": "unknown",
        "whisper": "unknown"
    }
    
    # Check database
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        status_info["database"] = "ok"
    except Exception as e:
        status_info["database"] = f"error: {str(e)[:50]}"
    
    # Check Ollama
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            status_info["ollama"] = f"ok ({len(models)} models)"
    except Exception as e:
        status_info["ollama"] = f"error: {str(e)[:50]}"
    
    # Check Whisper (optional)
    try:
        resp = requests.get(f"{WHISPER_URL}/", timeout=3)
        if resp.status_code in [200, 404]:
            status_info["whisper"] = "ok"
    except:
        status_info["whisper"] = "not configured"
    
    return status_info


# ==================== Chat Endpoints ====================

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Text-based chat with RAG"""
    try:
        user_text = request.message.strip()
        if not user_text:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Query RAG system
        query_result = await rag_query(QueryRequest(query=user_text))
        answer = query_result["answer"]
        
        # Save to database
        conversation_id = request.conversation_id
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    if not conversation_id:
                        # Create new conversation
                        cur.execute(
                            "INSERT INTO conversations (title) VALUES (%s) RETURNING id",
                            (user_text[:50] + "..." if len(user_text) > 50 else user_text,)
                        )
                        conversation_id = str(cur.fetchone()["id"])
                    
                    # Save messages
                    cur.execute(
                        "INSERT INTO conversation_messages (conversation_id, role, content) VALUES (%s, %s, %s)",
                        (int(conversation_id), "user", user_text)
                    )
                    cur.execute(
                        "INSERT INTO conversation_messages (conversation_id, role, content) VALUES (%s, %s, %s)",
                        (int(conversation_id), "assistant", answer)
                    )
                conn.commit()
        except Exception as e:
            print(f"[CHAT] DB error: {e}")
        
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
        # Decode audio
        audio_data = base64.b64decode(request.audio_data)
        
        # Transcribe with Whisper
        user_text = ""
        try:
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
        except Exception as e:
            print(f"[VOICE-CHAT] Whisper error: {e}")
            # Fallback: try local whisper if available
            try:
                import whisper
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio_data)
                    temp_path = f.name
                model = whisper.load_model("base")
                result = model.transcribe(temp_path)
                user_text = result["text"].strip()
                os.unlink(temp_path)
            except Exception as e2:
                print(f"[VOICE-CHAT] Local whisper error: {e2}")
                return {"error": "Speech recognition not available", "user_text": ""}
        
        if not user_text:
            return {"error": "No speech detected", "user_text": ""}
        
        # Query RAG
        query_result = await rag_query(QueryRequest(query=user_text))
        answer = query_result["answer"]
        
        # Save conversation
        conversation_id = request.conversation_id
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    if not conversation_id:
                        cur.execute(
                            "INSERT INTO conversations (title) VALUES (%s) RETURNING id",
                            (user_text[:50],)
                        )
                        conversation_id = str(cur.fetchone()["id"])
                    
                    cur.execute(
                        "INSERT INTO conversation_messages (conversation_id, role, content) VALUES (%s, %s, %s)",
                        (int(conversation_id), "user", user_text)
                    )
                    cur.execute(
                        "INSERT INTO conversation_messages (conversation_id, role, content) VALUES (%s, %s, %s)",
                        (int(conversation_id), "assistant", answer)
                    )
                conn.commit()
        except Exception as e:
            print(f"[VOICE-CHAT] DB error: {e}")
        
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
    """Query RAG system with vector similarity search"""
    try:
        context_docs = []
        context = ""
        
        # Try to get embeddings and search
        try:
            # Generate query embedding
            embedding_response = requests.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": request.query},
                timeout=30
            )
            embedding_response.raise_for_status()
            query_embedding = embedding_response.json()["embedding"]
            
            # Vector similarity search
            with get_db() as conn:
                with conn.cursor() as cur:
                    # Try vector search first
                    try:
                        cur.execute(
                            """
                            SELECT id, content, file_name,
                                   1 - (embedding <=> %s::vector) as similarity
                            FROM documents
                            WHERE status = 'indexed' 
                              AND embedding IS NOT NULL
                              AND content IS NOT NULL
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s
                            """,
                            (query_embedding, query_embedding, request.top_k)
                        )
                        context_docs = cur.fetchall()
                    except Exception as e:
                        print(f"[RAG] Vector search error: {e}")
                        # Fallback to simple text search
                        cur.execute(
                            """
                            SELECT id, content, file_name
                            FROM documents
                            WHERE status = 'indexed' AND content IS NOT NULL
                            LIMIT %s
                            """,
                            (request.top_k,)
                        )
                        context_docs = cur.fetchall()
            
            # Build context string
            context = "\n\n---\n\n".join([
                doc.get("content", "")[:2000] 
                for doc in context_docs 
                if doc.get("content")
            ])
            
        except Exception as e:
            print(f"[RAG] Embedding/search error: {e}")
        
        # Build prompt
        if context:
            prompt = f"""You are a helpful AI assistant. Use the following context from documents to answer the question. If the context doesn't contain relevant information, say so and provide a general answer.

Context from documents:
{context}

Question: {request.query}

Answer:"""
        else:
            prompt = f"""You are a helpful AI assistant. Answer the following question:

Question: {request.query}

Answer:"""
        
        # Query LLM
        llm_response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 500
                }
            },
            timeout=120
        )
        llm_response.raise_for_status()
        answer = llm_response.json().get("response", "Sorry, I couldn't generate a response.")
        
        return {
            "answer": answer,
            "context_docs": [{"id": d.get("id"), "file_name": d.get("file_name")} for d in context_docs],
            "context_count": len(context_docs)
        }
    except Exception as e:
        print(f"[RAG] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transcribe")
async def transcribe(request: TranscribeRequest):
    """Transcribe audio to text"""
    try:
        if request.audio_url:
            audio_response = requests.get(request.audio_url, timeout=30)
            audio_data = audio_response.content
        elif request.audio_data:
            audio_data = base64.b64decode(request.audio_data)
        else:
            raise HTTPException(status_code=400, detail="Either audio_url or audio_data required")
        
        # Try Whisper service
        try:
            files = {"file": ("audio.wav", audio_data, "audio/wav")}
            response = requests.post(
                f"{WHISPER_URL}/asr",
                files=files,
                data={"language": "en", "output": "json"},
                timeout=60
            )
            response.raise_for_status()
            return {"text": response.json().get("text", "")}
        except:
            # Fallback to local whisper
            import whisper
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            model = whisper.load_model("base")
            result = model.transcribe(temp_path)
            os.unlink(temp_path)
            return {"text": result["text"]}
            
    except Exception as e:
        print(f"[TRANSCRIBE] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Document Management ====================

@app.get("/api/documents")
async def list_documents():
    """List all documents"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, file_name, file_type, file_path, file_size, 
                              status, error_message, indexed_at, created_at 
                       FROM documents 
                       ORDER BY created_at DESC"""
                )
                docs = cur.fetchall()
                # Convert to list of dicts
                return [dict(doc) for doc in docs]
    except Exception as e:
        print(f"[DOCUMENTS] Error: {e}")
        return []


@app.get("/api/documents/status")
async def get_documents_status():
    """Get document status summary"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT 
                         COUNT(*) as total,
                         COUNT(*) FILTER (WHERE status = 'pending') as pending,
                         COUNT(*) FILTER (WHERE status = 'processing') as processing,
                         COUNT(*) FILTER (WHERE status = 'indexed') as indexed,
                         COUNT(*) FILTER (WHERE status = 'error') as error
                       FROM documents"""
                )
                result = cur.fetchone()
                return dict(result) if result else {
                    "total": 0, "pending": 0, "processing": 0, "indexed": 0, "error": 0
                }
    except Exception as e:
        print(f"[STATUS] Error: {e}")
        return {"total": 0, "pending": 0, "processing": 0, "indexed": 0, "error": 0}


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document"""
    try:
        # Get file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        # Save file
        file_path = DOCUMENTS_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"[UPLOAD] File saved: {file_path}")
        
        # Insert into database
        doc_id = None
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO documents (file_name, file_type, file_path, file_size, status) 
                       VALUES (%s, %s, %s, %s, 'pending') RETURNING id""",
                    (file.filename, Path(file.filename).suffix, str(file_path), file_size)
                )
                doc_id = cur.fetchone()["id"]
            conn.commit()
        
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
async def delete_document(document_id: int):
    """Delete a document"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Get file path
                cur.execute("SELECT file_path FROM documents WHERE id = %s", (document_id,))
                result = cur.fetchone()
                
                # Delete from database
                cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
                
                # Delete file
                if result and result.get("file_path"):
                    file_path = Path(result["file_path"])
                    if file_path.exists():
                        file_path.unlink()
            conn.commit()
        
        return {"message": "Document deleted"}
    except Exception as e:
        print(f"[DELETE] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Conversation Management ====================

@app.get("/api/conversations")
async def list_conversations():
    """List all conversations"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.*, 
                              (SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = c.id) as message_count
                       FROM conversations c 
                       ORDER BY created_at DESC"""
                )
                return [dict(conv) for conv in cur.fetchall()]
    except Exception as e:
        print(f"[CONVERSATIONS] Error: {e}")
        return []


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: int):
    """Get conversation with messages"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Get conversation
                cur.execute("SELECT * FROM conversations WHERE id = %s", (conversation_id,))
                conv = cur.fetchone()
                if not conv:
                    raise HTTPException(status_code=404, detail="Conversation not found")
                
                conv = dict(conv)
                
                # Get messages
                cur.execute(
                    """SELECT * FROM conversation_messages 
                       WHERE conversation_id = %s 
                       ORDER BY created_at""",
                    (conversation_id,)
                )
                conv["messages"] = [dict(msg) for msg in cur.fetchall()]
                
                return conv
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONVERSATION] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Legacy Endpoints for n8n ====================

@app.post("/voice-agent/process")
async def process_voice_agent_legacy(request: TranscribeRequest, conversation_id: Optional[str] = None):
    """Legacy endpoint for n8n compatibility"""
    try:
        transcript_result = await transcribe(request)
        user_text = transcript_result["text"]
        
        if not user_text:
            return {"error": "No speech detected"}
        
        query_result = await rag_query(QueryRequest(query=user_text))
        
        return {
            "conversation_id": conversation_id,
            "user_text": user_text,
            "answer": query_result["answer"],
            "context_docs": query_result["context_docs"],
            "context_count": query_result["context_count"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag-query")
async def rag_query_legacy(request: QueryRequest):
    """Legacy endpoint for n8n compatibility"""
    return await rag_query(request)


# ==================== Static Files & Frontend ====================

# Mount frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    
    @app.get("/")
    async def serve_index():
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="Frontend not found")
else:
    @app.get("/")
    async def root():
        return {
            "message": "Voice Agent API - RunPod Native",
            "docs": "/docs",
            "health": "/api/health",
            "status": "/api/status"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)

