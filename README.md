# ArangoDB MCP Server

A comprehensive Model Context Protocol (MCP) server for ArangoDB multi-model database operations. This server provides document, graph, and search capabilities through a clean, Poetry-managed Python environment with zero hardcoded configuration.

> **Note:** These MCP tools are built based on the **ArangoDB Community Edition**. All features available in the Community Edition work seamlessly. Features that are common to both Community and Enterprise editions will also work. However, advanced features exclusive to the Enterprise Edition.

## Installation & Setup

### Prerequisites
- Docker installed on your system
- ArangoDB instance (local or remote)

### 1. Build the Docker Image

```bash
# Clone or extract the project
cd arango-mcp-server

# Build the Docker image
docker build -t arangodb-mcp-server:latest -f Dockerfile .
```

### 2. Configuration

#### For Cursor IDE:

1. Open Cursor IDE
2. Go to **Settings** (Ctrl+,)
3. Navigate to **Features** → **Tools**
4. Click on **"New MCP Server"**
5. Configure the server with these settings:

```json
{
  "mcpServers": {
    "arangodb-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm", "--network", "host",
        "-e", "ARANGO_HOSTS=http://localhost:8529",
        "-e", "ARANGO_ROOT_USERNAME=root",
        "-e", "ARANGO_ROOT_PASSWORD=root",
        "-e", "ARANGO_DEFAULT_DB_NAME=test",
        "arangodb-mcp-server:latest"
      ]
    }
  }
}
```

#### For Claude Desktop:

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "arangodb-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm", "--network", "host",
        "-e", "ARANGO_HOSTS=http://localhost:8529",
        "-e", "ARANGO_ROOT_USERNAME=root",
        "-e", "ARANGO_ROOT_PASSWORD=root",
        "-e", "ARANGO_DEFAULT_DB_NAME=test",
        "arangodb-mcp-server:latest"
      ]
    }
  }
}
```

**Note:** Update the environment variables (`ARANGO_HOSTS`, `ARANGO_ROOT_USERNAME`, `ARANGO_ROOT_PASSWORD`, `ARANGO_DEFAULT_DB_NAME`) to match your ArangoDB instance configuration.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARANGO_HOSTS` | Yes | - | ArangoDB server URL(s) |
| `ARANGO_ROOT_USERNAME` | Yes | - | ArangoDB username |
| `ARANGO_ROOT_PASSWORD` | Yes | - | ArangoDB password |
| `ARANGO_DEFAULT_DB_NAME` | Yes | - | Default database name |


## Project Structure

```
arango-mcp-server/
├── pyproject.toml           # Poetry configuration 
├── poetry.lock             # Dependency lock file 
├── README.md               # This file
├── main.py                # Entry point
├── server.py              # FastMCP server setup
├── config.py              # Pydantic settings (env-based)
├── arango_connector.py    # Database connection management
├── agents/                # Business logic agents
│   ├── __init__.py
│   ├── agent_base.py
│   ├── database_management_agent.py
│   ├── collection_management_agent.py
│   ├── document_crud_agent.py
│   ├── graph_management_agent.py
│   ├── aql_execution_agent.py
│   ├── index_management_agent.py
│   ├── analyzer_management_agent.py
│   ├── view_management_agent.py
│   └── manual_management_agent.py
├── mcp_tools/             # MCP tool definitions
│   ├── __init__.py
│   ├── database_tools.py
│   ├── collection_tools.py
│   ├── document_tools.py
│   ├── graph_tools.py
│   ├── aql_tools.py
│   ├── index_tools.py
│   ├── analyzer_tools.py
│   ├── view_tools.py
│   └── manual_tools.py
└── manuals/               # AQL documentation
    ├── aql_ref.md
    ├── cypher2aql.md
    └── optimization.md
```

##  Available Tools

### Database Management
- `list-databases` - List all databases
- `create-database` - Create new database
- `delete-database` - Delete database 
- `get-database-info` - Get database properties

### Collection Management
- `list-collections` - List collections in database
- `create-collection` - Create document or edge collections
- `delete-collection` - Delete collection
- `get-collection-properties` - Get collection statistics

### Document Operations
- `create-document` - Insert single document
- `create-documents-bulk` - Bulk insert documents
- `read-document` - Get document by key/ID
- `read-documents-with-filter` - Query with filters
- `update-document` - Partial document update

### Graph Operations
- `list-graphs` - List named graphs
- `create-graph` - Create graph with edge definitions
- `delete-graph` - Remove graph structure
- `create-edge` - Create relationships between vertices

### AQL Queries
- `execute-aql-query` - Run AQL queries with bind variables
- `get-aql-manual` - Access AQL reference documentation (aql_ref, cypher2aql, optimization)

### Index Management
- `list-indexes` - Show collection indexes
- `create-index` - Create performance indexes
- `delete-index` - Remove indexes

### Text Analysis
- `list-analyzers` - Show text analyzers
- `create-analyzer` - Create custom analyzers
- `delete-analyzer` - Remove analyzers
- `get-analyzer-properties` - Analyzer configuration

### Search Views
- `list-views` - Show ArangoSearch views
- `create-view` - Create search views
- `get-view-properties` - View configuration
- `update-view-properties` - Modify view settings
- `replace-view-properties` - Replace view configuration
- `delete-view` - Remove search views

##  Development

### Adding New Tools

1. Create agent in `agents/` directory
2. Create tool definitions in `mcp_tools/` directory
3. Import in `server.py`

## Troubleshooting

### Import Errors
If you see import errors, ensure any deleted modules or new tools added/remove from `mcp_tools/__init__.py`.

### Connection Issues
- Verify ArangoDB is running on the specified host
- Check environment variables are correctly set
- Ensure Poetry dependencies are installed: `poetry install`

### Tool Discovery
If tools don't appear in your MCP client:
- Restart the MCP client
- Check the server logs for connection errors
- Verify the JSON configuration syntax

