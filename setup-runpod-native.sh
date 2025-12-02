#!/bin/bash

#################################################
# RunPod Native Setup Script (No Docker Required)
# This script sets up the Voice Agent directly on RunPod
# without needing Docker-in-Docker
#################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     AI Voice Agent - RunPod Native Setup                 ║"
echo "║     No Docker Required                                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

print_status() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_info() { echo -e "${BLUE}[i]${NC} $1"; }
print_step() { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }

#################################################
# Step 1: Check GPU
#################################################
print_step "Step 1/8: Checking GPU"

if command -v nvidia-smi &> /dev/null; then
    print_status "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | head -1
    GPU_AVAILABLE=true
else
    print_warning "No NVIDIA GPU detected - will use CPU (slower inference)"
    GPU_AVAILABLE=false
fi

#################################################
# Step 2: Install System Dependencies
#################################################
print_step "Step 2/8: Installing system dependencies"

print_info "Updating package lists..."
apt-get update -qq

print_info "Installing core packages..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    curl wget git ffmpeg \
    build-essential \
    libpq-dev \
    > /dev/null 2>&1

print_status "System dependencies installed"

#################################################
# Step 3: Install PostgreSQL with pgvector
#################################################
print_step "Step 3/8: Setting up PostgreSQL with pgvector"

# Check if PostgreSQL is already installed
if command -v psql &> /dev/null; then
    print_info "PostgreSQL already installed"
else
    print_info "Installing PostgreSQL..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        postgresql postgresql-contrib \
        postgresql-server-dev-all \
        > /dev/null 2>&1
fi

# Install pgvector extension
print_info "Installing pgvector extension..."
if [ ! -d "/tmp/pgvector" ]; then
    cd /tmp
    git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git > /dev/null 2>&1
    cd pgvector
    make > /dev/null 2>&1
    make install > /dev/null 2>&1
    cd "$SCRIPT_DIR"
fi

# Start PostgreSQL
print_info "Starting PostgreSQL..."
service postgresql start 2>/dev/null || true
sleep 3

# Create database and user
print_info "Configuring database..."
sudo -u postgres psql -c "CREATE USER voiceagent WITH PASSWORD 'voiceagent123';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE voiceagent OWNER voiceagent;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE voiceagent TO voiceagent;" 2>/dev/null || true
sudo -u postgres psql -c "ALTER USER voiceagent CREATEDB;" 2>/dev/null || true

# Enable pgvector and create tables
print_info "Creating database schema with vector support..."
sudo -u postgres psql -d voiceagent << 'EOSQL'
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table with vector embeddings
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    file_name TEXT NOT NULL,
    file_type TEXT,
    file_path TEXT,
    file_size BIGINT DEFAULT 0,
    content TEXT,
    embedding vector(768),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'indexed', 'error')),
    error_message TEXT,
    indexed_at DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create vector similarity index
CREATE INDEX IF NOT EXISTS documents_embedding_idx 
ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create status index
CREATE INDEX IF NOT EXISTS documents_status_idx ON documents(status);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Conversation messages table
CREATE TABLE IF NOT EXISTS conversation_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector similarity search function
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id int,
    content text,
    file_name text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        documents.id::int,
        documents.content,
        documents.file_name,
        (1 - (documents.embedding <=> query_embedding))::float as similarity
    FROM documents
    WHERE documents.status = 'indexed'
      AND documents.embedding IS NOT NULL
      AND (1 - (documents.embedding <=> query_embedding)) > match_threshold
    ORDER BY documents.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO voiceagent;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO voiceagent;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO voiceagent;
EOSQL

print_status "PostgreSQL with pgvector configured"

#################################################
# Step 4: Install Ollama
#################################################
print_step "Step 4/8: Installing Ollama"

if command -v ollama &> /dev/null; then
    print_status "Ollama already installed"
else
    print_info "Downloading and installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    print_status "Ollama installed"
fi

# Start Ollama in background
print_info "Starting Ollama server..."
pkill ollama 2>/dev/null || true
sleep 2

# Start with GPU if available
if [ "$GPU_AVAILABLE" = true ]; then
    OLLAMA_HOST=0.0.0.0 nohup ollama serve > /tmp/ollama.log 2>&1 &
