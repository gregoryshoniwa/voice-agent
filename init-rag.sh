#!/bin/bash

#################################################
# Initialize RAG System
# This script sets up the database tables and
# triggers reindexing of existing documents
#################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}"
echo "================================================"
echo "   RAG System Initialization"
echo "================================================"
echo -e "${NC}"

# Check if database is ready
echo -e "${BLUE}[i]${NC} Checking database connection..."
for i in {1..30}; do
    if docker exec supabase-db pg_isready -U postgres -h localhost &>/dev/null; then
        echo -e "${GREEN}[✓]${NC} Database is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}[✗]${NC} Database is not ready after 60 seconds"
        exit 1
    fi
    echo -n "."
    sleep 2
done

# Initialize RAG tables
echo -e "${BLUE}[i]${NC} Initializing RAG tables..."
if [ -f "$SCRIPT_DIR/supabase-project/volumes/db/rag-setup.sql" ]; then
    docker exec -i supabase-db psql -U postgres -d postgres < "$SCRIPT_DIR/supabase-project/volumes/db/rag-setup.sql" 2>&1 || true
    echo -e "${GREEN}[✓]${NC} RAG tables initialized"
else
    echo -e "${RED}[✗]${NC} rag-setup.sql not found"
fi

# Initialize conversations tables
echo -e "${BLUE}[i]${NC} Initializing conversations tables..."
if [ -f "$SCRIPT_DIR/supabase-project/volumes/db/conversations-setup.sql" ]; then
    docker exec -i supabase-db psql -U postgres -d postgres < "$SCRIPT_DIR/supabase-project/volumes/db/conversations-setup.sql" 2>&1 || true
    echo -e "${GREEN}[✓]${NC} Conversations tables initialized"
else
    echo -e "${RED}[✗]${NC} conversations-setup.sql not found"
fi

# Check if Ollama is ready and has the embedding model
echo -e "${BLUE}[i]${NC} Checking Ollama..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        echo -e "${GREEN}[✓]${NC} Ollama is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}[!]${NC} Ollama not ready, continuing..."
    fi
    echo -n "."
    sleep 2
done

# Check if embedding model is available
echo -e "${BLUE}[i]${NC} Checking embedding model..."
MODELS=$(curl -s http://localhost:11434/api/tags 2>/dev/null || echo "{}")
if echo "$MODELS" | grep -q "nomic-embed-text"; then
    echo -e "${GREEN}[✓]${NC} Embedding model (nomic-embed-text) is available"
else
    echo -e "${YELLOW}[!]${NC} Embedding model not found. Pulling nomic-embed-text..."
    docker exec ollama ollama pull nomic-embed-text || echo -e "${YELLOW}[!]${NC} Failed to pull model"
fi

# Restart RAG indexer to process existing documents
echo -e "${BLUE}[i]${NC} Restarting RAG indexer to process documents..."
docker restart rag-indexer 2>/dev/null || true
echo -e "${GREEN}[✓]${NC} RAG indexer restarted"

# List documents in the documents folder
echo ""
echo -e "${BLUE}[i]${NC} Documents in ./documents folder:"
ls -la "$SCRIPT_DIR/documents/" 2>/dev/null || echo "No documents found"

# Show RAG indexer logs
echo ""
echo -e "${BLUE}[i]${NC} RAG Indexer logs (last 20 lines):"
docker logs --tail 20 rag-indexer 2>&1 || echo "Could not get logs"

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}   RAG Initialization Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Upload documents via the web interface at http://localhost:3002"
echo "  2. Or copy files directly to the ./documents folder"
echo "  3. Check RAG indexer logs: docker logs -f rag-indexer"
echo "  4. Query documents in the Chat tab"
echo ""

