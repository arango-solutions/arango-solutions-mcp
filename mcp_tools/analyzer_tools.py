from typing import Any, Dict, List, Optional, Union  # Union for properties

from pydantic import Field

from agents.analyzer_management_agent import AnalyzerManagementAgent
from server import mcp_app

analyzer_agent = AnalyzerManagementAgent()


@mcp_app.tool(
    name="list-analyzers",
    description="""Lists all text analyzers available for full-text search and text processing.
    
    Analyzers in ArangoDB process text for search operations by:
    - Tokenizing text into searchable terms
    - Normalizing case, removing stopwords
    - Applying linguistic rules (stemming, lemmatization)
    - Handling different languages and character sets
    
    Built-in analyzers include:
    - 'identity': No processing (exact match)
    - 'text_en': English text processing
    - 'text_de': German text processing
    - 'norm': Unicode normalization
    - 'delimiter': Custom delimiter-based tokenization
    
    Use this to:
    - Explore available text processing options
    - Plan full-text search implementations
    - Understand analyzer capabilities for ArangoSearch views
    - Debug text processing issues
    """,
)
async def list_analyzers(
    database_name: Optional[str] = Field(
        default=None,
        description="""Target database name. Uses default database if not specified.
        
        Examples:
        - 'content_db' - database with text content
        - 'search_index' - dedicated search database
        - 'multilingual' - database with multiple languages
        
        Analyzers are database-specific configurations.
        """,
    ),
) -> Dict[str, Any]:
    return await analyzer_agent.arun(
        {"operation": "list_analyzers", "database_name": database_name}
    )


