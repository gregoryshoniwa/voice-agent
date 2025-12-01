#!/bin/bash
# Script to verify port availability on the server
# Run this on your server before running setup.sh

echo "=== Checking Port Availability ==="
echo ""

# Check port 3002 (for voice-agent-api)
echo "Checking port 3002 (voice-agent-api):"
if lsof -i :3002 > /dev/null 2>&1; then
    echo "  ❌ Port 3002 is IN USE"
    echo "  Finding alternative..."
    for port in 3003 3004 3005 3006 3007 3008 3009 3010; do
        if ! lsof -i :$port > /dev/null 2>&1; then
            echo "  ✓ Port $port is AVAILABLE (use this instead)"
            break
        fi
    done
else
    echo "  ✓ Port 3002 is AVAILABLE"
fi

echo ""
# Check port 5433 (for PostgreSQL pooler)
echo "Checking port 5433 (PostgreSQL pooler):"
if lsof -i :5433 > /dev/null 2>&1; then
    echo "  ❌ Port 5433 is IN USE"
    echo "  Finding alternative..."
    for port in 5434 5435 5436 5437 5438 5439 5440; do
        if ! lsof -i :$port > /dev/null 2>&1; then
            echo "  ✓ Port $port is AVAILABLE (use this instead)"
            break
        fi
    done
else
    echo "  ✓ Port 5433 is AVAILABLE"
fi

echo ""
echo "=== Summary ==="
echo "If ports 3002 and 5433 are available, you can proceed with setup.sh"
echo "If not, update docker-compose.full.yaml and .env.dev with the suggested alternatives"

