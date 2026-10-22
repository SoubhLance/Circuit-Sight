# ==============================================================================
# CircuitSight — Backend Production Dockerfile (Linux CPU / FastAPI)
#
# Build Context: Repository Root (.)
# Build Command: docker build -f backend/Dockerfile -t circuitsight-backend:latest .
#
# Safeguards:
# - Strictly pins Linux CPU-only PyTorch and torchvision with verification assertion
# - Excludes Windows venv/, local datasets, and caches via root .dockerignore
# - Runs as an unprivileged non-root user (appuser) with write access to tmp/batches
# - Preserves YOLOv8 (yolov8_pcb_best.pt) and EfficientNet-B0 (efficientnet_b0_best.pth)
# ==============================================================================

FROM python:3.12-slim

# Prevent Python from writing .pyc bytecode and enable immediate flush of stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

WORKDIR /app

# Step 1: Install essential Linux system shared libraries
# libglib2.0-0: Required by opencv-python-headless for core routines
# libgomp1: GNU OpenMP library required by PyTorch CPU for tensor multithreading
# curl, ca-certificates: Required for container health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Step 2: Install PyTorch CPU-only distribution first & verify CPU build tag
# Pinning the explicit '+cpu' version and asserting its presence guarantees that
# CUDA packages (3.5+ GB) are never pulled into the production image.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    torch==2.5.1+cpu torchvision==0.20.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu && \
    python -c "import torch, torchvision; assert '+cpu' in torch.__version__, f'Expected CPU build, got {torch.__version__}'; assert not torch.cuda.is_available(); print(f'Verified: PyTorch {torch.__version__} CPU build installed successfully.')"

# Step 3: Copy requirements and install runtime Python dependencies
# Because torch is already satisfied in site-packages, pip skips PyTorch entirely.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Step 4: Copy application source code and models
# High-volume training datasets (backend/dataset/, backend/data/) and local venv/
# are automatically excluded by root .dockerignore.
COPY backend /app/backend
COPY main.py /app/main.py

# Step 5: Create unprivileged runtime user and configure directory permissions
# Ensures appuser can create and purge batch directories in /app/backend/tmp/batches
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    mkdir -p /app/backend/tmp/batches && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Step 6: Container Healthcheck targeting the verified /api/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Step 7: Launch FastAPI via production Uvicorn ASGI server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
