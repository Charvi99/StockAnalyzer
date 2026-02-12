# ML Training Container - CPU Version
# Works WITHOUT GPU - will just be slower
# Python 3.11+ required for chronos-forecasting

FROM python:3.11-slim

LABEL maintainer="StockAnalyzer"
LABEL description="ML Training Container (CPU)"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scripts/ /app/scripts/
# COPY notebooks/ /app/notebooks/  # Commented out - directory doesn't exist

# Create outputs directories (no VOLUME directive - using bind mounts from docker-compose)
RUN mkdir -p /app/outputs/features && \
    mkdir -p /app/outputs/models && \
    mkdir -p /app/outputs/logs && \
    mkdir -p /app/outputs/validation

# Expose Jupyter port
EXPOSE 8888

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/health || exit 1

# Default command: Jupyter Lab
CMD ["jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--no-browser", \
     "--allow-root", \
     "--NotebookApp.token=''", \
     "--NotebookApp.password=''"]
