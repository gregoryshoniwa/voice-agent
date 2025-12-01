#!/usr/bin/env python3
"""
RAG Indexer - Watches a folder for documents and indexes them using Supabase vector storage
Uses Ollama for embeddings. Updates document status in real-time.
"""

import os
import sys
import time
import hashlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv
from supabase import create_client, Client
from pypdf import PdfReader
import requests

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://kong:8000")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
WATCH_FOLDER = os.getenv("WATCH_FOLDER", "/data/documents")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

print(f"[RAG INDEXER] Starting...", flush=True)
print(f"[RAG INDEXER] Supabase URL: {SUPABASE_URL}", flush=True)
print(f"[RAG INDEXER] Watch folder: {WATCH_FOLDER}", flush=True)
print(f"[RAG INDEXER] Ollama URL: {OLLAMA_BASE_URL}", flush=True)
print(f"[RAG INDEXER] Embedding model: {EMBEDDING_MODEL}", flush=True)

# Initialize Supabase client
supabase: Client = None
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    print("[RAG INDEXER] Supabase client initialized", flush=True)
except Exception as e:
    print(f"[RAG INDEXER] Error initializing Supabase: {e}", flush=True)

# Track processed files
processed_files = set()


def update_document_status(file_path: str, status: str, error_message: str = None, content: str = None, embedding: list = None):
    """Update document status in database"""
    try:
        if not supabase:
            return
        
        # Find document by file_path
        response = supabase.table("documents").select("id").eq("file_path", file_path).execute()
        
        if response.data and len(response.data) > 0:
            doc_id = response.data[0]["id"]
            update_data = {
                "status": status,
                "updated_at": time.time()
            }
            
            if error_message:
                update_data["error_message"] = error_message
            
            if content:
                update_data["content"] = content
            
            if embedding:
                update_data["embedding"] = embedding
            
            if status == "indexed":
                update_data["indexed_at"] = time.time()
            
            supabase.table("documents").update(update_data).eq("id", doc_id).execute()
            print(f"[INDEXER] Updated status for doc {doc_id}: {status}", flush=True)
        else:
            # Document not in DB yet (uploaded via file copy, not web UI)
            # Create a new record
            if status == "indexed" and content and embedding:
                supabase.table("documents").insert({
                    "file_path": file_path,
                    "file_name": Path(file_path).name,
                    "file_type": Path(file_path).suffix,
                    "content": content,
                    "embedding": embedding,
                    "status": status,
                    "indexed_at": time.time(),
                    "created_at": time.time()
                }).execute()
                print(f"[INDEXER] Created new indexed document for: {file_path}", flush=True)
    except Exception as e:
        print(f"[INDEXER] Error updating status: {e}", flush=True)


def wait_for_ollama():
    """Wait for Ollama to be ready"""
    print(f"[RAG INDEXER] Waiting for Ollama...", flush=True)
    max_retries = 60
    for i in range(max_retries):
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"[RAG INDEXER] Ollama is ready!", flush=True)
                return True
        except:
            pass
        
        if i % 10 == 0:
            print(f"[RAG INDEXER] Waiting for Ollama... ({i+1}/{max_retries})", flush=True)
        time.sleep(2)
    
    print(f"[RAG INDEXER] Warning: Ollama not available", flush=True)
    return False


def wait_for_supabase():
    """Wait for Supabase to be ready"""
    print(f"[RAG INDEXER] Waiting for Supabase...", flush=True)
    max_retries = 60
    for i in range(max_retries):
        try:
            if supabase:
                supabase.table("documents").select("id").limit(1).execute()
                print(f"[RAG INDEXER] Supabase is ready!", flush=True)
                return True
        except Exception as e:
            if "does not exist" in str(e):
                print(f"[RAG INDEXER] Waiting for documents table...", flush=True)
        
        if i % 10 == 0:
            print(f"[RAG INDEXER] Waiting for Supabase... ({i+1}/{max_retries})", flush=True)
        time.sleep(2)
    
    print(f"[RAG INDEXER] Warning: Supabase not ready", flush=True)
    return False


