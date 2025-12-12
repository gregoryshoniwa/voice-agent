#!/usr/bin/env python3
"""
RAG Indexer - Native RunPod Version (No Docker/Supabase Required)
Watches a folder for documents and indexes them using PostgreSQL with pgvector.
Uses Ollama for embeddings.
"""

import os
import sys
import time
import hashlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import psycopg2
from psycopg2.extras import RealDictCursor
from pypdf import PdfReader
import requests

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
WATCH_FOLDER = os.getenv("WATCH_FOLDER", "./documents")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

print(f"[RAG INDEXER] Starting Native Version...", flush=True)
print(f"[RAG INDEXER] Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}", flush=True)
print(f"[RAG INDEXER] Watch folder: {WATCH_FOLDER}", flush=True)
print(f"[RAG INDEXER] Ollama URL: {OLLAMA_BASE_URL}", flush=True)
print(f"[RAG INDEXER] Embedding model: {EMBEDDING_MODEL}", flush=True)

# Track processed files
processed_files = set()


def get_db():
    """Get database connection"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def update_document_status(file_path: str, status: str, error_message: str = None, 
                           content: str = None, embedding: list = None):
    """Update document status in database"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Find document by file_path
                cur.execute("SELECT id FROM documents WHERE file_path = %s", (file_path,))
                result = cur.fetchone()
                
                if result:
                    doc_id = result["id"]
                    
                    # Build update query
                    update_fields = ["status = %s", "updated_at = NOW()"]
                    update_values = [status]
                    
                    if error_message:
                        update_fields.append("error_message = %s")
                        update_values.append(error_message)
                    
                    if content:
                        update_fields.append("content = %s")
                        update_values.append(content)
                    
                    if embedding:
                        update_fields.append("embedding = %s::vector")
                        update_values.append(embedding)
                    
                    if status == "indexed":
                        update_fields.append("indexed_at = EXTRACT(EPOCH FROM NOW())")
                    
                    update_values.append(doc_id)
                    
                    cur.execute(
                        f"UPDATE documents SET {', '.join(update_fields)} WHERE id = %s",
                        update_values
                    )
                    print(f"[INDEXER] Updated status for doc {doc_id}: {status}", flush=True)
                else:
                    # Document not in DB yet - create new record
                    if status == "indexed" and content and embedding:
                        cur.execute(
                            """INSERT INTO documents 
                               (file_path, file_name, file_type, content, embedding, status, indexed_at) 
                               VALUES (%s, %s, %s, %s, %s::vector, %s, EXTRACT(EPOCH FROM NOW()))""",
                            (file_path, Path(file_path).name, Path(file_path).suffix, 
                             content, embedding, status)
                        )
                        print(f"[INDEXER] Created new indexed document for: {file_path}", flush=True)
            conn.commit()
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
                models = response.json().get("models", [])
                print(f"[RAG INDEXER] Ollama is ready! ({len(models)} models available)", flush=True)
                return True
        except:
            pass
        
        if i % 10 == 0:
            print(f"[RAG INDEXER] Waiting for Ollama... ({i+1}/{max_retries})", flush=True)
        time.sleep(2)
    
    print(f"[RAG INDEXER] Warning: Ollama not available", flush=True)
    return False


def wait_for_database():
    """Wait for database to be ready"""
    print(f"[RAG INDEXER] Waiting for database...", flush=True)
    max_retries = 30
    for i in range(max_retries):
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            print(f"[RAG INDEXER] Database is ready!", flush=True)
            return True
        except Exception as e:
            if i % 5 == 0:
                print(f"[RAG INDEXER] Waiting for database... ({i+1}/{max_retries})", flush=True)
        time.sleep(2)
    
    print(f"[RAG INDEXER] Warning: Database not ready", flush=True)
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


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX file"""
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        
        with zipfile.ZipFile(file_path) as z:
            xml_content = z.read('word/document.xml')
        
        tree = ET.fromstring(xml_content)
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        text_parts = []
        for paragraph in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
            texts = paragraph.findall('.//w:t', namespaces)
            para_text = ''.join([t.text for t in texts if t.text])
            if para_text:
                text_parts.append(para_text)
        
        return '\n'.join(text_parts)
    except Exception as e:
        print(f"[INDEXER] Error reading DOCX {file_path}: {e}", flush=True)
        return ""


def extract_text_from_file(file_path: str) -> str:
    """Extract text from various file types"""
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix == ".docx":
        return extract_text_from_docx(file_path)
    elif suffix in [".txt", ".md", ".json", ".csv"]:
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
    """Index a document into PostgreSQL with embeddings"""
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
        
        # Truncate if too long (Ollama has limits)
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
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, file_path FROM documents WHERE status = 'pending'"
                )
                pending_docs = cur.fetchall()
        
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
        print(f"[RAG INDEXER] Watch folder does not exist: {WATCH_FOLDER}", flush=True)
        return
    
    supported_extensions = {".pdf", ".txt", ".md", ".docx", ".json", ".csv"}
    
    for file_path in watch_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            if not file_path.name.startswith('.'):
                str_path = str(file_path)
                
                # Check if already in database
                try:
                    with get_db() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT id, status FROM documents WHERE file_path = %s",
                                (str_path,)
                            )
                            result = cur.fetchone()
                            
                            if result:
                                status = result.get("status")
                                if status == "indexed":
                                    processed_files.add(str_path)
                                    continue
                                elif status == "pending":
                                    index_document(str_path)
                                    continue
                except Exception as e:
                    print(f"[RAG INDEXER] Error checking file: {e}", flush=True)
                
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
        
        supported = {".pdf", ".txt", ".md", ".docx", ".json", ".csv"}
        if path.suffix.lower() in supported:
            print(f"[INDEXER] New file detected: {filepath}", flush=True)
            time.sleep(2)  # Wait for file to be fully written
            index_document(filepath)
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        path = Path(filepath)
        
        if path.name.startswith('.'):
            return
        
        supported = {".pdf", ".txt", ".md", ".docx", ".json", ".csv"}
        if path.suffix.lower() in supported:
            # Remove from processed to allow reindexing
            processed_files.discard(filepath)
            print(f"[INDEXER] File modified: {filepath}", flush=True)
            time.sleep(1)
            index_document(filepath)


def main():
    """Main function"""
    print("[RAG INDEXER] Initializing...", flush=True)
    
    # Wait for dependencies
    wait_for_database()
    wait_for_ollama()
    
    # Create watch folder if it doesn't exist
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
    print(f"[RAG INDEXER] Supported formats: PDF, TXT, MD, DOCX, JSON, CSV", flush=True)
    
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

