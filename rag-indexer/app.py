#!/usr/bin/env python3
"""
RAG Indexer - Watches a folder for documents and indexes them using Supabase vector storage
Uses Ollama for embeddings
"""

import os
import time
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

print(f"[RAG INDEXER] Starting...")
print(f"[RAG INDEXER] Supabase URL: {SUPABASE_URL}")
print(f"[RAG INDEXER] Watch folder: {WATCH_FOLDER}")
print(f"[RAG INDEXER] Ollama URL: {OLLAMA_BASE_URL}")
print(f"[RAG INDEXER] Embedding model: {EMBEDDING_MODEL}")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_embedding(text: str) -> list:
    """Get embedding from Ollama"""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": EMBEDDING_MODEL,
                "prompt": text
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except Exception as e:
        print(f"[INDEXER] Error getting embedding: {e}")
        raise


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file"""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"[INDEXER] Error reading PDF {file_path}: {e}")
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
            return text
        except Exception as e:
            print(f"[INDEXER] Error reading text file {file_path}: {e}")
            return ""
    else:
        print(f"[INDEXER] Unsupported file type: {suffix}")
        return ""


def index_document(file_path: str):
    """Index a document into Supabase"""
    print(f"[INDEXER] New document: {file_path}")
    
    try:
        # Extract text from file
        text = extract_text_from_file(file_path)
        
        if not text:
            print(f"[INDEXER] No text extracted from {file_path}")
            return
        
        # Truncate text if too long (Ollama has limits)
        max_chars = 8000  # Adjust based on your model
        if len(text) > max_chars:
            text = text[:max_chars]
            print(f"[INDEXER] Text truncated to {max_chars} characters")
        
        # Generate embedding
        print(f"[INDEXER] Generating embedding...")
        embedding = get_embedding(text)
        
        # Insert into Supabase
        supabase.table("documents").insert({
            "content": text,
            "embedding": embedding,
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "file_type": Path(file_path).suffix,
            "indexed_at": time.time()
        }).execute()
        
        print(f"[INDEXER] Document indexed → Supabase")
        
    except Exception as e:
        print(f"[INDEXER] Error indexing {file_path}: {e}")


def index_existing_documents():
    """Index all existing documents in the watch folder"""
    watch_path = Path(WATCH_FOLDER)
    if not watch_path.exists():
        print(f"[RAG INDEXER] Watch folder does not exist: {WATCH_FOLDER}")
        return
    
    print(f"[RAG INDEXER] Indexing existing documents in {WATCH_FOLDER}...")
    
    # Supported file extensions
    supported_extensions = {".pdf", ".txt", ".md"}
    
    for file_path in watch_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            index_document(str(file_path))


class DocHandler(FileSystemEventHandler):
    """Handler for file system events"""
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        path = Path(filepath)
        
        if path.suffix.lower() in {".pdf", ".txt", ".md"}:
            time.sleep(1)  # Wait for file to be fully written
            index_document(filepath)
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        path = Path(filepath)
        
        if path.suffix.lower() in {".pdf", ".txt", ".md"}:
            index_document(filepath)


def main():
    """Main function"""
    # Wait for Ollama to be ready
    print(f"[RAG INDEXER] Waiting for Ollama to be ready...")
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"[RAG INDEXER] Ollama is ready!")
                break
        except:
            if i < max_retries - 1:
                print(f"[RAG INDEXER] Waiting for Ollama... ({i+1}/{max_retries})")
                time.sleep(2)
            else:
                print(f"[RAG INDEXER] Warning: Ollama not available, continuing anyway...")
    
    # Index existing documents
    index_existing_documents()
    
    # Set up file watcher
    watch_path = Path(WATCH_FOLDER)
    if not watch_path.exists():
        print(f"[RAG INDEXER] Creating watch folder: {WATCH_FOLDER}")
        watch_path.mkdir(parents=True, exist_ok=True)
    
    event_handler = DocHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=True)
    observer.start()
    
    print(f"[RAG INDEXER] Watching folder: {WATCH_FOLDER}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[RAG INDEXER] Stopping...")
    
    observer.join()


if __name__ == "__main__":
    main()
