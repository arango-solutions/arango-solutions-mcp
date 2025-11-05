#!/bin/bash
set -e

echo "Preparing test environment..."

# Validate required environment variables FIRST
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
# Wait for ArangoDB to be ready if ARANGODB_HOST is set
if [ -n "$ARANGODB_HOST" ]; then
    echo "Waiting for ArangoDB at $ARANGODB_HOST..."
    
    # Wait for ArangoDB to be ready
    timeout=60
    counter=0
    until curl -s -f -u "${ARANGO_ROOT_USERNAME}:${ARANGO_ROOT_PASSWORD}" \
        "$ARANGODB_HOST/_api/version" > /dev/null 2>&1; do
        counter=$((counter + 1))
        if [ $counter -ge $timeout ]; then
            echo "Error: Timeout waiting for ArangoDB"
            exit 1
        fi
        echo "Waiting for ArangoDB... ($counter/$timeout)"
        sleep 1
    done
    
    echo "ArangoDB is ready!"
fi

#  Validate remaining vars
if [ -z "$ARANGO_HOSTS" ]; then
    echo "Error: ARANGO_HOSTS is required"
    echo "Please set it via environment variable"
    exit 1
fi

if [ -z "$ARANGO_DEFAULT_DB_NAME" ]; then
    echo "Error: ARANGO_DEFAULT_DB_NAME is required"
    echo "Please set it via environment variable"
    exit 1
fi

echo "Environment variables:"
echo "  ARANGO_HOSTS: $ARANGO_HOSTS"
echo "  ARANGO_ROOT_USERNAME: $ARANGO_ROOT_USERNAME"
echo "  ARANGO_DEFAULT_DB_NAME: $ARANGO_DEFAULT_DB_NAME"
echo ""

# Run tests
echo "Running tests..."
poetry run pytest -v --maxfail=1 --disable-warnings "$@"

