#!/bin/bash
# Setup script for development environment
# Run this script to initialize the development environment

set -e

echo "🚀 Setting up RAG Knowledge Indexing System development environment..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please update .env with your OpenAI API key"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p nginx/ssl
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/grafana/datasources

# Start infrastructure services
echo "🐳 Starting infrastructure services (PostgreSQL, Redis, MinIO)..."
docker compose -f docker-compose.dev.yml up -d postgres redis minio

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
until docker compose -f docker-compose.dev.yml exec -T postgres pg_isready -U raguser -d ragdb; do
    sleep 2
done

echo "✅ PostgreSQL is ready"

# Create MinIO bucket
echo "📦 Creating MinIO bucket..."
docker compose -f docker-compose.dev.yml exec -T minio mc alias set local http://localhost:9000 minioadmin minioadmin 2>/dev/null || true
docker compose -f docker-compose.dev.yml exec -T minio mc mb local/rag-uploads 2>/dev/null || true

# Run database migrations
echo "🔄 Running database migrations..."
docker compose -f docker-compose.dev.yml run --rm management-api alembic upgrade head

# Create default admin user
echo "👤 Creating default admin user..."
docker compose -f docker-compose.dev.yml run --rm management-api python /app/scripts/create-admin.py \
    --email admin@example.com \
    --password admin123! \
    --name "Default Admin"

# Start all services
echo "🚀 Starting all services..."
docker compose -f docker-compose.dev.yml up -d

echo ""
echo "✅ Development environment is ready!"
echo ""
echo "📍 Service URLs:"
echo "   Admin UI:       http://localhost:3000"
echo "   Management API: http://localhost:8001"
echo "   Query API:      http://localhost:8002"
echo "   Ingestion API:  http://localhost:8003"
echo "   MinIO Console:  http://localhost:9001"
echo ""
echo "🔐 Default admin credentials:"
echo "   Email:    admin@example.com"
echo "   Password: admin123!"
echo ""
echo "📊 Optional tools (start with: docker compose -f docker-compose.dev.yml --profile tools up -d):"
echo "   pgAdmin:         http://localhost:5050"
echo "   Redis Commander: http://localhost:8081"
echo "   Flower:          http://localhost:5555"
echo ""
