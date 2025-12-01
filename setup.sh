#!/bin/bash

#################################################
# AI Voice Agent - Setup Script
# This script sets up and runs the full stack
#################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}"
echo "================================================"
echo "   AI Voice Agent - Setup Script"
echo "================================================"
echo -e "${NC}"

#################################################
# Functions
#################################################

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        echo "  Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi
    
    print_status "Docker is installed and running"
}

check_docker_compose() {
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
        print_status "Docker Compose V2 found"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
        print_status "Docker Compose V1 found"
    else
        print_error "Docker Compose is not installed."
        exit 1
    fi
}

create_env_file() {
    ENV_FILE="$SCRIPT_DIR/supabase-project/.env"
    ENV_DEV_FILE="$SCRIPT_DIR/supabase-project/.env.dev"
    
    if [ -f "$ENV_FILE" ]; then
        print_warning ".env file already exists"
        read -p "Do you want to overwrite it with .env.dev? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing .env file"
            return
        fi
    fi
    
    if [ -f "$ENV_DEV_FILE" ]; then
        cp "$ENV_DEV_FILE" "$ENV_FILE"
        print_status "Created .env from .env.dev"
    else
        print_error ".env.dev file not found at $ENV_DEV_FILE"
        exit 1
    fi
}

create_directories() {
    print_info "Creating required directories..."
    
    mkdir -p "$SCRIPT_DIR/documents"
    mkdir -p "$SCRIPT_DIR/piper/models"
    mkdir -p "$SCRIPT_DIR/n8n-workflows"
    
    # Create .gitkeep files
    touch "$SCRIPT_DIR/documents/.gitkeep" 2>/dev/null || true
    touch "$SCRIPT_DIR/piper/models/.gitkeep" 2>/dev/null || true
    
    print_status "Directories created"
}

stop_existing_containers() {
    print_info "Stopping any existing containers..."
    $COMPOSE_CMD -f docker-compose.full.yaml --env-file supabase-project/.env down 2>/dev/null || true
    print_status "Existing containers stopped"
}

start_services() {
    print_info "Starting all services (this may take a few minutes)..."
    $COMPOSE_CMD -f docker-compose.full.yaml --env-file supabase-project/.env up -d --build
    print_status "Services started"
}

wait_for_services() {
    print_info "Waiting for services to be ready..."
    
    # Wait for database
    echo -n "  Waiting for database"
    for i in {1..60}; do
        if docker exec supabase-db pg_isready -U postgres -h localhost &>/dev/null; then
            echo -e " ${GREEN}ready${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Wait for Ollama
    echo -n "  Waiting for Ollama"
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags &>/dev/null; then
            echo -e " ${GREEN}ready${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Wait for Kong/Supabase API
    echo -n "  Waiting for Supabase API"
    for i in {1..30}; do
        if curl -s http://localhost:8000/rest/v1/ &>/dev/null; then
            echo -e " ${GREEN}ready${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    print_status "Core services are ready"
}

setup_database() {
    print_info "Setting up database tables..."
    
    # RAG setup
    if [ -f "$SCRIPT_DIR/supabase-project/volumes/db/rag-setup.sql" ]; then
        docker exec -i supabase-db psql -U postgres -d postgres < "$SCRIPT_DIR/supabase-project/volumes/db/rag-setup.sql" 2>/dev/null || true
        print_status "RAG tables created"
    fi
    
    # Conversations setup
    if [ -f "$SCRIPT_DIR/supabase-project/volumes/db/conversations-setup.sql" ]; then
        docker exec -i supabase-db psql -U postgres -d postgres < "$SCRIPT_DIR/supabase-project/volumes/db/conversations-setup.sql" 2>/dev/null || true
        print_status "Conversations tables created"
    fi
    
    # Restart RAG indexer to process any existing documents
    print_info "Restarting RAG indexer to process documents..."
    docker restart rag-indexer 2>/dev/null || true
    print_status "RAG indexer restarted"
}

pull_ollama_models() {
    print_info "Pulling Ollama models (this may take 5-10 minutes)..."
    
    echo "  Pulling llama3.2:1b (smaller, faster on CPU)..."
    docker exec ollama ollama pull llama3.2:1b || print_warning "Failed to pull llama3.2:1b"
    
    echo "  Pulling nomic-embed-text..."
    docker exec ollama ollama pull nomic-embed-text || print_warning "Failed to pull nomic-embed-text"
    
    print_status "Ollama models pulled"
}

show_status() {
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${GREEN}   Setup Complete!${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
    echo -e "${YELLOW}Service URLs:${NC}"
    echo "  • Frontend Dashboard:  http://localhost:3002"
    echo "  • n8n Workflows:       http://localhost:5678"
    echo "  • Supabase Studio:     http://localhost:8000"
    echo "  • Voice Agent API:     http://localhost:3002/api/docs"
    echo ""
    echo -e "${YELLOW}Default Credentials:${NC}"
    echo "  • Frontend:  admin / admin"
    echo "  • n8n:       admin / changeme123"
    echo "  • Supabase:  supabase / Developer2024"
    echo ""
    echo -e "${YELLOW}Useful Commands:${NC}"
    echo "  • View logs:     $COMPOSE_CMD -f docker-compose.full.yaml --env-file supabase-project/.env logs -f"
    echo "  • Stop services: $COMPOSE_CMD -f docker-compose.full.yaml --env-file supabase-project/.env down"
    echo "  • Restart:       $COMPOSE_CMD -f docker-compose.full.yaml --env-file supabase-project/.env restart"
    echo ""
    echo -e "${YELLOW}Container Status:${NC}"
    $COMPOSE_CMD -f docker-compose.full.yaml ps --format "table {{.Name}}\t{{.Status}}"
    echo ""
}

#################################################
# Main Script
#################################################

# Parse arguments
SKIP_MODELS=false
SKIP_DB=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-models)
            SKIP_MODELS=true
            shift
            ;;
        --skip-db)
            SKIP_DB=true
            shift
            ;;
        --force|-f)
            FORCE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-models    Skip pulling Ollama models"
            echo "  --skip-db        Skip database initialization"
            echo "  --force, -f      Force overwrite .env without asking"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run setup steps
echo ""
print_info "Step 1/7: Checking Docker..."
check_docker
check_docker_compose

echo ""
print_info "Step 2/7: Creating environment file..."
if [ "$FORCE" = true ]; then
    cp "$SCRIPT_DIR/supabase-project/.env.dev" "$SCRIPT_DIR/supabase-project/.env"
    print_status "Created .env from .env.dev (forced)"
else
    create_env_file
fi

echo ""
print_info "Step 3/7: Creating directories..."
create_directories

echo ""
print_info "Step 4/7: Stopping existing containers..."
stop_existing_containers

echo ""
print_info "Step 5/7: Starting services..."
start_services

echo ""
print_info "Step 6/7: Waiting for services..."
wait_for_services

if [ "$SKIP_DB" = false ]; then
    echo ""
    print_info "Step 7a/7: Setting up database..."
    setup_database
fi

if [ "$SKIP_MODELS" = false ]; then
    echo ""
    print_info "Step 7b/7: Pulling Ollama models..."
    pull_ollama_models
fi

# Show final status
show_status

