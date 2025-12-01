#!/bin/bash

#################################################
# RunPod Native Setup Script (No Docker Required)
# This script sets up the Voice Agent directly on RunPod
# without needing Docker-in-Docker
#################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}"
echo "================================================"
echo "   AI Voice Agent - RunPod Native Setup"
echo "   (No Docker Required)"
echo "================================================"
echo -e "${NC}"

print_status() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_info() { echo -e "${BLUE}[i]${NC} $1"; }

#################################################
# Step 1: Check GPU
#################################################
echo ""
print_info "Step 1/7: Checking GPU..."
if command -v nvidia-smi &> /dev/null; then
    print_status "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    print_warning "No NVIDIA GPU detected - will use CPU (slower)"
fi

#################################################
# Step 2: Install System Dependencies
#################################################
echo ""
print_info "Step 2/7: Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv curl wget git ffmpeg postgresql postgresql-contrib > /dev/null 2>&1
print_status "System dependencies installed"

#################################################
# Step 3: Install Ollama
#################################################
echo ""
print_info "Step 3/7: Installing Ollama..."
if command -v ollama &> /dev/null; then
    print_status "Ollama already installed"
else
    curl -fsSL https://ollama.com/install.sh | sh
    print_status "Ollama installed"
fi

# Start Ollama in background
print_info "Starting Ollama server..."
pkill ollama || true
sleep 2
nohup ollama serve > /tmp/ollama.log 2>&1 &
sleep 5

# Verify Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    print_status "Ollama server running"
else
    print_warning "Ollama may still be starting, continuing..."
fi

#################################################
# Step 4: Pull Ollama Models
#################################################
echo ""
print_info "Step 4/7: Pulling Ollama models (this may take 5-10 minutes)..."

echo "  Pulling llama3.2:1b (LLM model)..."
ollama pull llama3.2:1b || print_warning "Failed to pull llama3.2:1b"

echo "  Pulling nomic-embed-text (embedding model)..."
ollama pull nomic-embed-text || print_warning "Failed to pull nomic-embed-text"

print_status "Ollama models pulled"

#################################################
# Step 5: Setup PostgreSQL (Simple RAG DB)
#################################################
echo ""
print_info "Step 5/7: Setting up PostgreSQL database..."

# Start PostgreSQL
service postgresql start || true
sleep 2

# Create database and user
sudo -u postgres psql -c "CREATE USER voiceagent WITH PASSWORD 'voiceagent123';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE voiceagent OWNER voiceagent;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE voiceagent TO voiceagent;" 2>/dev/null || true

# Install pgvector extension
sudo -u postgres psql -d voiceagent -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || print_warning "pgvector may not be available"

# Create tables
sudo -u postgres psql -d voiceagent << 'EOF'
-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    file_name TEXT,
    file_type TEXT,
    file_path TEXT,
    file_size BIGINT,
    content TEXT,
    embedding vector(768),
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    indexed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Conversation messages table
CREATE TABLE IF NOT EXISTS conversation_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector similarity search function
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id int,
    content text,
    file_name text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        documents.id,
        documents.content,
        documents.file_name,
        1 - (documents.embedding <=> query_embedding) as similarity
    FROM documents
    WHERE documents.embedding IS NOT NULL
    AND 1 - (documents.embedding <=> query_embedding) > match_threshold
    ORDER BY documents.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO voiceagent;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO voiceagent;
EOF

print_status "PostgreSQL database configured"

#################################################
# Step 6: Setup Python Environment
#################################################
echo ""
print_info "Step 6/7: Setting up Python environment..."

# Create virtual environment
python3 -m venv "$SCRIPT_DIR/venv"
source "$SCRIPT_DIR/venv/bin/activate"

# Install dependencies
pip install --upgrade pip -q
pip install -q \
    fastapi \
    uvicorn \
    requests \
    python-dotenv \
    pydantic \
    python-multipart \
    psycopg2-binary \
    pypdf \
    watchdog \
    openai-whisper \
    torch \
    numpy

print_status "Python environment ready"

#################################################
# Step 7: Create Environment File
#################################################
echo ""
print_info "Step 7/7: Creating configuration..."

cat > "$SCRIPT_DIR/.env.runpod" << EOF
# RunPod Native Configuration
DATABASE_URL=postgresql://voiceagent:voiceagent123@localhost:5432/voiceagent
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.2:1b
EMBEDDING_MODEL=nomic-embed-text

# Whisper (local)
WHISPER_MODEL=base

# Paths
DOCUMENTS_DIR=$SCRIPT_DIR/documents
FRONTEND_DIR=$SCRIPT_DIR/frontend
EOF

# Create documents directory
mkdir -p "$SCRIPT_DIR/documents"

print_status "Configuration created"

#################################################
# Create Startup Script
#################################################
cat > "$SCRIPT_DIR/start-services.sh" << 'STARTSCRIPT'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting AI Voice Agent services..."

# Start PostgreSQL
service postgresql start 2>/dev/null || true

# Start Ollama
pkill ollama 2>/dev/null || true
sleep 1
nohup ollama serve > /tmp/ollama.log 2>&1 &
sleep 3

# Activate virtual environment and start API
source "$SCRIPT_DIR/venv/bin/activate"
export $(cat .env.runpod | xargs)

echo "Starting Voice Agent API on port 3001..."
cd "$SCRIPT_DIR"
python3 -m uvicorn voice_agent_native:app --host 0.0.0.0 --port 3001 --reload &

