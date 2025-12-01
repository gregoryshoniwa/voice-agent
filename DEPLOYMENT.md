# Deployment Guide - Linux Server

This guide walks you through deploying the AI Voice Agent on a Linux server.

## Prerequisites

### Server Requirements
- **OS**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+ / Rocky Linux 8+
- **RAM**: Minimum 8GB (16GB+ recommended for Ollama models)
- **Storage**: 50GB+ free space
- **CPU**: 4+ cores recommended
- **Ports**: 3001, 5678, 8000, 11434, 9000, 5500 (or configure firewall)

### Required Software
- Docker Engine 20.10+
- Docker Compose V2+
- Git

---

## Step 1: Install Docker on Linux

### Ubuntu/Debian
```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install prerequisites
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add current user to docker group (logout/login required)
sudo usermod -aG docker $USER

# Start Docker
sudo systemctl enable docker
sudo systemctl start docker
```

### CentOS/Rocky Linux
```bash
# Install prerequisites
sudo yum install -y yum-utils

# Add Docker repository
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# Install Docker
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER

# Start Docker
sudo systemctl enable docker
sudo systemctl start docker
```

### Verify Installation
```bash
docker --version
docker compose version
```

---

## Step 2: Clone from GitLab

```bash
# Navigate to your preferred directory
cd /opt  # or /home/yourusername

# Clone the repository
git clone https://gitlab.com/YOUR_USERNAME/YOUR_REPO_NAME.git voice-agent

# Enter the project directory
cd voice-agent
```

---

## Step 3: Configure Environment

```bash
# Copy the example environment file
cp supabase-project/.env.example supabase-project/.env

# Edit with your production secrets
nano supabase-project/.env
```

### Generate Secure Secrets

```bash
# Generate random secrets (run these commands)
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)"
echo "JWT_SECRET=$(openssl rand -base64 48)"
echo "SECRET_KEY_BASE=$(openssl rand -base64 64)"
echo "VAULT_ENC_KEY=$(openssl rand -hex 16)"
echo "PG_META_CRYPTO_KEY=$(openssl rand -hex 16)"
echo "LOGFLARE_PUBLIC_ACCESS_TOKEN=$(openssl rand -base64 32)"
echo "LOGFLARE_PRIVATE_ACCESS_TOKEN=$(openssl rand -base64 32)"
```

### Important `.env` Settings to Change

```bash
# Required - Generate new values using commands above
POSTGRES_PASSWORD=<generated-password>
JWT_SECRET=<generated-jwt-secret>
SECRET_KEY_BASE=<generated-secret-key>
VAULT_ENC_KEY=<generated-vault-key>
PG_META_CRYPTO_KEY=<generated-crypto-key>

# Dashboard credentials
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=<strong-password>

# API URLs - Update with your server IP or domain
SITE_URL=http://YOUR_SERVER_IP:3000
API_EXTERNAL_URL=http://YOUR_SERVER_IP:8000
SUPABASE_PUBLIC_URL=http://YOUR_SERVER_IP:8000

# Logflare tokens
LOGFLARE_PUBLIC_ACCESS_TOKEN=<generated-token>
LOGFLARE_PRIVATE_ACCESS_TOKEN=<generated-token>
```

### Generate Supabase JWT Keys

You need to generate proper JWT keys. Visit: https://supabase.com/docs/guides/self-hosting#api-keys

Or use this script:
```bash
# Install jwt-cli (or use online generator)
# Generate ANON_KEY and SERVICE_ROLE_KEY based on your JWT_SECRET
```

---

## Step 4: Create Required Directories

```bash
# Create directories
mkdir -p documents piper/models n8n-workflows

# Set permissions
chmod -R 755 documents piper
```

---

## Step 5: Start Services

```bash
# Pull images and start all services
docker compose -f docker-compose.full.yaml --env-file supabase-project/.env up -d

# Watch the logs (optional)
docker compose -f docker-compose.full.yaml logs -f
```

Wait 3-5 minutes for all services to initialize.

---

## Step 6: Initialize Database

```bash
# Wait for database to be ready
sleep 60

# Run RAG setup SQL
docker exec -i supabase-db psql -U postgres -d postgres < supabase-project/volumes/db/rag-setup.sql

# Run conversations setup SQL  
docker exec -i supabase-db psql -U postgres -d postgres < supabase-project/volumes/db/conversations-setup.sql
```

