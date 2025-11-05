#!/bin/bash
set -e

# Validate required environment variables
if [ -z "$ARANGO_HOSTS" ]; then
    echo "Error: ARANGO_HOSTS is required"
    echo "Please set it via environment variable"
    exit 1
fi

if [ -z "$ARANGO_ROOT_USERNAME" ]; then
    echo "Error: ARANGO_ROOT_USERNAME is required"
    echo "Please set it via environment variable"
    exit 1
fi

if [ -z "$ARANGO_ROOT_PASSWORD" ]; then
    echo "Error: ARANGO_ROOT_PASSWORD is required"
    echo "Please set it via environment variable"
    exit 1
fi

if [ -z "$ARANGO_DEFAULT_DB_NAME" ]; then
    echo "Error: ARANGO_DEFAULT_DB_NAME is required"
    echo "Please set it via environment variable"
    exit 1
fi


# Display configuration (without password)
echo "Starting ArangoDB MCP Server..."
echo "  ArangoDB Hosts: $ARANGO_HOSTS"
echo "  Username: $ARANGO_ROOT_USERNAME"
echo "  Default Database: $ARANGO_DEFAULT_DB_NAME"
echo ""

# Check if running in development mode
if [ "$DEV_MODE" = "true" ]; then
    echo "Running in DEVELOPMENT mode with Poetry..."
    exec poetry run python -m main
else
    echo "Running in PRODUCTION mode..."
    exec /usr/local/bin/arangodb_mcp_server
fi

