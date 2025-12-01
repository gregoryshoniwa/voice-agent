# AI Voice Agent with n8n, Supabase, and Ollama

This repository contains a complete AI voice agent system that uses RAG (Retrieval-Augmented Generation) to answer questions based on your documents. The system orchestrates speech-to-text, RAG queries, LLM generation, and text-to-speech using n8n workflows.

## 🎯 What This Does

**Voice Agent Flow**: User speaks → Whisper (STT) → n8n → RAG Query → Ollama (LLM) → Piper (TTS) → User hears answer

The system:
- Listens to voice input and converts to text
- Searches your documents using vector similarity
- Generates intelligent answers using LLM with document context
- Converts the answer back to speech

## 🚀 Quick Start

1. **Set up environment variables:**
   ```bash
   cp supabase-project/.env.example supabase-project/.env
   # Edit supabase-project/.env with your secrets
   ```

2. **Prepare directories:**
   ```bash
   mkdir -p piper/models documents n8n-workflows
   ```

3. **Start all services:**
   ```bash
   docker compose -f docker-compose.full.yaml --env-file supabase-project/.env up -d
   ```

4. **Set up Supabase:**
   - Open Supabase Studio at http://localhost:8000
   - Go to SQL Editor
   - Run the SQL from `supabase-project/volumes/db/rag-setup.sql`
   - Run the SQL from `supabase-project/volumes/db/conversations-setup.sql`

5. **Pull Ollama models:**
   ```bash
   docker exec ollama ollama pull llama3.2
   docker exec ollama ollama pull nomic-embed-text
   ```

6. **Import n8n workflows:**
   - Open n8n at http://localhost:5678
   - Import workflows from `n8n-workflows/` folder

7. **Access the dashboard:**
   - Open http://localhost:3001 in your browser
   - Login with username: `admin`, password: `admin`
   - Upload documents in the RAG section
   - View conversation history in the Conversation section

## 📋 Services Included

### Core Services
- **n8n** (Port 5678): Workflow orchestration
- **Supabase** (Port 8000): Vector storage & database
- **Ollama** (Port 11434): LLM & embeddings

### AI/ML Services
- **Whisper** (Port 9000): Speech-to-text
- **Piper** (Port 5500): Text-to-speech
- **RAG Indexer**: Automatic document indexing
- **Voice Agent API** (Port 3001): API for voice agent operations

## 🏗️ Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed architecture documentation.

**Simple Flow:**
```
Audio Input → Whisper → n8n → Voice Agent API → RAG (Supabase) → Ollama → Piper → Audio Output
```

## 📁 Project Structure

```
.
├── docker-compose.full.yaml    # Unified compose file (use this!)
├── ARCHITECTURE.md             # Detailed architecture docs
├── supabase-project/
│   ├── .env                    # Environment variables (DO NOT COMMIT)
│   ├── .env.example           # Template file
│   └── volumes/
│       └── db/
│           └── rag-setup.sql  # RAG database setup
├── rag-indexer/               # Document indexing service
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── voice-agent-api/           # Voice agent API service
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── n8n-workflows/            # n8n workflow configurations
│   ├── voice-agent-main.json
│   ├── rag-query.json
│   └── README.md
├── documents/                 # Documents to index (add your files here)
├── piper/
│   └── models/               # Piper TTS voice models
└── README.md                 # This file
```

## 🔧 Configuration

### Environment Variables

Key variables in `supabase-project/.env`:
- `SERVICE_ROLE_KEY` - Supabase service role key
- `ANON_KEY` - Supabase anonymous key
- `POSTGRES_PASSWORD` - Database password

### Model Configuration

In `docker-compose.full.yaml`:
- `LLM_MODEL` - Ollama LLM model (default: `llama3.2`)
- `EMBEDDING_MODEL` - Ollama embedding model (default: `nomic-embed-text`)
- `PIPER_VOICE` - Piper voice model (default: `en_US-lessac-medium`)

## 📖 Usage

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

### RAG Query Only

```bash
curl -X POST http://localhost:3001/rag-query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is our refund policy?",
    "top_k": 3
  }'
```

## 🛠️ Customization

### Change LLM Model

1. Pull new model: `docker exec ollama ollama pull <model-name>`
2. Update `LLM_MODEL` in docker-compose
3. Restart: `docker compose restart voice-agent-api`

### Customize n8n Workflows

- Edit workflows in n8n UI at http://localhost:5678
- Add custom logic, filtering, logging, etc.
- Export workflows to `n8n-workflows/` folder

### Add More Documents

- Place PDF, TXT, or MD files in `./documents/` folder
- RAG indexer automatically detects and indexes them
- Documents are searchable immediately after indexing

## 🔍 Access Services

- **Frontend Dashboard**: http://localhost:3001
  - Landing page → Login (admin/admin) → Dashboard
  - RAG management and Conversation history
- **n8n**: http://localhost:5678
  - Username: `admin`
  - Password: `changeme123` (change this!)
- **Supabase Studio**: http://localhost:8000
- **Voice Agent API**: http://localhost:3001/api/docs (API documentation)
- **Whisper API**: http://localhost:9000
- **Piper API**: http://localhost:5500
- **Ollama API**: http://localhost:11434

## 🛑 Stopping Services

```bash
docker compose -f docker-compose.full.yaml down
```

## 🔄 Resetting Everything

```bash
docker compose -f docker-compose.full.yaml down -v
rm -rf supabase-project/volumes/db/data/*
docker compose -f docker-compose.full.yaml --env-file supabase-project/.env up -d
```

## ⚠️ Important Notes

- **Never commit `.env` files** - they contain secrets
- Database data is stored in `supabase-project/volumes/db/data/` (excluded from git)
- Storage files are in Docker volume `storage_data` (not in git)
- All services share the `supabase_network` network for easy communication
- **Ollama models** must be pulled before first use
- Place documents in `./documents/` folder for automatic indexing
- Download Piper voice models to `./piper/models/` if needed

## 📚 Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Detailed architecture and data flow
- [n8n-workflows/README.md](./n8n-workflows/README.md) - n8n workflow documentation
- [rag-indexer/README.md](./rag-indexer/README.md) - RAG indexer documentation

## 🐛 Troubleshooting

### Ollama models not found
```bash
docker exec ollama ollama list  # Check available models
docker exec ollama ollama pull llama3.2  # Pull required model
```

### RAG indexer not working
- Check Ollama is running: `docker ps | grep ollama`
- Check logs: `docker logs rag-indexer`
- Verify documents folder exists: `ls -la documents/`

### n8n workflows not triggering
- Check webhook URL is correct
- Verify n8n is accessible: http://localhost:5678
- Check workflow is active in n8n UI
