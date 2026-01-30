FROM python:3.11-slim

WORKDIR /app

# ============================================
# PHASE 3: TA-Lib Installation (C Library)
# ============================================
# TA-Lib is a C library that provides 200+ technical indicators
# It's 10-50x faster than pure Python/pandas implementations
# Two-step installation: 1) C library, 2) Python wrapper
# ============================================

# Install system dependencies and build tools
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    postgresql-client \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library (required for TA-Lib Python wrapper)
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make scripts executable
RUN chmod +x start.sh migrate.sh migrate.py

# Expose port
EXPOSE 8080

# Run migrations and start the application
CMD ["./start.sh"]
