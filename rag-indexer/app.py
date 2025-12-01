#!/usr/bin/env python3
"""
RAG Indexer - Watches a folder for documents and indexes them using Supabase vector storage
Uses Ollama for embeddings
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

# Track indexed files to avoid duplicates
indexed_files = set()


def get_file_hash(file_path: str) -> str:
    """Get MD5 hash of a file"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"[INDEXER] Error hashing file: {e}", flush=True)
        return ""


def wait_for_ollama():
    """Wait for Ollama to be ready"""
    print(f"[RAG INDEXER] Waiting for Ollama to be ready...", flush=True)
    max_retries = 60
    for i in range(max_retries):
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"[RAG INDEXER] Ollama is ready!", flush=True)
                return True
        except:
            pass
        
        if i < max_retries - 1:
            if i % 10 == 0:
                print(f"[RAG INDEXER] Waiting for Ollama... ({i+1}/{max_retries})", flush=True)
            time.sleep(2)
    
    print(f"[RAG INDEXER] Warning: Ollama not available after {max_retries} attempts", flush=True)
    return False


def wait_for_supabase():
    """Wait for Supabase to be ready"""
    print(f"[RAG INDEXER] Waiting for Supabase to be ready...", flush=True)
    max_retries = 60
    for i in range(max_retries):
        try:
            if supabase:
                # Try to access the documents table
                supabase.table("documents").select("id").limit(1).execute()
                print(f"[RAG INDEXER] Supabase is ready!", flush=True)
                return True
        except Exception as e:
            if "does not exist" in str(e):
                print(f"[RAG INDEXER] Documents table not found, waiting for initialization...", flush=True)
        
        if i < max_retries - 1:
            if i % 10 == 0:
                print(f"[RAG INDEXER] Waiting for Supabase... ({i+1}/{max_retries})", flush=True)
            time.sleep(2)
    
    print(f"[RAG INDEXER] Warning: Supabase documents table not ready", flush=True)
    return False


def get_embedding(text: str) -> list:
    """Get embedding from Ollama"""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": EMBEDDING_MODEL,
                "prompt": text
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except Exception as e:
        print(f"[INDEXER] Error getting embedding: {e}", flush=True)
        raise


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
                text = f.read().decode(errors="ignore")
            return text.strip()
        except Exception as e:
            print(f"[INDEXER] Error reading text file {file_path}: {e}", flush=True)
            return ""
    else:
        print(f"[INDEXER] Unsupported file type: {suffix}", flush=True)
        return ""


def check_if_indexed(file_path: str, file_hash: str) -> bool:
    """Check if file is already indexed in Supabase"""
    try:
        if supabase:
            response = supabase.table("documents").select("id").eq("file_path", file_path).execute()
            if response.data and len(response.data) > 0:
                return True
    except Exception as e:
        print(f"[INDEXER] Error checking if indexed: {e}", flush=True)
    return False


def index_document(file_path: str):
    """Index a document into Supabase"""
    print(f"[INDEXER] Processing document: {file_path}", flush=True)
    
    # Skip if already processed in this session
    file_hash = get_file_hash(file_path)
    if file_hash in indexed_files:
        print(f"[INDEXER] Already processed in this session: {file_path}", flush=True)
        return
    
    # Check if already in database
    if check_if_indexed(file_path, file_hash):
        print(f"[INDEXER] Already indexed in database: {file_path}", flush=True)
        indexed_files.add(file_hash)
        return
    
    try:
        # Extract text from file
        text = extract_text_from_file(file_path)
        
        if not text:
            print(f"[INDEXER] No text extracted from {file_path}", flush=True)
            return
        
        print(f"[INDEXER] Extracted {len(text)} characters from {file_path}", flush=True)
        
        # Truncate text if too long (Ollama has limits)
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars]
            print(f"[INDEXER] Text truncated to {max_chars} characters", flush=True)
        
        # Generate embedding
        print(f"[INDEXER] Generating embedding...", flush=True)
        embedding = get_embedding(text)
        print(f"[INDEXER] Embedding generated (dimension: {len(embedding)})", flush=True)
        
        # Insert into Supabase
        if supabase:
            supabase.table("documents").insert({
                "content": text,
                "embedding": embedding,
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "file_type": Path(file_path).suffix,
                "indexed_at": time.time()
            }).execute()
            
            print(f"[INDEXER] ✓ Document indexed successfully: {Path(file_path).name}", flush=True)
            indexed_files.add(file_hash)
        else:
            print(f"[INDEXER] Warning: Supabase client not available", flush=True)
        
    except Exception as e:
        print(f"[INDEXER] Error indexing {file_path}: {e}", flush=True)


def index_existing_documents():
    """Index all existing documents in the watch folder"""
    watch_path = Path(WATCH_FOLDER)
    if not watch_path.exists():
        print(f"[RAG INDEXER] Watch folder does not exist: {WATCH_FOLDER}", flush=True)
        return
    
    # Supported file extensions
    supported_extensions = {".pdf", ".txt", ".md"}
    
    # Find all supported files
    files = []
    for file_path in watch_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            # Skip hidden files and gitkeep
            if not file_path.name.startswith('.'):
                files.append(str(file_path))
    
    if not files:
        print(f"[RAG INDEXER] No documents found in {WATCH_FOLDER}", flush=True)
        return
    
    print(f"[RAG INDEXER] Found {len(files)} document(s) to index", flush=True)
    
    for file_path in files:
        index_document(file_path)
        time.sleep(0.5)  # Small delay between files


class DocHandler(FileSystemEventHandler):
    """Handler for file system events"""
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        path = Path(filepath)
        
        # Skip hidden files
        if path.name.startswith('.'):
            return
        
        if path.suffix.lower() in {".pdf", ".txt", ".md"}:
            print(f"[INDEXER] New file detected: {filepath}", flush=True)
            time.sleep(2)  # Wait for file to be fully written
            index_document(filepath)
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        path = Path(filepath)
        
        # Skip hidden files
        if path.name.startswith('.'):
            return
        
        if path.suffix.lower() in {".pdf", ".txt", ".md"}:
            print(f"[INDEXER] File modified: {filepath}", flush=True)
            # Remove from indexed set to allow reindexing
            file_hash = get_file_hash(filepath)
            indexed_files.discard(file_hash)
            time.sleep(1)
            index_document(filepath)


def main():
    """Main function"""
    print("[RAG INDEXER] Initializing...", flush=True)
    
    # Wait for dependencies
    wait_for_ollama()
    wait_for_supabase()
    
    # Create watch folder if it doesn't exist
    watch_path = Path(WATCH_FOLDER)
    if not watch_path.exists():
        print(f"[RAG INDEXER] Creating watch folder: {WATCH_FOLDER}", flush=True)
        watch_path.mkdir(parents=True, exist_ok=True)
    
    # Index existing documents
    print(f"[RAG INDEXER] Indexing existing documents in {WATCH_FOLDER}...", flush=True)
    index_existing_documents()
    
    # Set up file watcher
    event_handler = DocHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=True)
    observer.start()
    
    print(f"[RAG INDEXER] Watching folder: {WATCH_FOLDER}", flush=True)
    print(f"[RAG INDEXER] Ready to index new documents", flush=True)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[RAG INDEXER] Stopping...", flush=True)
    
    observer.join()


if __name__ == "__main__":
    main()
