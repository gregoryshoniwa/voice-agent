# Deploying AI Voice Agent to RunPod Server

## ⚠️ Important: RunPod Does NOT Support Docker-in-Docker

RunPod pods run inside containers and **do not support running Docker or Docker Compose** inside them. Use the **Native Setup** method below.

---

## Method 1: Native Setup (Recommended for RunPod)

This method runs services directly without Docker.

### Step 1: Connect to Your RunPod Server

Get your SSH command from the RunPod console:
```bash
ssh root@<your-runpod-ip> -p <port>
# Or use the web terminal in RunPod console
```

### Step 2: Clone the Repository

```bash
cd /workspace
git clone https://github.com/gregoryshoniwa/voice-agent.git
cd voice-agent
```

### Step 3: Run Native Setup

```bash
# Make scripts executable
chmod +x setup-runpod-native.sh start-services.sh

# Run the native setup (installs Ollama, PostgreSQL, Python deps)
./setup-runpod-native.sh
```

This will:
- ✅ Detect your GPU (RTX A5000, A40, etc.)
- ✅ Install Ollama and pull AI models
- ✅ Set up PostgreSQL database
- ✅ Install Python dependencies
- ✅ Create the Voice Agent API

### Step 4: Start Services

```bash
./start-services.sh
```

### Step 5: Configure Public Endpoints in RunPod

1. Go to your RunPod console
2. Click on your pod → **Connect** → **HTTP Service**
3. Add public endpoint for port **80** (Voice Agent API/Frontend)
4. Optionally add port **11434** (Ollama API)

### Step 6: Access Your Application

- **Frontend**: `https://<pod-id>-80.proxy.runpod.net`
- **API Docs**: `https://<pod-id>-80.proxy.runpod.net/docs`

---

## Method 2: Docker Setup (For VPS/Cloud Servers with Docker)

If you're using a VPS or cloud server where Docker is available (NOT RunPod pods), use the Docker-based setup.

### Prerequisites

- Docker Engine 20.10+
- Docker Compose V2+
- GPU support (optional, for faster inference)

### Step 1: Clone and Setup

```bash
cd /opt  # or your preferred directory
git clone https://github.com/gregoryshoniwa/voice-agent.git
cd voice-agent

# Copy environment file
cp supabase-project/.env.dev supabase-project/.env

# Run Docker setup
chmod +x setup.sh setup-runpod.sh
./setup-runpod.sh  # For GPU servers
# or
./setup.sh         # For CPU servers
```

### Step 2: Access Services

- Frontend: `http://<server-ip>:3002`
- n8n: `http://<server-ip>:5678`
- Supabase Studio: `http://<server-ip>:8000`

---

## Troubleshooting

### RunPod: "Docker daemon is not running"
This is expected! RunPod doesn't support Docker-in-Docker. Use `setup-runpod-native.sh` instead.

### Check Ollama Status
```bash
curl http://localhost:11434/api/tags
ollama list
```

### Check API Status
```bash
curl http://localhost:80/api/health
curl http://localhost:80/api/status
```

### View Logs
```bash
# Ollama logs
tail -f /tmp/ollama.log

# API logs (if running in foreground)
# Check the terminal where uvicorn is running
```

### Restart Services
```bash
# Kill existing processes
pkill ollama
pkill uvicorn

# Restart
./start-services.sh
```

### GPU Not Detected
```bash
# Check NVIDIA driver
nvidia-smi

# If not working, install NVIDIA drivers
apt-get install nvidia-driver-535  # or appropriate version
```

---

## Performance Tips

1. **GPU Acceleration**: RTX A5000/A40 will significantly speed up Ollama inference
2. **Model Selection**: 
   - `llama3.2:1b` - Fast, good for testing
   - `llama3.2` - Better quality, slower
   - `llama3.1:8b` - Best quality, requires more VRAM
3. **Monitor Resources**: Use `nvidia-smi` to watch GPU memory

---

## Quick Reference

### Native Setup (RunPod)
```bash
cd /workspace
git clone https://github.com/gregoryshoniwa/voice-agent.git
cd voice-agent
chmod +x setup-runpod-native.sh start-services.sh
./setup-runpod-native.sh
./start-services.sh
```

### Docker Setup (VPS)
```bash
git clone https://github.com/gregoryshoniwa/voice-agent.git
cd voice-agent
cp supabase-project/.env.dev supabase-project/.env
chmod +x setup.sh
./setup.sh
```

