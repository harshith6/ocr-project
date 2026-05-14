# Debian slim + runtime libs for PaddlePaddle + OpenCV (PaddleOCR deps).
# Build: docker build -t ocr-backend .
# Run:  docker run -p 8000:8000 -e PORT=8000 ocr-backend

FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OpenCV (opencv-python) + Paddle native deps; ca-certificates for model HTTPS download
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    libice6 \
    libsm6 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY static ./static

# Default model cache inside app dir (mount a volume here on Render if you want persistence)
ENV PADDLEOCR_MODEL_DIR=/app/.paddleocr

EXPOSE 8000

CMD sh -c 'uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1'