echo ""
echo "================================================"
echo "   Services Started!"
echo "================================================"
echo ""
echo "Access URLs:"
echo "  • Frontend:  http://localhost:3001"
echo "  • API Docs:  http://localhost:3001/docs"
echo "  • Ollama:    http://localhost:11434"
echo ""
echo "To check logs:"
echo "  • Ollama:    tail -f /tmp/ollama.log"
echo ""
STARTSCRIPT

chmod +x "$SCRIPT_DIR/start-services.sh"

#################################################
# Create Native Voice Agent API
#################################################
cat > "$SCRIPT_DIR/voice_agent_native.py" << 'PYCODE'
#!/usr/bin/env python3
"""
Voice Agent API - Native RunPod Version (No Docker)
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
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="Voice Agent API - RunPod Native")

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
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR", "./documents"))
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", "./frontend"))

DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

print(f"[VOICE-AGENT] Starting Native RunPod Version...")
print(f"[VOICE-AGENT] Ollama URL: {OLLAMA_BASE_URL}")
print(f"[VOICE-AGENT] LLM Model: {LLM_MODEL}")

# Database connection
def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# Request Models
class QueryRequest(BaseModel):
    query: str
    top_k: int = 3

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


# Health & Status
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "voice-agent-api-native"}

@app.get("/api/status")
async def status():
    status_info = {"api": "ok", "database": "unknown", "ollama": "unknown"}
    
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        status_info["database"] = "ok"
    except Exception as e:
        status_info["database"] = f"error: {str(e)[:50]}"
    
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            status_info["ollama"] = "ok"
    except Exception as e:
        status_info["ollama"] = f"error: {str(e)[:50]}"
    
    return status_info


# Chat Endpoint
@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Text-based chat with RAG"""
    try:
        user_text = request.message.strip()
        if not user_text:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        query_result = await rag_query(QueryRequest(query=user_text))
        answer = query_result["answer"]
        
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


# RAG Query
@app.post("/api/rag-query")
async def rag_query(request: QueryRequest):
    """Query RAG system"""
    try:
        context_docs = []
        context = ""
        
        # Try to get embeddings and search
        try:
            embedding_response = requests.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": request.query},
                timeout=30
            )
            embedding_response.raise_for_status()
            query_embedding = embedding_response.json()["embedding"]
            
            # Search database
            with get_db() as conn:
                with conn.cursor() as cur:
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
            
            context = "\n\n---\n\n".join([doc.get("content", "")[:2000] for doc in context_docs])
        except Exception as e:
            print(f"[RAG] Search error: {e}")
        
        # Build prompt
        if context:
            prompt = f"""You are a helpful AI assistant. Use the following context to answer the question.

Context:
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
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
            timeout=120
        )
        llm_response.raise_for_status()
        answer = llm_response.json().get("response", "Sorry, I couldn't generate a response.")
        
        return {"answer": answer, "context_docs": context_docs, "context_count": len(context_docs)}
    except Exception as e:
        print(f"[RAG] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Document Management
@app.get("/api/documents")
async def list_documents():
    """List all documents"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, file_name, file_type, file_path, file_size, status, 
                              error_message, indexed_at, created_at 
                       FROM documents ORDER BY created_at DESC"""
                )
                return cur.fetchall()
    except Exception as e:
        print(f"[DOCUMENTS] Error: {e}")
        return []

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document"""
    try:
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        file_path = DOCUMENTS_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
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
            "status": "pending",
            "message": "File uploaded successfully"
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
                cur.execute("SELECT file_path FROM documents WHERE id = %s", (document_id,))
                result = cur.fetchone()
                if result and result.get("file_path"):
                    file_path = Path(result["file_path"])
                    if file_path.exists():
                        file_path.unlink()
                cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
            conn.commit()
        return {"message": "Document deleted"}
    except Exception as e:
        print(f"[DELETE] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Conversations
@app.get("/api/conversations")
async def list_conversations():
    """List all conversations"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM conversations ORDER BY created_at DESC")
                return cur.fetchall()
    except Exception as e:
        print(f"[CONVERSATIONS] Error: {e}")
        return []

@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: int):
    """Get conversation with messages"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM conversations WHERE id = %s", (conversation_id,))
                conv = cur.fetchone()
                if not conv:
                    raise HTTPException(status_code=404, detail="Not found")
                
                cur.execute(
                    "SELECT * FROM conversation_messages WHERE conversation_id = %s ORDER BY created_at",
                    (conversation_id,)
                )
                conv["messages"] = cur.fetchall()
                return conv
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONVERSATION] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Static Files & Frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    
    @app.get("/")
    async def serve_index():
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="Frontend not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
PYCODE

#################################################
# Final Output
#################################################
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}   Setup Complete!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${YELLOW}To start the services:${NC}"
echo "  ./start-services.sh"
echo ""
echo -e "${YELLOW}Or manually:${NC}"
echo "  source venv/bin/activate"
echo "  export \$(cat .env.runpod | xargs)"
echo "  python3 -m uvicorn voice_agent_native:app --host 0.0.0.0 --port 3001"
echo ""
echo -e "${YELLOW}Access URLs (configure RunPod public endpoints):${NC}"
echo "  • Frontend:  http://<runpod-ip>:3001"
echo "  • API Docs:  http://<runpod-ip>:3001/docs"
echo "  • Ollama:    http://<runpod-ip>:11434"
echo ""
echo -e "${YELLOW}Ollama models installed:${NC}"
ollama list 2>/dev/null || echo "  (Ollama still starting...)"
echo ""

