# n8n Workflows for Voice Agent

This folder contains n8n workflow configurations for the AI voice agent system.

## Workflow Structure

### 1. Voice Agent Main Workflow (`voice-agent-main.json`)
Main workflow that orchestrates the complete voice agent flow:
- Receives audio input (webhook)
- Calls Whisper for STT
- Calls RAG query
- Calls Ollama for LLM response
- Calls Piper for TTS
- Returns audio response

### 2. RAG Query Workflow (`rag-query.json`)
Standalone workflow for RAG queries:
- Takes text query
- Searches Supabase vector store
- Returns relevant documents

### 3. Document Indexing Workflow (`document-indexing.json`)
Workflow to manually trigger document indexing:
- Monitors document uploads
- Triggers RAG indexer
- Validates indexing

## Importing Workflows

1. Open n8n at http://localhost:5678
2. Click "Import from File" or "Import from URL"
3. Select the workflow JSON file
4. Configure the credentials:
   - Supabase API credentials
   - Voice Agent API endpoint
   - Ollama endpoint

## Workflow Endpoints

After importing, workflows will be available at:
- `http://localhost:5678/webhook/voice-agent` - Main voice agent endpoint
- `http://localhost:5678/webhook/rag-query` - RAG query endpoint

## Configuration

Update the following in each workflow:
- **Supabase URL**: `http://kong:8000`
- **Supabase Service Role Key**: From `.env` file
- **Voice Agent API**: `http://voice-agent-api:3001`
- **Ollama URL**: `http://ollama:11434`

