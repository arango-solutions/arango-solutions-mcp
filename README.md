# ArangoDB MCP Server

A comprehensive Model Context Protocol (MCP) server for ArangoDB multi-model database operations. This server provides document, graph, and search capabilities through a clean, Poetry-managed Python environment with zero hardcoded configuration.



### Prerequisites

- Python 3.10 or higher
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management
- ArangoDB instance (local or remote)

### 1. Installation

```bash
# Clone or extract the project
cd mcp_server

# Install dependencies with Poetry
poetry install
```

### 2. Configuration

The server uses environment variables configured through your MCP client's `mcp.json` file. **No hardcoded credentials!**

#### For Cursor IDE:

Edit your `.cursor/mcp.json` file:

```json
{
  "mcpServers": {
    "arangodb-mcp": {
      "command": "poetry",
      "args": ["run", "python", "main.py"],
      "env": {
        "ARANGO_HOSTS": "http://localhost:8529",
        "ARANGO_ROOT_USERNAME": "root",
        "ARANGO_ROOT_PASSWORD": "your_password_here",
        "ARANGO_DEFAULT_DB_NAME": "myapp"
      }
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
      "command": "poetry",
      "args": ["run", "python", "main.py"],
      "cwd": "/path/to/mcp_server",
      "env": {
        "ARANGO_HOSTS": "http://localhost:8529",
        "ARANGO_ROOT_USERNAME": "root",
        "ARANGO_ROOT_PASSWORD": "your_password_here",
        "ARANGO_DEFAULT_DB_NAME": "myapp"
      }
    }
  }
}
```

### 3. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARANGO_HOSTS` | Yes | - | ArangoDB server URL(s) |
| `ARANGO_ROOT_USERNAME` | Yes | - | ArangoDB username |
| `ARANGO_ROOT_PASSWORD` | Yes | - | ArangoDB password |
| `ARANGO_DEFAULT_DB_NAME` | No | `_system` | Default database name |


```

## Project Structure

```
mcp_server/
├── pyproject.toml           # Poetry configuration (no hardcoding!)
├── poetry.lock             # Dependency lock file (auto-generated)
├── README.md               # This file
├── .cursor/
│   └── mcp.json           # Cursor MCP configuration
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
│   └── view_management_agent.py
├── mcp_tools/             # MCP tool definitions
│   ├── __init__.py
│   ├── database_tools.py
│   ├── collection_tools.py
│   ├── document_tools.py
│   ├── graph_tools.py
│   ├── aql_tools.py
│   ├── index_tools.py
│   ├── analyzer_tools.py
│   └── view_tools.py

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


