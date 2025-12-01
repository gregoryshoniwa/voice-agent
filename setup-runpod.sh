#!/bin/bash

#################################################
# Quick Setup Script for RunPod Server
# This enables GPU support and runs initial setup
#################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================"
echo "   RunPod Server Setup"
echo "================================================"
echo ""

# Check for GPU
if command -v nvidia-smi &> /dev/null; then
    echo "[✓] NVIDIA GPU detected"
    nvidia-smi --query-gpu=name --format=csv,noheader
    echo ""
    
    # Enable GPU in docker-compose
    echo "[i] Enabling GPU support for Ollama..."
    sed -i 's/# deploy:/deploy:/' docker-compose.full.yaml
    sed -i 's/#   resources:/  resources:/' docker-compose.full.yaml
    sed -i 's/#     reservations:/    reservations:/' docker-compose.full.yaml
    sed -i 's/#       devices:/      devices:/' docker-compose.full.yaml
    sed -i 's/#         - driver: nvidia/        - driver: nvidia/' docker-compose.full.yaml
    sed -i 's/#           count: 1/          count: 1/' docker-compose.full.yaml
    sed -i 's/#           capabilities: \[gpu\]/          capabilities: [gpu]/' docker-compose.full.yaml
    echo "[✓] GPU support enabled"
else
    echo "[!] No NVIDIA GPU detected - will use CPU"
fi

echo ""
echo "[i] Running standard setup..."
./setup.sh

echo ""
echo "================================================"
echo "   Setup Complete!"
echo "================================================"
echo ""
echo "Access your services:"
echo "  • Frontend: http://<runpod-ip>:3002"
echo "  • n8n: http://<runpod-ip>:5678"
echo "  • Supabase: http://<runpod-ip>:8000"
echo ""
echo "Note: You may need to configure RunPod public endpoints"
echo "      or port forwarding to access from outside."
echo ""