Or manually via Supabase Studio:
1. Open http://YOUR_SERVER_IP:8000
2. Go to SQL Editor
3. Run the SQL files

---

## Step 7: Pull Ollama Models

```bash
# Pull the LLM model (this may take 10-20 minutes)
docker exec ollama ollama pull llama3.2

# Pull the embedding model
docker exec ollama ollama pull nomic-embed-text

# Verify models
docker exec ollama ollama list
```

---

## Step 8: Import n8n Workflows (Optional)

1. Open n8n at http://YOUR_SERVER_IP:5678
2. Login with `admin` / `changeme123`
3. Import workflows from `n8n-workflows/` folder

---

## Step 9: Verify Installation

### Check All Services
```bash
docker compose -f docker-compose.full.yaml ps
```

All services should show "Up" or "healthy".

### Test Endpoints
```bash
# Test Voice Agent API
curl http://localhost:3001/api/health

# Test Ollama
curl http://localhost:11434/api/tags

# Test RAG Query
curl -X POST http://localhost:3001/api/rag-query \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello", "top_k": 3}'
```

---

## Step 10: Configure Firewall (Production)

```bash
# Ubuntu/Debian (UFW)
sudo ufw allow 3001/tcp  # Voice Agent API / Frontend
sudo ufw allow 5678/tcp  # n8n (optional - internal only)
sudo ufw allow 8000/tcp  # Supabase (optional - internal only)
sudo ufw enable

# CentOS/Rocky (firewalld)
sudo firewall-cmd --permanent --add-port=3001/tcp
sudo firewall-cmd --reload
```

**Security Note**: For production, use a reverse proxy (nginx/traefik) with SSL.

---

## Access URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend Dashboard | http://YOUR_IP:3001 | admin / admin |
| n8n Workflows | http://YOUR_IP:5678 | admin / changeme123 |
| Supabase Studio | http://YOUR_IP:8000 | as configured |
| Voice Agent API | http://YOUR_IP:3001/api/docs | - |

---

## Maintenance Commands

### View Logs
```bash
# All services
docker compose -f docker-compose.full.yaml logs -f

# Specific service
docker compose -f docker-compose.full.yaml logs -f voice-agent-api
```

### Restart Services
```bash
docker compose -f docker-compose.full.yaml restart
```

### Stop Services
```bash
docker compose -f docker-compose.full.yaml down
```

### Update Application
```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.full.yaml down
docker compose -f docker-compose.full.yaml --env-file supabase-project/.env up -d --build
```

### Backup Database
```bash
docker exec supabase-db pg_dump -U postgres postgres > backup_$(date +%Y%m%d).sql
```

### Reset Everything
```bash
docker compose -f docker-compose.full.yaml down -v
rm -rf supabase-project/volumes/db/data/*
docker compose -f docker-compose.full.yaml --env-file supabase-project/.env up -d
```

---

## Troubleshooting

### Services Not Starting
```bash
# Check logs for errors
docker compose -f docker-compose.full.yaml logs --tail=100

# Check system resources
free -h
df -h
```

### Ollama Out of Memory
- Ensure server has 8GB+ RAM
- Use smaller models: `llama3.2:1b` instead of `llama3.2`

### Database Connection Issues
```bash
# Check if database is healthy
docker exec supabase-db pg_isready -U postgres
```

### Permission Issues
```bash
# Fix volume permissions
sudo chown -R 1000:1000 supabase-project/volumes/
sudo chown -R 1000:1000 documents/
```

---

## Production Recommendations

1. **Use HTTPS**: Set up nginx/traefik reverse proxy with Let's Encrypt SSL
2. **Change Default Passwords**: Update all default credentials
3. **Backup Strategy**: Set up automated database backups
4. **Monitoring**: Add Prometheus/Grafana for monitoring
5. **Resource Limits**: Configure Docker resource limits in compose file
6. **Log Rotation**: Configure Docker log rotation

---

## Quick Reference

```bash
# Start
docker compose -f docker-compose.full.yaml --env-file supabase-project/.env up -d

# Stop
docker compose -f docker-compose.full.yaml down

# Logs
docker compose -f docker-compose.full.yaml logs -f

# Status
docker compose -f docker-compose.full.yaml ps
```

