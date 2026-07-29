# =========================================================================
# STAGE 1: Builder - Build Dependencies & Virtual Environment
# =========================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system build dependencies required for compiling Python C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated virtual environment to isolate dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency definition and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt gunicorn

# =========================================================================
# STAGE 2: Runner - Production Runtime Image
# =========================================================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime dependencies required for DB drivers & curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_APP=app.py
ENV PORT=5000

# Create non-root system user for secure container execution
RUN useradd -m -u 10001 appuser

# Create required persistent storage and logging directories with permissions
RUN mkdir -p /app/instance /app/uploads /app/logs && \
    chown -R appuser:appuser /app

# Copy application source code
COPY --chown=appuser:appuser . /app

# Switch to non-root user
USER appuser

# Expose HTTP port
EXPOSE 5000

# Configure Health Check endpoint polling
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:5000/api/v2/health || exit 1

# Production WSGI server command
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "--timeout", "120", "app:app"]