def get_embedding(text: str) -> list:
    """Get embedding from Ollama"""
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text},
        timeout=60
    )
    response.raise_for_status()
    return response.json()["embedding"]


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file"""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"[INDEXER] Error reading PDF {file_path}: {e}", flush=True)
        return ""


def extract_text_from_file(file_path: str) -> str:
    """Extract text from various file types"""
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix in [".txt", ".md"]:
        try:
            with open(file_path, "rb") as f:
                return f.read().decode(errors="ignore").strip()
        except Exception as e:
            print(f"[INDEXER] Error reading {file_path}: {e}", flush=True)
            return ""
    else:
        print(f"[INDEXER] Unsupported file type: {suffix}", flush=True)
        return ""


def index_document(file_path: str):
    """Index a document into Supabase with status updates"""
    print(f"[INDEXER] Processing: {file_path}", flush=True)
    
    # Skip if already processed
    if file_path in processed_files:
        print(f"[INDEXER] Already processed: {file_path}", flush=True)
        return
    
    try:
        # Update status to processing
        update_document_status(file_path, "processing")
        
        # Extract text
        text = extract_text_from_file(file_path)
        
        if not text:
            update_document_status(file_path, "error", "No text could be extracted from file")
            return
        
        print(f"[INDEXER] Extracted {len(text)} characters", flush=True)
        
        # Truncate if too long
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars]
            print(f"[INDEXER] Truncated to {max_chars} chars", flush=True)
        
        # Generate embedding
        print(f"[INDEXER] Generating embedding...", flush=True)
        embedding = get_embedding(text)
        print(f"[INDEXER] Embedding generated (dim: {len(embedding)})", flush=True)
        
        # Update document with content, embedding, and indexed status
        update_document_status(file_path, "indexed", content=text, embedding=embedding)
        
        processed_files.add(file_path)
        print(f"[INDEXER] ✓ Successfully indexed: {Path(file_path).name}", flush=True)
        
    except Exception as e:
        print(f"[INDEXER] Error indexing {file_path}: {e}", flush=True)
        update_document_status(file_path, "error", str(e))


def process_pending_documents():
    """Process any documents with pending status"""
    try:
        if not supabase:
            return
        
        response = supabase.table("documents").select("id, file_path").eq("status", "pending").execute()
        pending_docs = response.data if response.data else []
        
        if pending_docs:
            print(f"[RAG INDEXER] Found {len(pending_docs)} pending documents", flush=True)
            for doc in pending_docs:
                file_path = doc.get("file_path")
                if file_path and Path(file_path).exists():
                    index_document(file_path)
                else:
                    print(f"[INDEXER] File not found: {file_path}", flush=True)
                    update_document_status(file_path, "error", "File not found on disk")
    except Exception as e:
        print(f"[RAG INDEXER] Error processing pending: {e}", flush=True)


def index_existing_files():
    """Index files that exist on disk but not in database"""
    watch_path = Path(WATCH_FOLDER)
    if not watch_path.exists():
        return
    
    supported_extensions = {".pdf", ".txt", ".md"}
    
    for file_path in watch_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            if not file_path.name.startswith('.'):
                str_path = str(file_path)
                
                # Check if already in database
                try:
                    if supabase:
                        response = supabase.table("documents").select("id, status").eq("file_path", str_path).execute()
                        if response.data and len(response.data) > 0:
                            status = response.data[0].get("status")
                            if status == "indexed":
                                processed_files.add(str_path)
                                continue
                            elif status == "pending":
                                index_document(str_path)
                                continue
                except:
                    pass
                
                # File not in DB, index it
                index_document(str_path)


class DocHandler(FileSystemEventHandler):
    """Handler for file system events"""
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        path = Path(filepath)
        
        if path.name.startswith('.'):
            return
        
        if path.suffix.lower() in {".pdf", ".txt", ".md"}:
            print(f"[INDEXER] New file detected: {filepath}", flush=True)
            time.sleep(2)  # Wait for file to be written
            index_document(filepath)
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        path = Path(filepath)
        
        if path.name.startswith('.'):
            return
        
        if path.suffix.lower() in {".pdf", ".txt", ".md"}:
            # Remove from processed to allow reindexing
            processed_files.discard(filepath)
            print(f"[INDEXER] File modified: {filepath}", flush=True)
            time.sleep(1)
            index_document(filepath)


def main():
    """Main function"""
    print("[RAG INDEXER] Initializing...", flush=True)
    
    # Wait for dependencies
    wait_for_ollama()
    wait_for_supabase()
    
    # Create watch folder
    watch_path = Path(WATCH_FOLDER)
    watch_path.mkdir(parents=True, exist_ok=True)
    
    # Process pending documents from database
    print("[RAG INDEXER] Checking for pending documents...", flush=True)
    process_pending_documents()
    
    # Index existing files
    print(f"[RAG INDEXER] Checking existing files in {WATCH_FOLDER}...", flush=True)
    index_existing_files()
    
    # Set up file watcher
    event_handler = DocHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=True)
    observer.start()
    
    print(f"[RAG INDEXER] Watching: {WATCH_FOLDER}", flush=True)
    print(f"[RAG INDEXER] Ready for new documents!", flush=True)
    
    # Periodically check for pending documents
    try:
        while True:
            time.sleep(10)
            process_pending_documents()
    except KeyboardInterrupt:
        observer.stop()
        print("\n[RAG INDEXER] Stopping...", flush=True)
    
    observer.join()


if __name__ == "__main__":
    main()
