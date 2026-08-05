# From python:3.11-slim

# #Install system-wide depenedcies for unstructured
# RUN apt-get update && apt-get install -y\
#     poppler-utils \
#     tesseract-ocr \
#     libmagic-dev \
#     libgl1 \
#     libglib2.0-0 \
#     && apt-get clean \
#     && rm -rf /var/lib/apt/lists/*

# # Instal UV
# COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# # Create directory named app and set current working path to app
# WORKDIR app

# # Tell UV to install  into system python instead of creating .venv
# # overrride default setting to make uv use local filesystem instead of virtual enivornment
# ENV UV_PROJECT_ENVIRONMENT=/usr/local   
# # to make forecfully install on your os filesystem
# ENV UV_SYSTEM_PYTHON=1

# # Copy dependency files first 
# COPY pyproject.toml uv.lock ./

# # Install dependices directly into system site-packages
# RUN uv sync --frozen --no-install-project

# # Copy the rest of application
# COPY . .

# # Expost port 8000
# EXPOSE 8000

# # Command to start
# CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]


# # ---------- Stage 1: builder ----------
#     FROM python:3.11-slim AS builder

#     RUN apt-get update && apt-get install -y --no-install-recommends \
#         build-essential \
#         && rm -rf /var/lib/apt/lists/*
    
#     COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
    
#     WORKDIR /app
    
#     ENV UV_PROJECT_ENVIRONMENT=/usr/local
#     ENV UV_SYSTEM_PYTHON=1
#     ENV UV_COMPILE_BYTECODE=1
    
#     COPY pyproject.toml uv.lock ./
#     RUN uv sync --frozen --no-install-project --no-dev

# # ---------- Stage 1: builder ----------
#     FROM python:3.11-slim AS builder

#     RUN apt-get update && apt-get install -y --no-install-recommends \
#         build-essential \
#         && rm -rf /var/lib/apt/lists/*
    
#     COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
    
#     WORKDIR /app
    
#     ENV UV_PROJECT_ENVIRONMENT=/usr/local
#     ENV UV_SYSTEM_PYTHON=1
#     ENV UV_COMPILE_BYTECODE=1
    
#     # ---- Install CPU-only torch/torchvision FIRST ----
#     # Version must match what's pinned in pyproject.toml/uv.lock,
#     # otherwise uv sync will think it's unsatisfied and try to re-resolve.
#     # RUN uv pip install --no-cache \
#     #     torch==2.13.0 torchvision==0.28.0 \
#     #     --index-url https://download.pytorch.org/whl/cpu
    
#     COPY pyproject.toml uv.lock ./
#     RUN uv sync --frozen --no-install-project --no-dev\
#     && uv pip install --no-cache torch==2.13.0 torchvision==0.28.0 --index-url https://download.pytorch.org/whl/cpu \
#     && uv pip uninstall \
#         nvidia-cublas nvidia-cuda-cupti nvidia-cuda-nvrtc nvidia-cuda-runtime \
#         nvidia-cudnn-cu13 nvidia-cufft nvidia-cufile nvidia-curand nvidia-cusolver \
#         nvidia-cusparse nvidia-cusparselt-cu13 nvidia-nccl-cu13 nvidia-nvjitlink \
#         nvidia-nvshmem-cu13 nvidia-nvtx triton cuda-bindings cuda-pathfinder cuda-toolkit    
#     # ---------- Stage 2: runtime ----------
#     FROM python:3.11-slim AS runtime
    
#     RUN apt-get update && apt-get install -y --no-install-recommends \
#         poppler-utils \
#         tesseract-ocr \
#         libmagic-dev \
#         libgl1 \
#         libglib2.0-0 \
#         && apt-get clean \
#         && rm -rf /var/lib/apt/lists/*
    
#     WORKDIR /app
    
#     # Copy only the installed packages, not uv/build tools
#     COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
#     COPY --from=builder /usr/local/bin /usr/local/bin
    
#     COPY . .
    
#     EXPOSE 8000
#     CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------- Stage 1: builder ----------
    FROM python:3.11-slim AS builder

    RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        && rm -rf /var/lib/apt/lists/*
    
    COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
    
    WORKDIR /app
    
    ENV UV_PROJECT_ENVIRONMENT=/usr/local
    ENV UV_SYSTEM_PYTHON=1
    ENV UV_COMPILE_BYTECODE=1
    
    COPY pyproject.toml uv.lock ./
    RUN uv sync --frozen --no-install-project --no-dev \
        && uv pip install --no-cache --no-deps --reinstall \
            torch==2.13.0 torchvision==0.28.0 \
            --index-url https://download.pytorch.org/whl/cpu \
        && uv pip uninstall \
            nvidia-cublas nvidia-cuda-cupti nvidia-cuda-nvrtc nvidia-cuda-runtime \
            nvidia-cudnn-cu13 nvidia-cufft nvidia-cufile nvidia-curand nvidia-cusolver \
            nvidia-cusparse nvidia-cusparselt-cu13 nvidia-nccl-cu13 nvidia-nvjitlink \
            nvidia-nvshmem-cu13 nvidia-nvtx triton cuda-bindings cuda-pathfinder cuda-toolkit
    
    # ---------- Stage 2: runtime ----------
    FROM python:3.11-slim AS runtime
    
    RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        libmagic1 \
        libgl1 \
        libglib2.0-0 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*
    
    WORKDIR /app
    
    COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
    COPY --from=builder /usr/local/bin /usr/local/bin
    
    ENV CUDA_VISIBLE_DEVICES=""
    
    COPY . .
    
    EXPOSE 8000
    CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]