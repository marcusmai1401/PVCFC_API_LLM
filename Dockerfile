# PVCFC RAG API - Production Dockerfile
# Multi-stage build cho tối ưu image size và security

# Builder stage - cài dependencies và build app
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies cần thiết cho build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create build directory
WORKDIR /build

# Copy requirements và install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-warn-script-location -r requirements.txt

# Runtime stage - image cuối cùng
FROM python:3.11-slim

# Metadata
LABEL maintainer="PVCFC Engineering" \
      version="0.1.0" \
      description="PVCFC RAG API for Technical Documentation Query"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.local/bin:$PATH"
ENV PYTHONPATH="/app/.local/lib/python3.11/site-packages:$PYTHONPATH"

# Install runtime system dependencies (nếu cần)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Create non-root user cho security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create app directory
WORKDIR /app

# Copy Python packages từ builder stage
COPY --from=builder /root/.local /app/.local

# Copy application code
COPY app/ ./app/
COPY env.example ./.env

# Create logs directory và set permissions
RUN mkdir -p logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Build arguments (sẽ được set bởi CI/CD)
ARG VERSION=0.1.0-dev
ARG COMMIT_SHA=unknown
ENV VERSION=$VERSION
ENV COMMIT_SHA=$COMMIT_SHA
