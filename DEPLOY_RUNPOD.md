# Deploying AI Voice Agent to RunPod Server

## Prerequisites

Your RunPod server should have:
- GPU: A40 (or similar)
- Docker installed
- Docker Compose installed
- Internet access

## Step 1: Connect to Your RunPod Server

```bash
# SSH into your RunPod server
ssh root@<your-runpod-ip>
```

## Step 2: Install Docker & Docker Compose (if not already installed)

```bash
# Update system
apt-get update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose V2
apt-get install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

## Step 3: Clone or Transfer Your Code

### Option A: If you have Git access
```bash
cd /workspace
git clone <your-repo-url> batsi-4.0-ai-voice-agent-rag
cd batsi-4.0-ai-voice-agent-rag
```

### Option B: Transfer files from your local machine
```bash
# On your local machine, create a tarball
cd /path/to/Batsi\ 4.0
tar -czf batsi-4.0.tar.gz --exclude='.git' --exclude='node_modules' --exclude='__pycache__' .

# Transfer to RunPod
scp batsi-4.0.tar.gz root@<runpod-ip>:/workspace/

# On RunPod server
cd /workspace
tar -xzf batsi-4.0.tar.gz
cd batsi-4.0-ai-voice-agent-rag
```

## Step 4: Configure Environment

```bash
# Copy environment file
cp supabase-project/.env.dev supabase-project/.env

# Edit if needed (check POSTGRES_PORT, etc.)
nano supabase-project/.env
```

## Step 5: Update Ports for RunPod

RunPod might have different port requirements. Check your RunPod network settings and update if needed:

```bash
# Check what ports are available
netstat -tuln | grep LISTEN

# If port 3002 is taken, update docker-compose.full.yaml
# Change: "3002:3001" to something else like "3003:3001"
```

## Step 6: Enable GPU Support for Ollama (Important!)

Since you have an A40 GPU, we should use it for faster inference:

```bash
# Edit docker-compose.full.yaml
nano docker-compose.full.yaml

# Find the ollama service and uncomment GPU section:
# ollama:
#   ...
#   deploy:
#     resources:
#       reservations:
#         devices:
#           - driver: nvidia
#             count: 1
#             capabilities: [gpu]
```

## Step 7: Run Setup

```bash
# Make scripts executable
chmod +x setup.sh stop.sh logs.sh status.sh init-rag.sh

# Run setup (this will take 10-20 minutes)
./setup.sh

# Or skip model pulling if you want faster setup
./setup.sh --skip-models
```

## Step 8: Access Your Application

After setup completes, you'll see URLs like:
- Frontend: `http://<runpod-ip>:3002`
- n8n: `http://<runpod-ip>:5678`
- Supabase Studio: `http://<runpod-ip>:8000`

**Important:** RunPod might require you to:
1. Create a Public Endpoint in RunPod dashboard
2. Or use their port forwarding feature

## Step 9: Pull Ollama Models (with GPU acceleration)

```bash
# Pull models (will use GPU automatically)
docker exec ollama ollama pull llama3.2:1b
docker exec ollama ollama pull nomic-embed-text

# Verify GPU is being used
docker exec ollama nvidia-smi
```

## Step 10: Initialize RAG System

```bash
# Initialize database tables
./init-rag.sh

# Or manually:
docker exec -i supabase-db psql -U postgres -d postgres < supabase-project/volumes/db/rag-setup.sql
docker exec -i supabase-db psql -U postgres -d postgres < supabase-project/volumes/db/conversations-setup.sql
```

## Troubleshooting

### Check container status
```bash
./status.sh
```

### View logs
```bash
./logs.sh
# Or specific service
./logs.sh voice-agent-api
./logs.sh ollama
```

### Restart services
```bash
./stop.sh
./setup.sh
```

### Check GPU usage
```bash
nvidia-smi
docker exec ollama nvidia-smi
```

## Performance Tips

1. **Use GPU for Ollama** - Much faster inference
2. **Use smaller models** - `llama3.2:1b` is good for CPU, but with GPU you can use `llama3.2` (2GB) or even `llama3.1:8b` for better quality
3. **Monitor GPU memory** - A40 has 48GB, so you have plenty of room

## Next Steps

1. Upload documents via the web interface
2. Test chat functionality
3. Configure n8n workflows if needed
4. Set up public endpoints in RunPod dashboard for external access