@mcp_app.tool(
    name="create-analyzer",
    description="""Creates a custom text analyzer for specialized text processing and search.
    
    Custom analyzers enable:
    - Domain-specific text processing (medical, legal, technical)
    - Multi-language support with custom rules
    - Specialized tokenization for codes, IDs, or structured text
    - Performance optimization for specific use cases
    
    Common analyzer types:
    - 'text': Language-aware text processing with locale support
    - 'ngram': Character n-gram generation for fuzzy matching
    - 'delimiter': Custom delimiter-based tokenization
    - 'identity': Pass-through (no processing)
    
    Use cases:
    - Product code search (SKU-123-ABC)
    - Multi-language content processing
    - Technical documentation search
    - Fuzzy name matching
    - Custom domain terminology
    
    Best practices:
    - Test analyzer output with sample data
    - Consider performance impact of complex processing
    - Use appropriate features for your search needs
    """,
)
async def create_analyzer(
    analyzer_name: str = Field(
        description="""Unique name for the custom analyzer.
        
        Examples:
        - 'product_code_analyzer' - for SKU/product codes
        - 'multilingual_content' - for multi-language text
        - 'technical_terms' - for technical documentation
        - 'fuzzy_names' - for person/company name matching
        
        Naming conventions:
        - Use descriptive names indicating purpose
        - Include domain or use case context
        - Avoid conflicts with built-in analyzers
        """
    ),
    analyzer_type: str = Field(
        description="""Type of analyzer algorithm to use.
        
        Available types:
        - 'text': Language-aware processing (recommended for natural language)
        - 'ngram': Character n-gram generation (good for fuzzy matching)
        - 'delimiter': Custom tokenization using delimiters
        - 'identity': No processing (exact string matching)
        - 'norm': Unicode normalization only
        
        Choose based on your text processing needs:
        - 'text' for articles, descriptions, comments
        - 'ngram' for fuzzy search, typo tolerance
        - 'delimiter' for structured codes, IDs
        """
    ),
    properties: Optional[Union[Dict[str, Any], str]] = Field(
        default=None,
        description="""Analyzer-specific configuration properties.
        
        For 'text' analyzer:
        {
          "locale": "en.utf-8",  // Language locale
          "case": "lower",       // Case normalization
          "stopwords": ["the", "and", "or"],  // Words to ignore
          "accent": false,       // Remove accents
          "stemming": true       // Apply stemming
        }
        
        For 'ngram' analyzer:
        {
          "minN": 2,            // Minimum n-gram length
          "maxN": 4,            // Maximum n-gram length
          "preserveOriginal": true,  // Keep original term
          "streamType": "utf8"   // Character encoding
        }
        
        For 'delimiter' analyzer:
        {
          "delimiter": "-",     // Split character
          "case": "upper"       // Case handling
        }
        """,
    ),
    features: Optional[List[str]] = Field(
        default=None,
        description="""Search features to enable for this analyzer.
        
        Available features:
        - 'frequency': Term frequency counting (for relevance scoring)
        - 'norm': Length normalization (for document length independence)
        - 'position': Term position tracking (for phrase queries)
        
        Examples:
        - ['frequency', 'norm'] - for relevance-ranked search
        - ['frequency', 'norm', 'position'] - for phrase and proximity search
        - [] - minimal features for exact matching
        
        More features = more storage and processing overhead.
        """,
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await analyzer_agent.arun(
        {
            "operation": "create_analyzer",
            "database_name": database_name,
            "analyzer_name": analyzer_name,
            "analyzer_type": analyzer_type,
            "properties": properties,
            "features": features,
        }
    )


@mcp_app.tool(
    name="delete-analyzer",
    description="""Removes a custom analyzer from the database.
    
     WARNING: Deleting an analyzer will:
    - Break any ArangoSearch views using this analyzer
    - Invalidate existing search indexes
    - Require rebuilding views that reference it
    - Cannot be undone
    
    Before deletion:
    - Check which views use this analyzer
    - Have a replacement analyzer ready if needed
    - Consider the impact on existing search functionality
    - Backup analyzer configuration for recreation
    
    Built-in analyzers cannot be deleted:
    - 'identity', 'text_en', 'text_de', 'norm', etc.
    
    Use cases:
    - Cleaning up unused custom analyzers
    - Replacing old analyzer configurations
    - Database maintenance and optimization
    """,
)
async def delete_analyzer(
    analyzer_name: str = Field(
        description="""Name of the custom analyzer to delete.
        
         CAUTION: Ensure this analyzer is not used by any ArangoSearch views.
        
        Examples:
        - 'old_product_analyzer' - obsolete product code analyzer
        - 'test_analyzer' - temporary test analyzer
        - 'deprecated_text_processor' - replaced analyzer
        
        Cannot delete built-in analyzers (identity, text_en, etc.).
        Check view dependencies before deletion.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await analyzer_agent.arun(
        {
            "operation": "delete_analyzer",
            "database_name": database_name,
            "analyzer_name": analyzer_name,
        }
    )


@mcp_app.tool(
    name="get-analyzer-properties",
    description="""Retrieves detailed configuration and capabilities of a text analyzer.
    
    Returns comprehensive analyzer information:
    - Analyzer type and algorithm
    - Configuration properties and parameters
    - Enabled features (frequency, norm, position)
    - Processing behavior and settings
    - Usage recommendations
    
    Use this to:
    - Understand how text is processed
    - Debug search behavior and results
    - Plan analyzer usage in views
    - Compare analyzer configurations
    - Optimize search performance
    
    Helpful for:
    - Search troubleshooting and optimization
    - Analyzer configuration review
    - Planning text processing strategies
    - Understanding built-in analyzer behavior
    """,
)
async def get_analyzer_definition(
    analyzer_name: str = Field(
        description="""Name of the analyzer to inspect.
        
        Examples:
        - 'text_en' - built-in English text analyzer
        - 'identity' - exact matching analyzer
        - 'custom_product_analyzer' - your custom analyzer
        - 'multilingual_content' - custom multi-language analyzer
        
        Works with both built-in and custom analyzers.
        Returns complete configuration and feature details.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await analyzer_agent.arun(
        {
            "operation": "get_analyzer_properties",  # Agent operation name remains the same
            "database_name": database_name,
            "analyzer_name": analyzer_name,
        }
    )
