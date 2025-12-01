# RAG Indexer

A document indexing service that watches a folder for documents (PDF, TXT, MD) and automatically indexes them into Supabase vector storage for RAG (Retrieval-Augmented Generation) applications.

## Features

- **File Watching**: Automatically detects new and modified documents
- **Multiple Formats**: Supports PDF, TXT, and Markdown files
- **Vector Storage**: Uses Supabase for vector storage
- **Ollama Integration**: Uses Ollama for embeddings (runs on host machine)
- **Automatic Indexing**: Indexes existing documents on startup

## Configuration

The service is configured via environment variables:

- `SUPABASE_URL`: Supabase API URL (default: `http://kong:8000`)
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key
- `WATCH_FOLDER`: Folder to watch for documents (default: `/data/documents`)
- `EMBEDDING_MODEL`: HuggingFace embedding model to use (default: `BAAI/bge-small-en-v1.5`)

### Popular Embedding Models

- `BAAI/bge-small-en-v1.5` - Small, fast (384 dimensions)
- `BAAI/bge-base-en-v1.5` - Balanced (768 dimensions)
- `BAAI/bge-large-en-v1.5` - Large, high quality (1024 dimensions)
- `sentence-transformers/all-MiniLM-L6-v2` - Very small, fast (384 dimensions)

## Setup

Before using the RAG indexer, you need to create the vector store table in Supabase. You can do this by running a migration or using the Supabase SQL editor:

```sql
-- Create the documents table for vector storage
-- Adjust vector dimension based on your embedding model
CREATE TABLE IF NOT EXISTS documents (
  id BIGSERIAL PRIMARY KEY,
  content TEXT,
  embedding vector(384),  -- Adjust dimension: bge-small=384, bge-base=768, bge-large=1024
  file_path TEXT,
  file_name TEXT,
  file_type TEXT,
  indexed_at DOUBLE PRECISION
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS documents_embedding_idx ON documents 
USING ivfflat (embedding vector_cosine_ops);
```

**Note**: Adjust the `vector(384)` dimension to match your embedding model:
- `BAAI/bge-small-en-v1.5`: 384 dimensions
- `BAAI/bge-base-en-v1.5`: 768 dimensions
- `BAAI/bge-large-en-v1.5`: 1024 dimensions
- `sentence-transformers/all-MiniLM-L6-v2`: 384 dimensions

## Usage

The service is automatically started with the unified docker-compose setup. Place documents in the `./documents` folder and they will be automatically indexed.

## Requirements

- Supabase must be running and accessible
- The embedding model will be downloaded from HuggingFace on first run (may take a few minutes)
- Sufficient memory for the embedding model (small models need ~1GB, large models need ~4GB+)

## Supported File Types

- PDF (`.pdf`)
- Text files (`.txt`)
- Markdown (`.md`)

