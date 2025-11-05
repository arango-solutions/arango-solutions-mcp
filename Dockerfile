# Production Dockerfile for ArangoDB MCP Server
FROM python:3.10-slim AS build-env

# Install system dependencies
RUN apt-get update --allow-releaseinfo-change && \
    apt-get install -y \
    python3-dev \
    gcc \
    g++ \
    curl \
    dnsutils \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install pipx and Poetry
RUN python -m venv /opt/pipx \
    && /opt/pipx/bin/pip install pipx \
    && /opt/pipx/bin/pipx ensurepath

# Update PATH for pipx
ENV PATH=/root/.local/bin:/opt/pipx/bin:$PATH
ENV POETRY_VIRTUALENVS_IN_PROJECT=1

# Install Poetry
RUN pipx install poetry==2.1.1

# Install dependencies without dev packages
RUN poetry install --without dev --no-root --verbose

# Copy application code
COPY agents/ agents/
COPY mcp_tools/ mcp_tools/
COPY manuals/ manuals/
COPY scripts/ scripts/
COPY main.py server.py config.py arango_connector.py ./

# Install pyinstaller and tomli for creating standalone binary
RUN poetry run pip install pyinstaller tomli

# Generate PyInstaller spec file
RUN poetry run python scripts/generate_pyinstaller_spec.py

# Create the executable using the generated spec file
RUN poetry run pyinstaller arangodb_mcp_server.spec

# Runtime stage
FROM python:3.10-slim AS runtime

WORKDIR /app

# Copy binary package from build-env stage
COPY --from=build-env /app/dist/arangodb_mcp_server /usr/local/bin/arangodb_mcp_server

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

