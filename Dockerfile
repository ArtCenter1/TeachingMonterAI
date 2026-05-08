FROM python:3.11-slim
LABEL version="0.8.0"

# Install system dependencies
# - ffmpeg: for video processing
# - imagemagick: for moviepy text rendering
# - fonts-dejavu-core: standard fonts
RUN apt-get update && apt-get install -y \
    ffmpeg \
    imagemagick \
    libsm6 \
    libxext6 \
    libfreetype6-dev \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Fix ImageMagick security policy to allow PDF/Text operations
# Standard ImageMagick installs often disable these by default for security
RUN sed -i 's/policy domain="path" rights="none" pattern="@\*"/policy domain="path" rights="read|write" pattern="@\*"/g' /etc/ImageMagick-7/policy.xml

WORKDIR /app

# Install torch CPU-only layer first (saves ~2GB vs full torch)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy and install other dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install edge-tts: free Microsoft Neural TTS fallback (no API key required)
RUN pip install --no-cache-dir edge-tts

# Install Playwright Chromium for NLM headless auth refresh (no manual login needed at runtime)
RUN playwright install chromium --with-deps

# Copy application code
COPY . .

# Warm-up the model cache: Pre-download embedding model during build
# This ensures a faster startup and true "local" operation at runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy config and run ingestion to pre-populate ChromaDB
COPY config/domains.yaml config/domains.yaml
RUN python scripts/ingest_rag.py

# Create necessary directories
RUN mkdir -p temp/output temp/video temp/audio temp/assets temp/chroma_db

# Expose the API port
EXPOSE 8000

# Ensure Python output is not buffered
ENV PYTHONUNBUFFERED=1

# Command to run the application
# --timeout-keep-alive: keep HTTP connection alive for 30 min (contest pipeline duration)
# --timeout-graceful-shutdown: give long requests time to finish on SIGTERM
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "1800", "--timeout-graceful-shutdown", "1800"]
