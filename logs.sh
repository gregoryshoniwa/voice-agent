#!/bin/bash

#################################################
# AI Voice Agent - View Logs Script
#################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE=${1:-""}

if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

if [ -n "$SERVICE" ]; then
    echo "Showing logs for: $SERVICE"
    $COMPOSE_CMD -f docker-compose.full.yaml --env-file supabase-project/.env logs -f "$SERVICE"
else
    echo "Showing logs for all services (Ctrl+C to exit)"
    $COMPOSE_CMD -f docker-compose.full.yaml --env-file supabase-project/.env logs -f
fi
