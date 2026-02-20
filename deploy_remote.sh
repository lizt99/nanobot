#!/bin/bash
set -e

# Define vars
TARGET_DIR="nanobot"
BACKUP_DIR="nanobot_backup_$(date +%s)"

echo "🚀 Starting Hive Mind Deployment..."

# 1. Stop existing stack if present
if [ -d "$TARGET_DIR" ]; then
    echo "🛑 Found existing $TARGET_DIR, attempting to stop..."
    cd "$TARGET_DIR"
    
    # Try to find docker-compose file
    if [ -f "deployment/docker-compose.yml" ]; then
        docker compose -f deployment/docker-compose.yml down || docker-compose -f deployment/docker-compose.yml down || true
    elif [ -f "docker-compose.yml" ]; then
        docker compose down || docker-compose down || true
    fi
    
    cd ..
    echo "📦 Backing up $TARGET_DIR to $BACKUP_DIR..."
    mv "$TARGET_DIR" "$BACKUP_DIR"
fi

# 2. Extract new code
echo "📂 Extracting new code..."
mkdir -p "$TARGET_DIR"
tar -xzf hive_deploy.tar.gz -C "$TARGET_DIR"

# 3. Setup Environment
cd "$TARGET_DIR"
if [ ! -f ".env" ]; then
    echo "📝 Creating default .env..."
    echo "AGENT_API_KEY=sk-secure-key-123456" > .env
    echo "OPENAI_API_KEY=placeholder" >> .env
fi

# 4. Launch
echo "🏗️ Building and Launching..."
CMD="docker compose"
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found!"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    CMD="docker-compose"
fi

$CMD -f deployment/docker-compose.yml up -d --build --remove-orphans

echo "✅ Deployment Complete!"
$CMD -f deployment/docker-compose.yml ps
