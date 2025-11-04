#!/bin/bash

# Redis Development Startup Script
# Starts Redis server for conversation caching

echo "🔴 Starting Redis server for conversation cache..."

# Check if Redis is already running
if pgrep -x "redis-server" > /dev/null; then
    echo "✅ Redis is already running"
    redis-cli ping
    exit 0
fi

# Check if Redis is installed
if ! command -v redis-server &> /dev/null; then
    echo "❌ Redis not found. Installing Redis..."
    
    # Install Redis based on the system
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y redis-server
    elif command -v yum &> /dev/null; then
        sudo yum install -y redis
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm redis
    else
        echo "❌ Could not install Redis. Please install manually."
        exit 1
    fi
fi

# Create Redis configuration for development
REDIS_CONFIG_FILE="/tmp/redis-dev.conf"
cat > "$REDIS_CONFIG_FILE" << EOF
# Redis Development Configuration
port 6379
bind 127.0.0.1
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir ./
maxmemory-policy allkeys-lru
maxmemory 256mb
timeout 0
tcp-keepalive 300
loglevel notice
logfile ""
databases 16
EOF

echo "📝 Created Redis config at $REDIS_CONFIG_FILE"

# Start Redis server
echo "🚀 Starting Redis server..."
redis-server "$REDIS_CONFIG_FILE" --daemonize yes

# Wait a moment for Redis to start
sleep 2

# Test Redis connection
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis server started successfully!"
    echo "📊 Redis Info:"
    redis-cli INFO server | grep -E "redis_version|uptime_in_seconds|process_id"
    echo ""
    echo "🔗 Connection: localhost:6379"
    echo "💾 Memory Policy: LRU eviction"
    echo "📝 Max Memory: 256MB"
else
    echo "❌ Failed to start Redis server"
    exit 1
fi
