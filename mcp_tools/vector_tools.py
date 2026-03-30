from typing import Any, Dict, List, Optional

from pydantic import Field

from agents.vector_search_agent import VectorSearchAgent
from server import mcp_app

vector_agent = VectorSearchAgent()


@mcp_app.tool(
    name="vector-search",
    description="""Performs approximate nearest neighbor (ANN) vector similarity search.

    Finds documents whose vector embeddings are most similar to a given
    query vector, using a vector index on the collection. Internally
    generates and executes an optimized AQL query with APPROX_NEAR_*
    functions.

    Prerequisites (3.12.4+):
    - ArangoDB started with --vector-index flag
    - Collection populated with vector embeddings
    - Vector index created on the embedding field

    Similarity metrics:
    - cosine: Angular similarity (normalized, -1 to 1, higher = more similar)
    - l2: Euclidean distance (0+, lower = more similar)
    - innerProduct: Dot product (higher = more similar, 3.12.6+)

    The metric MUST match what was used when creating the vector index.

    Supports optional pre-filters on document attributes to narrow
    the search space before computing similarity (3.12.6+).
    """,
)
async def vector_search(
    collection_name: str = Field(description="Name of the collection with a vector index."),
    vector_field: str = Field(
        description="""Attribute name storing the vector embedding.
        Must be indexed by a vector index.

        Examples: 'embedding', 'vector', 'text_embedding'
        """
    ),
    query_vector: List[float] = Field(
        description="""The query vector to find similar documents for.
        Must have the same dimension as the vector index.

        Example for dimension 3: [0.1, 0.5, -0.3]
        In practice, dimensions are typically 256, 384, 768, or 1536.
        """
    ),
    metric: str = Field(
        default="cosine",
        description="""Similarity metric. Must match the vector index metric.
        - 'cosine': angular similarity (default)
        - 'l2': Euclidean distance
        - 'innerProduct': dot product (3.12.6+)
        """,
    ),
    limit: int = Field(
        default=10,
        description="Maximum number of similar documents to return.",
    ),
    n_probe: Optional[int] = Field(
        default=None,
        description="""Number of neighboring Voronoi cells to search.
        Higher = better recall but slower. Overrides the index's
        defaultNProbe for this query only.
        """,
    ),
    return_fields: Optional[List[str]] = Field(
        default=None,
        description="""Specific fields to return from each document.
        If not specified, returns the entire document.

        Example: ['title', 'category', 'price']
        """,
    ),
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="""Pre-filter documents before vector search (3.12.6+).
        Applied as equality filters on document attributes.

        Example: {'category': 'electronics', 'status': 'active'}

        For storedValues fields, filtering happens efficiently within
        the vector index lookup.
        """,
    ),
    include_similarity: bool = Field(
        default=True,
        description="Include the similarity/distance score in results.",
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "operation": "vector_search",
        "database_name": database_name,
        "collection_name": collection_name,
        "vector_field": vector_field,
        "query_vector": query_vector,
        "metric": metric,
        "limit": limit,
        "include_similarity": include_similarity,
    }
    if n_probe is not None:
        payload["n_probe"] = n_probe
    if return_fields is not None:
        payload["return_fields"] = return_fields
    if filters is not None:
        payload["filters"] = filters
    return await vector_agent.arun(payload)


@mcp_app.tool(
    name="hybrid-search",
    description="""Performs hybrid search combining vector similarity with full-text search.

    Retrieves candidates from both a vector index (semantic similarity)
    and an ArangoSearch view (keyword/BM25 relevance), then combines
    scores using weighted fusion.

    This is useful when you want results that are both semantically
    relevant AND textually matching, such as:
    - "Find products similar to this image embedding that also mention 'wireless'"
    - "Find documents about 'machine learning' that are semantically close to this embedding"

    Prerequisites:
    - Vector index on the embedding field
    - ArangoSearch view with the text field linked
    - Both must be on the same collection

    The combined score is: vec_score * vector_weight + text_score * text_weight
    """,
)
async def hybrid_search(
    collection_name: str = Field(
        description="Name of the collection (must have both vector index and search view)."
    ),
    vector_field: str = Field(description="Attribute name storing the vector embedding."),
    query_vector: List[float] = Field(description="The query vector for similarity matching."),
    view_name: str = Field(
        description="Name of the ArangoSearch or search-alias view for text search."
    ),
    text_field: str = Field(
        description="""Document attribute to search text in.
        Must be linked in the ArangoSearch view.

        Examples: 'title', 'description', 'content'
        """
    ),
    text_query: str = Field(
        description="""Text search query. Tokenized using the specified analyzer.

        Example: 'machine learning neural network'
        """
    ),
    metric: str = Field(
        default="cosine",
        description="Vector similarity metric: 'cosine', 'l2', or 'innerProduct'.",
    ),
    limit: int = Field(
        default=10,
        description="Maximum number of combined results to return.",
    ),
    text_analyzer: str = Field(
        default="text_en",
        description="Analyzer for tokenizing the text query. Default: 'text_en'.",
    ),
    vector_weight: float = Field(
        default=0.7,
        description="Weight for vector similarity score in combined ranking (0-1).",
    ),
    text_weight: float = Field(
        default=0.3,
        description="Weight for text relevance score in combined ranking (0-1).",
    ),
    n_probe: Optional[int] = Field(
        default=None,
        description="Number of Voronoi cells to search (overrides index default).",
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await vector_agent.arun(
        {
            "operation": "hybrid_search",
            "database_name": database_name,
            "collection_name": collection_name,
            "vector_field": vector_field,
            "query_vector": query_vector,
            "metric": metric,
            "limit": limit,
            "n_probe": n_probe,
            "view_name": view_name,
            "text_field": text_field,
            "text_query": text_query,
            "text_analyzer": text_analyzer,
            "vector_weight": vector_weight,
            "text_weight": text_weight,
        }
    )
