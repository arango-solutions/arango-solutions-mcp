FROM python:3.11-slim

# Set environment vars (avoid writing .pyc files, ensure stdout flush)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.4

RUN apt-get update && apt-get install -y curl build-essential && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

COPY . .

# Expose HTTP port (if using HTTP transport)
EXPOSE 8050

# Health check for HTTP mode
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8050/health || exit 1

# Default: HTTP mode with uvicorn (production)
# Override with environment variables or command for STDIO mode
CMD ["poetry", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8050"]
