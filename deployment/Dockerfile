FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Expose port for API server (default 8080)
EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8080
ENV LOG_LEVEL=info

# Environment variables for translation models (set these when running the container)
# ENV OPENAI_API_KEY=""
# ENV OPENAI_BASE_URL="https://api.openai.com/v1"
# ENV ANTHROPIC_API_KEY=""
# ENV ANTHROPIC_BASE_URL="https://api.anthropic.com/v1"

# Download all required fonts
ADD "https://github.com/satbyy/go-noto-universal/releases/download/v7.0/GoNotoKurrent-Regular.ttf" /app/
ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifCN-Regular.ttf" /app/
ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifTW-Regular.ttf" /app/
ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifJP-Regular.ttf" /app/
ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifKR-Regular.ttf" /app/

# Install system dependencies
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    libgl1 libglib2.0-0 libxext6 libsm6 libxrender1 build-essential \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Copy project configuration
COPY pyproject.toml .

# Install Python dependencies
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy application files
COPY . .

# Install the application and upgrade babeldoc
# Calls for a random number to break the caching of babeldoc upgrade
ADD "https://www.random.org/cgi-bin/randbyte?nbytes=10&format=h" skipcache

RUN uv pip install --system --no-cache . && \
    uv pip install --system --no-cache "babeldoc>=0.3.64,<0.4.0" "pymupdf<1.25.3"

# Verify installations
RUN python check_babeldoc.py && \
    python test-imports.py && \
    babeldoc --version && \
    babeldoc --warmup

# Verify installation
RUN uv run pdf2zh --version

# Create directories for static files and uploads
RUN mkdir -p /app/static /app/pdf2zh_files

# Make entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Run the API server
CMD ["/app/docker-entrypoint.sh"]