#!/bin/bash
# Deploy Page-First RAG Agent API with Docker

set -e

echo "=== Deploying Page-First RAG Agent API with Docker ==="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠ .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo "⚠ Please edit .env and add your API keys before deploying!"
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "⚠ Docker is not installed!"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "⚠ Docker Compose is not installed!"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if artifacts exist
if [ ! -d "artifacts/ingestion_production" ]; then
    echo "⚠ Artifacts directory not found!"
    echo "Please run the ingestion pipeline first."
    exit 1
fi

# Build and start containers
echo "Building Docker image..."
docker-compose build

echo "Starting containers..."
docker-compose up -d

# Wait for service to be healthy
echo "Waiting for service to be healthy..."
for i in {1..30}; do
    if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo "✓ Service is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠ Service health check timed out!"
        echo "Check logs with: docker-compose logs -f"
        exit 1
    fi
    sleep 2
done

echo ""
echo "✅ Deployment successful!"
echo ""
echo "📚 API Documentation: http://localhost:8000/docs"
echo "❤️  Health Check: http://localhost:8000/api/v1/health"
echo "📊 Metrics: http://localhost:8000/api/v1/metrics"
echo ""
echo "View logs: docker-compose logs -f"
echo "Stop service: docker-compose down"
