#!/bin/bash

#################################################
# AI Voice Agent - Status Script
#################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo ""
echo "=== Container Status ==="
echo ""
$COMPOSE_CMD -f docker-compose.full.yaml --env-file supabase-project/.env ps

echo ""
echo "=== Service Health ==="
echo ""

# Check each service
check_service() {
    local name=$1
    local url=$2
    if curl -s --max-time 2 "$url" &>/dev/null; then
        echo "  ✓ $name is running"
    else
        echo "  ✗ $name is not responding"
    fi
}

check_service "Voice Agent API" "http://localhost:3002/api/health"
check_service "Supabase API" "http://localhost:8000/rest/v1/"
check_service "Ollama" "http://localhost:11434/api/tags"
check_service "n8n" "http://localhost:5678"
check_service "Whisper STT" "http://localhost:9000"

echo ""
echo "=== Ollama Models ==="
docker exec ollama ollama list 2>/dev/null || echo "  Ollama not running"

echo ""
