from typing import Any, Dict, Optional

from pydantic import Field

from agents.view_management_agent import ViewManagementAgent
from server import mcp_app

view_agent = ViewManagementAgent()

ARANGOSEARCH_PROPERTIES_EXAMPLE = """
Example for 'arangosearch' view type when adding links:
{
  "cleanupIntervalStep": 2, // Optional, ArangoDB has defaults
  "consolidationIntervalMsec": 1000, // Optional
  "links": {
    "your_collection_name": { // Replace with actual collection name
      "analyzers": ["text_en", "identity"], // Ensure these analyzers exist
      "fields": {
        "field_to_search_with_text_analyzer": { "analyzers": ["text_en"] },
        "field_for_exact_filter": { "analyzers": ["identity"] }
      },
      "includeAllFields": false, // Set to true to include all fields by default
      "storeValues": "id", // "id", "full", or "none"
      "trackListPositions": false // For array field indexing
    }
    // Add more collections here if needed
  }
}
"""

SEARCHALIAS_PROPERTIES_EXAMPLE = """
Example for 'search-alias' view type (requires an existing inverted index on the collection):
{
  "indexes": [
    {
      "collection": "source_collection_name", // Replace with actual collection name
      "index": "inverted_index_name_on_source_collection" // Replace with actual index name
    }
    // Add more index links here if needed
  ]
}
"""


@mcp_app.tool(
    name="list-views",
    description="""Lists all search views for full-text search and aggregation capabilities.
    
    Views in ArangoDB provide advanced search and aggregation:
    - ArangoSearch views: Full-text search with analyzers and ranking
    - Search-alias views: Virtual views over inverted indexes
    
    Views enable:
    - Complex text search across multiple collections
    - Relevance ranking and scoring
    - Faceted search and aggregations
    - Real-time search index updates
    - Multi-field and cross-collection queries
    
    Use this to:
    - Explore available search capabilities
    - Understand search infrastructure
    - Plan search implementations
    - Monitor view performance and usage
    
    Common view types:
    - ArangoSearch: Comprehensive full-text search with custom analyzers
    - Search-alias: Lightweight views over existing inverted indexes
    """,
)
async def list_views(
    database_name: Optional[str] = Field(
        default=None,
        description="""Target database name. Uses default database if not specified.
        
        Examples:
        - 'content_db' - database with searchable content
        - 'ecommerce' - product catalog with search views
        - 'knowledge_base' - documentation and articles
        
        Views are database-specific and tied to collections in that database.
        """,
    ),
) -> Dict[str, Any]:
    return await view_agent.arun({"operation": "list_views", "database_name": database_name})


