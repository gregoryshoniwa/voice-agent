#!/bin/bash

#################################################
# AI Voice Agent - Stop Script
#################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping all services..."

if docker compose version &> /dev/null; then
    docker compose -f docker-compose.full.yaml --env-file supabase-project/.env down
else
    docker-compose -f docker-compose.full.yaml --env-file supabase-project/.env down
fi

echo "All services stopped."
