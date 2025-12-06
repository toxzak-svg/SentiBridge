# SentiBridge Worker Dockerfile
# Multi-stage build for security and minimal image size

# Build stage
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir --target=/app/deps .

# Production stage
FROM python:3.11-slim-bookworm AS production

# Security: Create non-root user
RUN groupadd -r sentibridge && \
    useradd -r -g sentibridge -d /app -s /sbin/nologin sentibridge

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy dependencies from builder
COPY --from=builder /app/deps /app/deps
ENV PYTHONPATH="/app/deps:${PYTHONPATH}"

# Copy application code
COPY --chown=sentibridge:sentibridge src/ /app/src/
COPY --chown=sentibridge:sentibridge run.py /app/

# Security hardening
RUN chmod -R 555 /app && \
    chmod 444 /app/src/**/*.py

# Switch to non-root user
USER sentibridge

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Labels
LABEL org.opencontainers.image.source="https://github.com/sentibridge/sentibridge" \
      org.opencontainers.image.description="SentiBridge Crypto Sentiment Worker" \
      org.opencontainers.image.licenses="MIT"

# Run the worker
CMD ["python", "run.py"]
