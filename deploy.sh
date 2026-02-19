#!/bin/bash
set -e

# Deployment Script for Sol's Hive
# Usage: ./deploy.sh

echo "🚀 Deploying Sol's Hive to sol.leadsagent.app..."

# 1. Stop old containers (if running manually)
echo "🛑 Stopping old containers..."
docker stop nostr-relay sol || true
docker rm nostr-relay sol || true

# 2. Build and Start
echo "🏗️  Building and Starting Hive..."
cd deployment
docker compose up -d --build

echo "✅ Deployment Complete."
echo "   - Relay: wss://sol.leadsagent.app"
echo "   - Caddy: https://sol.leadsagent.app"
echo "   - Sol:   Connected internally"
echo ""
echo "📝 Logs:"
docker compose logs -f