@mcp_app.tool(
    name="create-view",
    description="""Creates a new search view for full-text search and aggregation.
    
    View types and capabilities:
    
    ArangoSearch Views:
    - Full-text search across multiple collections
    - Custom text analyzers and processing
    - Relevance scoring and ranking
    - Real-time index updates
    - Complex query capabilities
    - Faceted search and aggregations
    
    Search-alias Views:
    - Lightweight views over inverted indexes
    - Fast setup for existing indexed data
    - Limited to collections with inverted indexes
    - Good for simple search needs
    
    Use cases:
    - E-commerce product search
    - Content management systems
    - Knowledge bases and documentation
    - Log analysis and monitoring
    - Multi-language content search
    
    Best practices:
    - Start with minimal configuration and iterate
    - Test with sample data before production
    - Monitor performance and optimize accordingly
    - Plan analyzer strategy for your content
    """,
)
async def create_view(
    view_name: str = Field(
        description="""Unique name for the new search view.
        
        Examples:
        - 'product_search' - for e-commerce product catalog
        - 'content_index' - for articles and documentation
        - 'user_profiles' - for user search functionality
        - 'multilingual_content' - for multi-language search
        
        Naming conventions:
        - Use descriptive names indicating purpose
        - Include entity type (products, users, content)
        - Avoid conflicts with collection names
        - Consider search domain or use case
        """
    ),
    view_type: str = Field(
        description="""Type of search view to create.
        
        Options:
        - 'arangosearch': Full-featured search with custom analyzers (recommended)
        - 'search-alias': Lightweight view over existing inverted indexes
        
        Choose 'arangosearch' for:
        - Complex text search requirements
        - Multi-collection search
        - Custom text processing needs
        - Advanced relevance scoring
        
        Choose 'search-alias' for:
        - Simple search over existing indexes
        - Quick setup with minimal configuration
        - Limited search requirements
        """
    ),
    properties: Optional[Dict[str, Any]] = Field(
        default=None,
        description=f"""View configuration properties (optional for initial ArangoSearch creation).
        
        For ArangoSearch views, you can:
        - Create empty and add links later via update/replace operations
        - Provide initial configuration with collection links
        
        For Search-alias views, properties are required:
        - Must specify index links to existing inverted indexes
        
        ArangoSearch example:
        {ARANGOSEARCH_PROPERTIES_EXAMPLE}
        
        Search-alias example:
        {SEARCHALIAS_PROPERTIES_EXAMPLE}
        
        Start minimal and iterate - you can always update configuration later.
        """,
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await view_agent.arun(
        {
            "operation": "create_view",
            "database_name": database_name,
            "view_name": view_name,
            "view_type": view_type,
            "properties": properties,  # Pass None if user doesn't provide it
        }
    )


@mcp_app.tool(
    name="get-view-properties",
    description="""Retrieves detailed configuration and status of a search view.
    
    Returns comprehensive view information:
    - View type and configuration
    - Collection links and analyzers
    - Index status and statistics
    - Performance metrics
    - Processing settings
    
    Use this to:
    - Understand view configuration
    - Monitor search performance
    - Debug search behavior
    - Plan optimization strategies
    - Audit search infrastructure
    
    Particularly useful for:
    - Search troubleshooting
    - Performance analysis
    - Configuration verification
    - Index health monitoring
    """,
)
async def get_view_properties(
    view_name: str = Field(
        description="""Name of the search view to analyze.
        
        Examples:
        - 'product_search' - get product search configuration
        - 'content_index' - analyze content search setup
        - 'user_profiles' - check user search view
        
        Returns complete configuration including:
        - Collection links and field mappings
        - Analyzer configurations
        - Index statistics and performance data
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await view_agent.arun(
        {"operation": "get_view_properties", "database_name": database_name, "view_name": view_name}
    )


@mcp_app.tool(
    name="update-view-properties",
    description="""Incrementally updates search view configuration without replacing existing settings.
    
    Update behavior:
    - Only specified properties are modified
    - Existing configuration is preserved
    - New collection links can be added
    - Analyzer settings can be modified
    - Index rebuilding happens automatically
    
    Common update scenarios:
    - Adding new collections to search scope
    - Modifying field mappings and analyzers
    - Adjusting search behavior and scoring
    - Adding or removing indexed fields
    - Tuning performance parameters
    
    Use this for:
    - Incremental search improvements
    - Adding new data sources to search
    - Fine-tuning search behavior
    - Performance optimization
    
    Note: Updates trigger index rebuilding which may impact performance temporarily.
    """,
)
async def update_view_properties(
    view_name: str = Field(
        description="""Name of the search view to update.
        
        Examples:
        - 'product_search' - add new product fields to search
        - 'content_index' - modify text processing settings
        - 'user_profiles' - add new user collections
        """
    ),
    properties: Dict[str, Any] = Field(
        description=f"""Partial configuration update - only specified properties will be changed.
        
        Common updates:
        
        Add new collection link:
        {{
          "links": {{
            "new_collection": {{
              "analyzers": ["text_en"],
              "fields": {{
                "title": {{"analyzers": ["text_en"]}},
                "description": {{"analyzers": ["text_en"]}}
              }}
            }}
          }}
        }}
        
        Modify existing collection:
        {{
          "links": {{
            "products": {{
              "fields": {{
                "new_field": {{"analyzers": ["identity"]}}
              }}
            }}
          }}
        }}
        
        For ArangoSearch views:
        {ARANGOSEARCH_PROPERTIES_EXAMPLE}
        
        Only include properties you want to change - existing settings are preserved.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await view_agent.arun(
        {
            "operation": "update_view_properties",
            "database_name": database_name,
            "view_name": view_name,
            "properties": properties,
        }
    )


@mcp_app.tool(
    name="replace-view-properties",
    description="""Completely replaces the search view configuration with a new set of properties.
    
     WARNING: This operation:
    - Replaces ALL existing configuration
    - Removes properties not specified in the new configuration
    - Triggers complete index rebuilding
    - May cause temporary search downtime
    - Cannot be easily undone
    
    Use this for:
    - Major search restructuring
    - Complete configuration overhauls
    - Migrating to new search strategies
    - Fixing broken configurations
    
    Before replacement:
    - Backup current configuration via get-view-properties
    - Test new configuration thoroughly
    - Plan for index rebuild time
    - Consider using update-view-properties for smaller changes
    
    This operation is more disruptive than update-view-properties.
    """,
)
async def replace_view_properties(
    view_name: str = Field(
        description="""Name of the search view whose configuration will be completely replaced.
        
         CAUTION: All existing configuration will be lost and replaced.
        
        Examples:
        - 'product_search' - complete search restructuring
        - 'content_index' - major analyzer changes
        - 'broken_view' - fixing corrupted configuration
        """
    ),
    properties: Dict[str, Any] = Field(
        description=f"""Complete new configuration for the view - this replaces everything.
        
        Must include ALL desired settings as existing configuration will be lost.
        
        Complete ArangoSearch configuration:
        {ARANGOSEARCH_PROPERTIES_EXAMPLE}
        
        Complete Search-alias configuration:
        {SEARCHALIAS_PROPERTIES_EXAMPLE}
        
         Include all desired properties - anything omitted will be reset to defaults.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await view_agent.arun(
        {
            "operation": "replace_view_properties",
            "database_name": database_name,
            "view_name": view_name,
            "properties": properties,
        }
    )


@mcp_app.tool(
    name="delete-view",
    description="""Permanently removes a search view and all its indexes.
    
     WARNING: Deleting a view will:
    - Remove all search indexes and data
    - Break applications using this view for search
    - Free up storage space used by indexes
    - Cannot be easily undone (requires recreation and reindexing)
    
    Impact on applications:
    - Search queries against this view will fail
    - Applications must be updated to use alternative search methods
    - Any dependent search functionality will break
    
    Before deletion:
    - Backup view configuration for potential recreation
    - Update applications to stop using this view
    - Consider alternatives (disable vs delete)
    - Plan for search functionality replacement
    
    Use cases:
    - Removing obsolete search functionality
    - Cleaning up unused views
    - Database optimization and cleanup
    - Search infrastructure restructuring
    """,
)
async def delete_view(
    view_name: str = Field(
        description="""Name of the search view to permanently delete.
        
         DANGER: All search indexes and configuration will be lost forever.
        
        Examples:
        - 'old_product_search' - obsolete product search
        - 'test_search_view' - temporary test view
        - 'deprecated_content_index' - replaced search implementation
        
        Ensure no applications depend on this view before deletion.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await view_agent.arun(
        {"operation": "delete_view", "database_name": database_name, "view_name": view_name}
    )
