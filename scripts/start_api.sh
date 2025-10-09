#!/bin/bash
# Start Page-First RAG Agent API

set -e

echo "=== Starting Page-First RAG Agent API ==="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠ .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo "⚠ Please edit .env and add your API keys before starting!"
    exit 1
fi

# Check for required environment variables
if ! grep -q "OPENAI_API_KEY=sk-" .env; then
    echo "⚠ OPENAI_API_KEY not set in .env file!"
    echo "Please add your OpenAI API key to .env"
    exit 1
fi

if ! grep -q "GEMINI_API_KEY=" .env && [ "$(grep GEMINI_API_KEY .env | cut -d= -f2)" != "your-gemini-api-key-here" ]; then
    echo "⚠ GEMINI_API_KEY not set in .env file!"
    echo "Please add your Gemini API key to .env"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Check if artifacts exist
if [ ! -d "artifacts/ingestion_production" ]; then
    echo "⚠ Artifacts directory not found!"
    echo "Please run the ingestion pipeline first to generate artifacts."
    exit 1
fi

# Create logs directory
mkdir -p logs

# Start API with uvicorn
echo "Starting API server on http://0.0.0.0:${API_PORT:-8000}..."
echo "📚 API Documentation: http://localhost:${API_PORT:-8000}/docs"
echo "❤️  Health Check: http://localhost:${API_PORT:-8000}/api/v1/health"
echo ""

uvicorn app.api.page_first_api:app \
    --host ${API_HOST:-0.0.0.0} \
    --port ${API_PORT:-8000} \
    --reload \
    --log-level ${LOG_LEVEL:-info}
