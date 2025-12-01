# AI Voice Agent Architecture

## Overview

This system implements a complete AI voice agent that uses RAG (Retrieval-Augmented Generation) to answer questions based on your documents.

## Architecture Flow

```
User Voice Input
    ↓
[Whisper STT] → Transcribes audio to text
    ↓
[n8n Workflow] → Orchestrates the flow
    ↓
[Voice Agent API] → Processes the request
    ↓
[RAG Query] → Searches Supabase vector store for relevant documents
    ↓
[Ollama LLM] → Generates answer using context from RAG
    ↓
[Piper TTS] → Converts text response to speech
    ↓
Audio Response to User
```

## Components

### 1. **Whisper (Speech-to-Text)**
- **Service**: `whisper-stt`
- **Port**: 9000
- **Purpose**: Converts audio input to text
- **Language**: English (configurable)

### 2. **n8n (Workflow Orchestration)**
- **Service**: `n8n_automation`
- **Port**: 5678
- **Purpose**: Orchestrates the entire voice agent flow
- **Workflows**: Located in `n8n-workflows/` folder
- **Webhooks**: 
  - `/webhook/voice-agent` - Main voice agent endpoint
  - `/webhook/rag-query` - Direct RAG query endpoint

### 3. **Voice Agent API**
- **Service**: `voice-agent-api`
- **Port**: 3001
- **Purpose**: Provides API endpoints for voice agent operations
- **Endpoints**:
  - `POST /transcribe` - Audio to text
  - `POST /rag-query` - Query RAG system
  - `POST /synthesize` - Text to speech
  - `POST /voice-agent/process` - Complete flow

### 4. **Supabase (Vector Storage & Database)**
- **Service**: Multiple services (Kong, PostgreSQL, etc.)
- **Port**: 8000 (Kong API Gateway)
- **Purpose**: 
  - Stores document embeddings
  - Provides vector similarity search
  - Database for application data
- **Table**: `documents` - Stores indexed documents with embeddings

### 5. **RAG Indexer**
- **Service**: `rag-indexer`
- **Purpose**: Watches `./documents/` folder and indexes documents
- **Process**:
  1. Detects new/modified files (PDF, TXT, MD)
  2. Extracts text
  3. Generates embeddings using Ollama
  4. Stores in Supabase

### 6. **Ollama (LLM & Embeddings)**
- **Service**: `ollama`
- **Port**: 11434
- **Purpose**: 
  - Generates embeddings for documents and queries
  - Generates LLM responses with RAG context
- **Models Used**:
  - Embedding: `nomic-embed-text` (768 dimensions)
  - LLM: `llama3.2` (configurable)

### 7. **Piper (Text-to-Speech)**
- **Service**: `piper-tts`
- **Port**: 5500
- **Purpose**: Converts text responses to speech audio
- **Voice**: `en_US-lessac-medium` (configurable)

## Data Flow Example

### User asks: "What is our refund policy?"

1. **Audio Input** → User records question
2. **Whisper** → "What is our refund policy?"
3. **n8n** → Receives text, triggers voice agent workflow
4. **Voice Agent API** → Processes request
5. **RAG Query**:
   - Gets embedding for "What is our refund policy?"
   - Searches Supabase for similar document chunks
   - Finds relevant policy documents
6. **Ollama LLM** → Generates answer using found context:
   - "Based on our policy documents, our refund policy states..."
7. **Piper TTS** → Converts answer to audio
8. **Response** → Audio file returned to user

## Network Architecture

All services are on the `supabase_network` Docker network:

```
supabase_network
├── n8n_automation
├── voice-agent-api
├── whisper-stt
├── piper-tts
├── ollama
├── rag-indexer
└── supabase services (kong, db, etc.)
```

## Configuration

### Environment Variables

Key environment variables in `supabase-project/.env`:
- `SERVICE_ROLE_KEY` - Supabase service role key
- `ANON_KEY` - Supabase anonymous key

### Model Configuration

In `docker-compose.full.yaml`:
- `LLM_MODEL` - Ollama LLM model (default: `llama3.2`)
- `EMBEDDING_MODEL` - Ollama embedding model (default: `nomic-embed-text`)
- `PIPER_VOICE` - Piper voice model (default: `en_US-lessac-medium`)

## Setup Steps

1. **Start all services**:
   ```bash
   docker compose -f docker-compose.full.yaml --env-file supabase-project/.env up -d
   ```

2. **Set up Supabase RAG**:
   - Run `supabase-project/volumes/db/rag-setup.sql` in Supabase SQL Editor
   - Or it will be auto-run on database init

3. **Pull Ollama models**:
   ```bash
   docker exec ollama ollama pull llama3.2
   docker exec ollama ollama pull nomic-embed-text
   ```

4. **Import n8n workflows**:
   - Open n8n at http://localhost:5678
   - Import workflows from `n8n-workflows/` folder

5. **Add documents**:
   - Place PDF, TXT, or MD files in `./documents/` folder
   - RAG indexer will automatically index them

## Usage

### Via n8n Webhook

```bash
curl -X POST http://localhost:5678/webhook/voice-agent \
  -H "Content-Type: application/json" \
  -d '{
    "audio_url": "https://example.com/audio.wav"
  }'
```

### Direct API Call

```bash
curl -X POST http://localhost:3001/voice-agent/process \
  -H "Content-Type: application/json" \
  -d '{
    "audio_url": "https://example.com/audio.wav"
  }'
```

## Customization

### Change LLM Model

1. Pull new model: `docker exec ollama ollama pull <model-name>`
2. Update `LLM_MODEL` in docker-compose
3. Restart: `docker compose restart voice-agent-api`

### Change Embedding Model

1. Pull new model: `docker exec ollama ollama pull <model-name>`
2. Update `EMBEDDING_MODEL` in docker-compose
3. Update vector dimension in `rag-setup.sql` if needed
4. Restart services

### Customize n8n Workflows

- Edit workflows in n8n UI at http://localhost:5678
- Export workflows to `n8n-workflows/` folder
- Workflows can add custom logic, filtering, logging, etc.

