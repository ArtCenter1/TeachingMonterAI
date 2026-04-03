FROM python:3.11-slim

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libfreetype6-dev \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy and install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (excludes .env, bin/, temp/ via .dockerignore)
COPY . .

# Create output directories
RUN mkdir -p temp/output temp/segments temp/audio

# Expose the API port
EXPOSE 8000

# Ensure Python output is not buffered (so logs appear instantly)
ENV PYTHONUNBUFFERED=1

# Run the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
