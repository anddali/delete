"""
Search schemas for query API.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import BaseSchema


class SearchFilters(BaseModel):
    """Search filters."""
    
    source_types: Optional[list[str]] = None
    source_ids: Optional[list[str]] = None
    date_range: Optional[dict[str, datetime]] = None
    
    @field_validator("source_types")
    @classmethod
    def validate_source_types(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        allowed_types = ["confluence", "slack", "file_upload"]
        for st in v:
            if st not in allowed_types:
                raise ValueError(f"Source type must be one of: {', '.join(allowed_types)}")
        return v


class SearchOptions(BaseModel):
    """Search options."""
    
    include_content: bool = True
    include_metadata: bool = True
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    deduplicate_chunks: bool = Field(
        default=True,
        description="Remove duplicate chunks in sliding window results",
    )


class SearchRequest(BaseModel):
    """Semantic search request."""
    
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=100)
    sliding_window: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Include N adjacent chunks before/after each result",
    )
    filters: Optional[SearchFilters] = None
    options: Optional[SearchOptions] = None


class HybridSearchRequest(SearchRequest):
    """Hybrid search request (semantic + keyword)."""
    
    semantic_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    keyword_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    
    @field_validator("keyword_weight")
    @classmethod
    def validate_weights(cls, v: float, info) -> float:
        semantic_weight = info.data.get("semantic_weight", 0.7)
        if abs(semantic_weight + v - 1.0) > 0.01:
            raise ValueError("semantic_weight and keyword_weight must sum to 1.0")
        return v


class MultiSearchRequest(BaseModel):
    """Multi-query search request."""
    
    queries: list[str] = Field(..., min_length=1, max_length=10)
    top_k_per_query: int = Field(default=5, ge=1, le=20)
    deduplicate: bool = True
    filters: Optional[SearchFilters] = None


class DocumentInfo(BaseSchema):
    """Document information in search results."""
    
    id: UUID
    title: str
    url: Optional[str] = None
    source_type: str
    source_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SearchResultMetadata(BaseModel):
    """Search result metadata."""
    
    chunk_position: int
    total_chunks: Optional[int] = None
    window_size: int = 0
    included_positions: list[int] = Field(default_factory=list)


class SearchResult(BaseSchema):
    """Individual search result."""
    
    chunk_id: UUID
    document_id: UUID
    score: float
    content: str
    extended_content: Optional[str] = None
    document: DocumentInfo
    metadata: Optional[SearchResultMetadata] = None
    highlights: Optional[list[str]] = None


class SearchResponse(BaseSchema):
    """Search response."""
    
    query_id: UUID
    results: list[SearchResult]
    total: int
    took_ms: int
    cached: bool = False


class MultiSearchResponse(BaseSchema):
    """Multi-query search response."""
    
    results: dict[str, list[SearchResult]]
    took_ms: int


class DocumentResponse(BaseSchema):
    """Full document response."""
    
    id: UUID
    title: str
    content: str
    source_type: str
    source_id: UUID
    url: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
