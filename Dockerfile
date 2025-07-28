FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    libgl1 libglib2.0-0 libxext6 libsm6 libxrender1 build-essential \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Download required fonts
# ADD "https://github.com/satbyy/go-noto-universal/releases/download/v7.0/GoNotoKurrent-Regular.ttf" /app/
# ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifCN-Regular.ttf" /app/
# ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifTW-Regular.ttf" /app/
# ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifJP-Regular.ttf" /app/
# ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifKR-Regular.ttf" /app/

# Copy project files needed for installation
COPY pyproject.toml .
COPY README.md .
COPY pdf2zh_next ./pdf2zh_next

# Install Python dependencies from pyproject.toml
RUN pip install --no-cache-dir .

# Copy application files
COPY . .

# Create directories for static files and uploads
RUN mkdir -p /app/static /app/pdf2zh_files

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000

# Expose the port
EXPOSE 8000

# Run the API server
CMD ["python", "api_server.py"]
