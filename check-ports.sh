#!/bin/bash
# Commands to check port availability on the server
# Run these commands on your server to find available ports

echo "=== Checking ports 3001 and 5432 ==="
echo ""
echo "Checking port 3001 (voice-agent-api):"
netstat -tuln | grep :3001 || ss -tuln | grep :3001 || echo "Port 3001 appears to be free (or command not available)"
echo ""
echo "Checking port 5432 (PostgreSQL):"
netstat -tuln | grep :5432 || ss -tuln | grep :5432 || echo "Port 5432 appears to be free (or command not available)"
echo ""

echo "=== Finding available ports ==="
echo ""
echo "Checking ports 3002-3010 for voice-agent-api:"
for port in {3002..3010}; do
    if ! (netstat -tuln 2>/dev/null | grep -q :$port || ss -tuln 2>/dev/null | grep -q :$port); then
        echo "  Port $port is available"
    fi
done

echo ""
echo "Checking ports 5433-5440 for PostgreSQL pooler:"
for port in {5433..5440}; do
    if ! (netstat -tuln 2>/dev/null | grep -q :$port || ss -tuln 2>/dev/null | grep -q :$port); then
        echo "  Port $port is available"
    fi
done

echo ""
echo "=== Alternative: Using lsof (if available) ==="
echo "lsof -i :3001"
echo "lsof -i :5432"
echo ""
echo "=== Alternative: Using docker ps (to see container ports) ==="
echo "docker ps --format 'table {{.Names}}\t{{.Ports}}'"

