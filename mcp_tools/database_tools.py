from typing import Any, Dict, Optional

from pydantic import Field

from agents.database_management_agent import DatabaseManagementAgent
from server import mcp_app

db_agent = DatabaseManagementAgent()


@mcp_app.tool(
    name="list-databases",
    description="""Lists all databases available in the ArangoDB instance.
    
    Databases in ArangoDB provide logical separation of data, similar to schemas in SQL.
    Each database can contain its own collections, users, and access controls.
    
    Common database patterns:
    - 'production' - live application data
    - 'staging' - pre-production testing
    - 'development' - development environment
    - 'analytics' - data analysis and reporting
    - 'archive' - historical data storage
    
    Use this to:
    - Explore available databases in your instance
    - Plan data organization and separation
    - Choose target database for operations
    - Audit database structure
    
    System databases (like '_system') are included and contain ArangoDB metadata.
    """,
)
async def list_databases() -> Dict[str, Any]:
    """Lists all ArangoDB databases with descriptions and metadata."""
    return await db_agent.arun({"operation": "list_databases"})


@mcp_app.tool(
    name="create-database",
    description="""Creates a new database for logical data separation.
    
    Databases provide isolation and organization:
    - Independent collections and data
    - Separate user access controls
    - Individual backup and restore
    - Environment separation (dev/staging/prod)
    
    Best practices:
    - Use descriptive names (myapp_production, analytics_warehouse)
    - Plan database structure before creation
    - Consider access control requirements
    - Document database purposes and schemas
    
    Common use cases:
    - Multi-tenant applications (one database per tenant)
    - Environment separation (development vs production)
    - Data partitioning (operational vs analytical)
    - Microservice data isolation
    """,
)
async def create_database(
    database_name: str = Field(
        description="""Name for the new database. Should be descriptive and follow conventions.
        
        Examples:
        - 'myapp_production' - production application data
        - 'analytics_warehouse' - data analytics and reporting
        - 'customer_tenant_123' - multi-tenant application
        - 'staging_environment' - staging and testing
        
        Naming conventions:
        - Use lowercase letters, numbers, and underscores
        - Avoid spaces and special characters
        - Include environment or purpose in name
        - Keep names descriptive but concise
        """
    ),
) -> Dict[str, Any]:
    """Creates a new ArangoDB database with specified name."""
    return await db_agent.arun(
        {
            "operation": "create_database",
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="delete-database",
    description="""Permanently deletes a database and all its contents.
    
     CRITICAL WARNING: This operation is irreversible and will:
    - Delete ALL collections in the database
    - Remove ALL documents and data
    - Delete ALL indexes and views
    - Remove ALL user permissions for this database
    - Cannot be undone
    
    Use with extreme caution. Consider:
    - Creating backups before deletion
    - Exporting critical data first
    - Verifying you have the correct database name
    - Using development/staging databases for testing
    
    Protected databases:
    - '_system' database cannot be deleted (contains ArangoDB system data)
    
    Common use cases:
    - Cleaning up temporary or test databases
    - Removing obsolete tenant databases
    - Development environment cleanup
    - Database migration and restructuring
    """,
)
async def delete_database(
    database_name: str = Field(
        description="""Name of the database to permanently delete.
        
         DANGER: All data in this database will be lost forever.
        
        Examples:
        - 'old_staging' - obsolete staging database
        - 'temp_migration' - temporary migration database
        - 'test_environment' - development test database
        
        Cannot delete:
        - '_system' database (contains ArangoDB system data)
        
        Double-check the name before execution. This cannot be undone.
        """
    ),
) -> Dict[str, Any]:
    """Permanently deletes an ArangoDB database and all its contents."""
    if database_name == "_system":
        return {"error": "Deleting the _system database is not allowed via this tool."}
    return await db_agent.arun({"operation": "delete_database", "database_name": database_name})


@mcp_app.tool(
    name="get-database-info",
    description="""Retrieves detailed information about a database's configuration and statistics.
    
    Provides comprehensive database metadata including:
    - Database properties and configuration
    - Storage and usage statistics
    - Collection count and overview
    - User access and permissions
    - System information and version details
    
    Use this to:
    - Monitor database health and performance
    - Understand database configuration
    - Plan capacity and optimization
    - Audit database properties
    - Debug database-related issues
    
    Particularly useful for:
    - Database administration and monitoring
    - Capacity planning and growth analysis
    - Configuration verification
    - Performance troubleshooting
    - Compliance and auditing
    """,
)
async def get_database_info(
    database_name: Optional[str] = Field(
        default=None,
        description="""Name of the database to analyze. Uses default database if not specified.
        
        Examples:
        - 'production' - get production database stats
        - 'analytics' - analyze analytics database
        - 'staging' - check staging database config
        
        Returns detailed information about:
        - Database configuration and properties
        - Storage usage and performance
        - Collection count and types
        - System and version information
        """,
    ),
) -> Dict[str, Any]:
    """Retrieves comprehensive information about an ArangoDB database."""
    return await db_agent.arun({"operation": "get_database_info", "database_name": database_name})
