# AI Voice Agent - RunPod Native

An intelligent voice/text chat agent with RAG (Retrieval Augmented Generation) capabilities. Ask questions and get answers from your uploaded documents.

## Features

- 🎤 **Voice & Text Chat** - Ask questions via voice or text
- 📄 **Document RAG** - Upload PDFs, TXT, DOCX files for context-aware answers
- 🧠 **Local LLM** - Uses Ollama with Llama 3.2 (runs on GPU)
- 🔍 **Vector Search** - PostgreSQL + pgvector for semantic document search
- 🖥️ **Web Interface** - Clean dashboard for chat and document management

## Quick Start (RunPod)

### 1. Create a RunPod GPU Pod

- Go to [RunPod.io](https://runpod.io)
- Create a new pod with GPU (RTX A5000, A40, etc.)
- Use Ubuntu/PyTorch template

### 2. Connect via SSH and Clone

```bash
cd /workspace
git clone https://github.com/gregoryshoniwa/voice-agent.git
cd voice-agent
```

### 3. Run Setup

```bash
chmod +x setup-runpod-native.sh
./setup-runpod-native.sh
```

This installs:
- PostgreSQL with pgvector
- Ollama with GPU support
- LLM model (llama3.2:1b)
- Embedding model (nomic-embed-text)
- Python dependencies

### 4. Start Services

```bash
./start-services.sh
```

### 5. Access the App

- Configure a public endpoint for port **80** in RunPod console
- Or access via `http://localhost:80` from within the pod

**Default Login:** admin / admin

## Project Structure

```
voice-agent/
├── voice_agent_native.py    # Main API server
├── rag_indexer_native.py    # Document indexer with embeddings
├── setup-runpod-native.sh   # Setup script for RunPod
├── frontend/                # Web interface
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── documents/               # Upload directory
├── .env.runpod             # Configuration (created by setup)
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/status` | GET | Service status |
| `/api/chat` | POST | Text chat with RAG |
| `/api/voice-chat` | POST | Voice chat (audio input) |
| `/api/rag-query` | POST | Direct RAG query |
| `/api/documents` | GET | List documents |
| `/api/documents/upload` | POST | Upload document |
| `/api/conversations` | GET | List conversations |

## Configuration

Edit `.env.runpod`:

```env
DATABASE_URL=postgresql://voiceagent:voiceagent123@localhost:5432/voiceagent
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=gpt-oss:latest
EMBEDDING_MODEL=nomic-embed-text
TTS_VOICE=en-US-AriaNeural
```

### System Prompt (Batsi Personality)

The agent uses a built-in system prompt that gives it the personality of **Batsi** - a helpful Zimbabwean banking support agent for Steward Bank. This prompt includes:

- Personality traits (smart, approachable, empathetic)
- Knowledge of Steward Bank services
- Zimbabwean cultural context
- Professional tone guidelines
- Safety guardrails

To customize the system prompt, set the `SYSTEM_PROMPT` environment variable in `.env.runpod`:

```env
SYSTEM_PROMPT="Your custom prompt here..."
```

Or check the current prompt via API:
```bash
curl http://localhost:80/api/system-prompt
```

## Useful Commands

```bash
# Check service status
./check-status.sh

# Stop all services
./stop-services.sh

# View logs
tail -f /tmp/ollama.log
tail -f /tmp/rag-indexer.log

# List Ollama models
ollama list

# Pull a different model
ollama pull llama3.2  # Larger, better quality
```

## Supported Document Types

- PDF (.pdf)
- Text (.txt)
- Markdown (.md)
- Word Documents (.docx)
- JSON (.json)
- CSV (.csv)

## Requirements

- Python 3.10+
- PostgreSQL with pgvector extension
- Ollama
- NVIDIA GPU (recommended for faster inference)

## License

MIT