else
    OLLAMA_HOST=0.0.0.0 nohup ollama serve > /tmp/ollama.log 2>&1 &
fi
sleep 5

# Verify Ollama is running
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        print_status "Ollama server running"
        break
    fi
    sleep 1
done

#################################################
# Step 5: Pull Ollama Models
#################################################
print_step "Step 5/8: Pulling AI models (this may take 5-15 minutes)"

print_info "Pulling llama3.2:1b (LLM model - ~1.3GB)..."
ollama pull llama3.2:1b || print_warning "Failed to pull llama3.2:1b - will retry later"

print_info "Pulling nomic-embed-text (embedding model - ~274MB)..."
ollama pull nomic-embed-text || print_warning "Failed to pull nomic-embed-text - will retry later"

# Verify models
print_info "Installed models:"
ollama list 2>/dev/null || echo "  (Checking...)"

print_status "AI models ready"

#################################################
# Step 6: Setup Python Environment
#################################################
print_step "Step 6/8: Setting up Python environment"

# Create virtual environment
print_info "Creating Python virtual environment..."
python3 -m venv "$SCRIPT_DIR/venv"
source "$SCRIPT_DIR/venv/bin/activate"

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip -q

# Install Python dependencies
print_info "Installing Python packages..."
pip install -q \
    fastapi==0.109.0 \
    uvicorn==0.27.0 \
    requests==2.31.0 \
    python-dotenv==1.0.0 \
    pydantic==2.5.3 \
    python-multipart==0.0.6 \
    psycopg2-binary==2.9.9 \
    pypdf==4.0.1 \
    watchdog==3.0.0 \
    numpy==1.26.3

# Install whisper for voice recognition (optional - uses more memory)
print_info "Installing OpenAI Whisper for voice recognition..."
pip install -q openai-whisper || print_warning "Whisper installation failed - voice input may not work"

print_status "Python environment ready"

#################################################
# Step 7: Create Configuration
#################################################
print_step "Step 7/8: Creating configuration"

# Create .env file
cat > "$SCRIPT_DIR/.env.runpod" << EOF
# RunPod Native Configuration
DATABASE_URL=postgresql://voiceagent:voiceagent123@localhost:5432/voiceagent
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.2:1b
EMBEDDING_MODEL=nomic-embed-text

# Directories
DOCUMENTS_DIR=$SCRIPT_DIR/documents
FRONTEND_DIR=$SCRIPT_DIR/frontend
WATCH_FOLDER=$SCRIPT_DIR/documents

# Optional: Whisper service URL (if running separately)
# WHISPER_URL=http://localhost:9000
EOF

# Create documents directory
mkdir -p "$SCRIPT_DIR/documents"

print_status "Configuration created at .env.runpod"

#################################################
# Step 8: Create Startup Scripts
#################################################
print_step "Step 8/8: Creating startup scripts"

# Create main startup script
cat > "$SCRIPT_DIR/start-services.sh" << 'STARTEOF'
#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     Starting AI Voice Agent Services                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Start PostgreSQL
echo -e "${BLUE}[i]${NC} Starting PostgreSQL..."
service postgresql start 2>/dev/null || true
sleep 2

# Start Ollama
echo -e "${BLUE}[i]${NC} Starting Ollama..."
pkill ollama 2>/dev/null || true
sleep 1
OLLAMA_HOST=0.0.0.0 nohup ollama serve > /tmp/ollama.log 2>&1 &
sleep 3

# Wait for Ollama
echo -n "    Waiting for Ollama"
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e " ${GREEN}ready${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Load environment
export $(cat "$SCRIPT_DIR/.env.runpod" | grep -v '^#' | xargs)

# Start RAG Indexer in background
echo -e "${BLUE}[i]${NC} Starting RAG Indexer..."
nohup python3 "$SCRIPT_DIR/rag_indexer_native.py" > /tmp/rag-indexer.log 2>&1 &
RAG_PID=$!
echo "    RAG Indexer PID: $RAG_PID"

# Stop nginx if running (it uses port 80)
service nginx stop 2>/dev/null || true
pkill nginx 2>/dev/null || true

# Start Voice Agent API in background (detached mode)
echo -e "${BLUE}[i]${NC} Starting Voice Agent API on port 80..."
nohup python3 -m uvicorn voice_agent_native:app --host 0.0.0.0 --port 80 > /tmp/voice-agent.log 2>&1 &
API_PID=$!
echo "    Voice Agent API PID: $API_PID"

