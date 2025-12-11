# =============================================================================
# Multi-stage Dockerfile for Intelligent Trading Bot
# =============================================================================
# Build strategy:
#   - Stage 1 (builder): Compile TA-Lib and install dependencies
#   - Stage 2 (runtime): Copy only necessary files, minimal footprint
#
# Build modes:
#   - Production (minimal):  docker build --target production -t itb:minimal .
#   - Training (train):      docker build --target training -t itb:train .
#   - Full (development):    docker build --target full -t itb:full .
#
# Expected sizes:
#   - production: ~400MB
#   - training:   ~600MB
#   - full:       ~1.1GB
# =============================================================================

# =============================================================================
# STAGE 1: Builder - Compile TA-Lib
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies for TA-Lib
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download and compile TA-Lib C library
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# =============================================================================
# STAGE 2: Production (minimal) - Shadow Mode
# =============================================================================
FROM python:3.11-slim AS production

LABEL maintainer="ITB Team"
LABEL description="Intelligent Trading Bot - Production (Shadow Mode)"
LABEL version="1.0"

WORKDIR /app

# Copy compiled TA-Lib from builder
COPY --from=builder /usr/lib/libta_lib.* /usr/lib/
COPY --from=builder /usr/include/ta-lib/ /usr/include/ta-lib/

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (minimal)
COPY requirements-minimal.txt /app/
RUN pip install --no-cache-dir -r requirements-minimal.txt && \
    pip install --no-cache-dir ta-lib && \
    rm requirements-minimal.txt

# Copy application code
COPY common/ /app/common/
COPY inputs/ /app/inputs/
COPY outputs/ /app/outputs/
COPY scripts/ /app/scripts/
COPY service/ /app/service/
COPY configs/ /app/configs/

# Remove any stray files that might shadow stdlib
RUN rm -f /app/types.py || true

# Data directories will be mounted from Azure File Share or local volumes
# Do NOT create them here - they should be mounted at runtime:
#   - Azure: Mount File Share using GitHub env vars (AZURE_STORAGE_ACCOUNT/AZURE_FILE_SHARE_5M)
#   - Local: docker run -v $(pwd)/DATA_ITB_5m:/app/DATA_ITB_5m

# Set Python path
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check (optional)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "-m", "scripts.output", "--help"]

# =============================================================================
# STAGE 3: Training - Includes model training dependencies
# =============================================================================
FROM production AS training

LABEL description="Intelligent Trading Bot - Training Mode"

# Install additional training dependencies
# Note: requirements-train.txt includes -r requirements-minimal.txt
COPY requirements-minimal.txt requirements-train.txt /app/
RUN pip install --no-cache-dir -r requirements-train.txt && \
    rm requirements-train.txt requirements-minimal.txt

# Default command for training
CMD ["python", "-m", "scripts.train", "--help"]

# =============================================================================
# STAGE 4: Full - All dependencies (development)
# =============================================================================
FROM training AS full

LABEL description="Intelligent Trading Bot - Full (Development)"

# Install all dependencies including TensorFlow and GCP
# Note: requirements-full.txt includes -r requirements-train.txt which includes -r requirements-minimal.txt
COPY requirements-minimal.txt requirements-train.txt requirements-full.txt /app/
RUN pip install --no-cache-dir -r requirements-full.txt && \
    rm requirements-minimal.txt requirements-train.txt requirements-full.txt

# Default command
CMD ["bash", "-c", "echo 'ITB Container ready. Available modes: minimal, training, full'"]

# =============================================================================
# Build examples:
#
# Production (minimal - 400MB):
#   docker build --target production -t itb:minimal .
#
# Training (600MB):
#   docker build --target training -t itb:train .
#
# Full development (1.1GB):
#   docker build --target full -t itb:full .
#
# Run examples:
#
# Shadow mode:
#   docker run -v $(pwd)/DATA_ITB_5m:/app/DATA_ITB_5m \
#     itb:minimal python -m scripts.output -c configs/base_conservative.jsonc \
#     --symbol BTCUSDT --freq 5m
#
# Training:
#   docker run -v $(pwd)/DATA_ITB_5m:/app/DATA_ITB_5m \
#     itb:train python -m scripts.train -c configs/base_conservative.jsonc \
#     --symbol BTCUSDT --freq 5m
#
# Full pipeline:
#   docker run -v $(pwd):/app itb:full \
#     make run SYMBOL=BTCUSDT FREQ=5m
# =============================================================================
