# Use a minimal Python base image
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

# Disable .pyc generation, unbuffer stdout/stderr, and disable pip cache
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Application working directory
WORKDIR /app

# --------------------------------------------------------------------
# 1) System dependencies for embeddings + rerank + OCR
#    (BLAS, OpenGL, X11, glib, OpenMP, etc.)
# --------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------------
# 2) Python dependencies (torch CPU or GPU depending on DEVICE)
# --------------------------------------------------------------------
COPY requirements.txt .

# DEVICE is a build arg and also exposed as ENV
# so the app can read it at runtime (e.g. "cpu" or "cuda:0")
ARG DEVICE=cpu
ENV DEVICE=${DEVICE}

# Torch / torchvision versions (keep in sync with your code/runtime)
ARG TORCH_VERSION=2.6.0
ARG TORCHVISION_VERSION=0.21.0

# Wheel index URLs for CPU-only and CUDA builds
ARG TORCH_INDEX_URL_CPU=https://download.pytorch.org/whl/cpu
ARG TORCH_INDEX_URL_CUDA=https://download.pytorch.org/whl/cu118

RUN pip install --no-cache-dir --upgrade pip && \
    # Select the appropriate torch index based on DEVICE
    if echo "$DEVICE" | grep -qi "^cuda"; then \
        echo ">>> Build GPU: torch CUDA (DEVICE=$DEVICE)"; \
        TORCH_INDEX_URL="$TORCH_INDEX_URL_CUDA"; \
    else \
        echo ">>> Build CPU: torch CPU (DEVICE=$DEVICE)"; \
        TORCH_INDEX_URL="$TORCH_INDEX_URL_CPU"; \
    fi && \
    # Install torch / torchvision from the selected index
    pip install --no-cache-dir \
        torch==${TORCH_VERSION} \
        torchvision==${TORCHVISION_VERSION} \
        --index-url "$TORCH_INDEX_URL" && \
    # Install remaining Python dependencies
    pip install --no-cache-dir -r requirements.txt

# --------------------------------------------------------------------
# 3) Application code
# --------------------------------------------------------------------
# Ensure .dockerignore excludes secrets (e.g. .secret-env, keys, etc.)
COPY . .

# --------------------------------------------------------------------
# 4) Expose API port & start unified API
# --------------------------------------------------------------------
EXPOSE 9005

# Run the FastAPI app with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9005"]