sleep 3

# Verify API is running
if curl -s http://localhost:80/api/health > /dev/null 2>&1; then
    echo -e "    ${GREEN}✓ API is running${NC}"
else
    echo -e "    ${YELLOW}! API may still be starting...${NC}"
fi

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${GREEN}✓ All Services Started (Detached Mode)${NC}                  ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Access URLs:${NC}"
echo "  • Frontend:     http://localhost:80  (or http://localhost)"
echo "  • API Docs:     http://localhost:80/docs"
echo "  • API Health:   http://localhost:80/api/health"
echo "  • Ollama:       http://localhost:11434"
echo ""
echo -e "${GREEN}Default Login:${NC}"
echo "  • Username: admin"
echo "  • Password: admin"
echo ""
echo -e "${GREEN}Logs:${NC}"
echo "  • Voice Agent:  tail -f /tmp/voice-agent.log"
echo "  • Ollama:       tail -f /tmp/ollama.log"
echo "  • RAG Indexer:  tail -f /tmp/rag-indexer.log"
echo ""
echo -e "${GREEN}Check status:${NC}"
echo "  ./check-status.sh"
echo ""
echo -e "${GREEN}Stop services:${NC}"
echo "  ./stop-services.sh"
echo ""
echo -e "${BLUE}[i]${NC} Configure a public endpoint in RunPod for port 80 to access externally"
echo ""
echo -e "${GREEN}All services are running in the background. Terminal is free to use.${NC}"
STARTEOF

chmod +x "$SCRIPT_DIR/start-services.sh"

# Create stop script
cat > "$SCRIPT_DIR/stop-services.sh" << 'STOPEOF'
#!/bin/bash

echo "Stopping AI Voice Agent services..."

# Kill processes
echo "  Stopping Voice Agent API..."
pkill -f "uvicorn voice_agent_native" 2>/dev/null || true

echo "  Stopping RAG Indexer..."
pkill -f "rag_indexer_native" 2>/dev/null || true

echo "  Stopping Ollama..."
pkill ollama 2>/dev/null || true

sleep 2
echo ""
echo "✓ All services stopped."
echo ""
echo "To restart: ./start-services.sh"
STOPEOF

chmod +x "$SCRIPT_DIR/stop-services.sh"

# Create status script
cat > "$SCRIPT_DIR/check-status.sh" << 'STATUSEOF'
#!/bin/bash

echo "=== Service Status ==="
echo ""

# Check PostgreSQL
if service postgresql status > /dev/null 2>&1; then
    echo "✓ PostgreSQL: Running"
else
    echo "✗ PostgreSQL: Not running"
fi

# Check Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama: Running"
    echo "  Models: $(ollama list 2>/dev/null | tail -n +2 | wc -l)"
else
    echo "✗ Ollama: Not running"
fi

# Check Voice Agent API
if curl -s http://localhost:80/api/health > /dev/null 2>&1; then
    echo "✓ Voice Agent API: Running"
else
    echo "✗ Voice Agent API: Not running"
fi

# Check RAG Indexer
if pgrep -f "rag_indexer_native" > /dev/null 2>&1; then
    echo "✓ RAG Indexer: Running"
else
    echo "✗ RAG Indexer: Not running"
fi

echo ""
echo "=== API Status ==="
curl -s http://localhost:80/api/status 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "API not responding"
STATUSEOF

chmod +x "$SCRIPT_DIR/check-status.sh"

print_status "Startup scripts created"

#################################################
# Final Output
#################################################
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${GREEN}✓ Setup Complete!${NC}                                       ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}To start the services:${NC}"
echo "  ./start-services.sh"
echo ""
echo -e "${GREEN}To check status:${NC}"
echo "  ./check-status.sh"
echo ""
echo -e "${GREEN}To stop services:${NC}"
echo "  ./stop-services.sh"
echo ""
echo -e "${GREEN}Available AI Models:${NC}"
ollama list 2>/dev/null || echo "  (Run 'ollama list' after starting)"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "  Configure a public endpoint in RunPod dashboard for port 80"
echo "  to access the application from your browser."
echo ""
