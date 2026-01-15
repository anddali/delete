"""
Query API routes.
"""

import hashlib
import time
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.auth import get_api_token, TokenData
from app.services.cache import cache_service
from app.services.search import SearchService
from shared.database.connection import get_db
from shared.database.models import Source, QueryLog

logger = structlog.get_logger()

router = APIRouter(tags=["Query"])


# Request/Response models
class SearchRequest(BaseModel):
    """Search request body."""
    
    query: str = Field(..., min_length=1, max_length=2000)
    sliding_window: int = Field(
        default=settings.DEFAULT_SLIDING_WINDOW,
        ge=0,
        le=settings.MAX_SLIDING_WINDOW,
        description="Number of adjacent chunks to include (0-3)",
    )
    limit: int = Field(default=10, ge=1, le=settings.MAX_RESULTS)
    source_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Filter by specific sources",
    )
    source_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by source types (confluence, slack, file_upload)",
    )
    min_similarity: float = Field(
        default=settings.MIN_SIMILARITY_THRESHOLD,
        ge=0.0,
        le=1.0,
    )
    include_metadata: bool = Field(default=True)


class ChunkResult(BaseModel):
    """Individual chunk in search result."""
    
    chunk_id: UUID
    content: str
    position: int
    char_start: int
    char_end: int
    similarity: float
    is_match: bool = Field(description="True if this is the matching chunk")


class SearchResult(BaseModel):
    """Single search result with extended context."""
    
    document_id: UUID
    document_title: str
    document_url: Optional[str]
    source_id: UUID
    source_name: str
    source_type: str
    similarity: float
    chunks: List[ChunkResult]
    extended_content: str = Field(
        description="Combined content from sliding window",
    )
    metadata: Optional[dict] = None


class SearchResponse(BaseModel):
    """Search response."""
    
    query: str
    total_results: int
    results: List[SearchResult]
    search_time_ms: float
    cached: bool = False


class BatchSearchRequest(BaseModel):
    """Batch search request."""
    
    queries: List[str] = Field(..., min_length=1, max_length=10)
    sliding_window: int = Field(default=settings.DEFAULT_SLIDING_WINDOW, ge=0, le=3)
    limit: int = Field(default=5, ge=1, le=10)
    source_ids: Optional[List[UUID]] = None


class BatchSearchResponse(BaseModel):
    """Batch search response."""
    
    results: List[SearchResponse]
    total_time_ms: float


class SourceInfo(BaseModel):
    """Source information."""
    
    id: UUID
    name: str
    type: str
    document_count: int
    chunk_count: int


@router.post("/query/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    token: TokenData = Depends(get_api_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic search with sliding window context retrieval.
    
    The sliding_window parameter controls how many adjacent chunks to include:
    - 0: Only the matching chunk
    - 1: 1 chunk before + match + 1 chunk after
    - 2: 2 chunks before + match + 2 chunks after
    - 3: 3 chunks before + match + 3 chunks after
    """
    logger.info("=== SEARCH REQUEST START ===")
    logger.info("Request params", 
        query=request.query,
        sliding_window=request.sliding_window,
        limit=request.limit,
        source_ids=request.source_ids,
        min_similarity=request.min_similarity
    )
    logger.info("Token info",
        token_id=str(token.token_id),
        token_source_ids=[str(s) for s in (token.source_ids or [])]
    )
    
    start_time = time.time()
    
    # Check cache
    cache_key = _build_cache_key(request, token.source_ids)
    logger.info("Cache check", cache_key=cache_key, cache_enabled=settings.CACHE_ENABLED)
    if settings.CACHE_ENABLED:
        cached = await cache_service.get(cache_key)
        if cached:
            logger.info("Cache HIT - returning cached result")
            cached["cached"] = True
            cached["search_time_ms"] = (time.time() - start_time) * 1000
            return SearchResponse(**cached)
    logger.info("Cache MISS - proceeding with search")
    
    # Resolve source IDs from token scopes
    allowed_source_ids = token.source_ids
    logger.info("Allowed source IDs from token", allowed_source_ids=[str(s) for s in (allowed_source_ids or [])])
    
    # Apply request filters
    filter_source_ids = None
    if request.source_ids:
        logger.info("Request has source_ids filter")
        # Intersect with allowed sources
        if allowed_source_ids:
            filter_source_ids = [
                sid for sid in request.source_ids
                if str(sid) in [str(a) for a in allowed_source_ids]
            ]
            logger.info("Intersected with allowed", filter_source_ids=[str(s) for s in filter_source_ids])
        else:
            filter_source_ids = request.source_ids
            logger.info("No token scope restriction, using request source_ids")
    elif allowed_source_ids:
        filter_source_ids = allowed_source_ids
        logger.info("Using token scope source_ids", filter_source_ids=[str(s) for s in filter_source_ids])
    else:
        logger.info("No source filter applied - searching all sources")
    
    logger.info("Final filter_source_ids", 
        filter_source_ids=[str(s) for s in filter_source_ids] if filter_source_ids else None
    )
    
    # Perform search
    search_service = SearchService(db)
    logger.info("Calling search_service.search...")
    
    results = await search_service.search(
        query=request.query,
        sliding_window=request.sliding_window,
        limit=request.limit,
        source_ids=filter_source_ids,
        source_types=request.source_types,
        min_similarity=request.min_similarity,
        include_metadata=request.include_metadata,
    )
    
    logger.info("Search complete", result_count=len(results))
    
    search_time_ms = (time.time() - start_time) * 1000
    
    response_data = {
        "query": request.query,
        "total_results": len(results),
        "results": results,
        "search_time_ms": search_time_ms,
        "cached": False,
    }
    
    # Cache response
    if settings.CACHE_ENABLED and results:
        await cache_service.set(
            cache_key,
            response_data,
            ttl=settings.CACHE_TTL_SECONDS,
        )
    
    # Log query
    await _log_query(db, token, request, len(results), search_time_ms)
    
    logger.info("=== SEARCH REQUEST END ===", total_results=len(results), time_ms=search_time_ms)
    return SearchResponse(**response_data)


@router.post("/query/search/batch", response_model=BatchSearchResponse)
async def batch_search(
    request: BatchSearchRequest,
    token: TokenData = Depends(get_api_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch search for multiple queries.
    
    Limited to 10 queries per batch.
    """
    start_time = time.time()
    results = []
    
    search_service = SearchService(db)
    
    for query in request.queries:
        query_start = time.time()
        
        search_results = await search_service.search(
            query=query,
            sliding_window=request.sliding_window,
            limit=request.limit,
            source_ids=request.source_ids or token.source_ids,
        )
        
        results.append(SearchResponse(
            query=query,
            total_results=len(search_results),
            results=search_results,
            search_time_ms=(time.time() - query_start) * 1000,
            cached=False,
        ))
    
    return BatchSearchResponse(
        results=results,
        total_time_ms=(time.time() - start_time) * 1000,
    )


@router.get("/query/sources", response_model=List[SourceInfo])
async def list_sources(
    token: TokenData = Depends(get_api_token),
    db: AsyncSession = Depends(get_db),
):
    """List sources accessible by the API token."""
    query = select(Source).where(Source.is_active == True)
    
    # Filter by token scopes
    if token.source_ids:
        query = query.where(Source.id.in_(token.source_ids))
    
    result = await db.execute(query)
    sources = result.scalars().all()
    
    return [
        SourceInfo(
            id=s.id,
            name=s.name,
            type=s.type,
            document_count=s.document_count or 0,
            chunk_count=s.chunk_count or 0,
        )
        for s in sources
    ]


@router.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db)):
    """Readiness check - verifies dependencies."""
    from app.services.health import check_all_health
    
    health_status = await check_all_health(db)
    
    if not all(health_status.values()):
        raise HTTPException(status_code=503, detail=health_status)
    
    return {"status": "ready", "checks": health_status}


def _build_cache_key(request: SearchRequest, source_ids: Optional[List[UUID]]) -> str:
    """Build cache key from request."""
    key_parts = [
        request.query,
        str(request.sliding_window),
        str(request.limit),
        str(sorted(str(s) for s in (request.source_ids or []))),
        str(sorted(request.source_types or [])),
        str(request.min_similarity),
        str(sorted(str(s) for s in (source_ids or []))),
    ]
    
    key_string = "|".join(key_parts)
    key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    return f"{settings.CACHE_PREFIX}{key_hash}"


async def _log_query(
    db: AsyncSession,
    token: TokenData,
    request: SearchRequest,
    result_count: int,
    search_time_ms: float,
):
    """Log query for analytics."""
    try:
        log = QueryLog(
            api_token_id=token.token_id,
            query=request.query,
            sliding_window=request.sliding_window,
            source_ids=[str(s) for s in (request.source_ids or [])],
            result_count=result_count,
            search_time_ms=search_time_ms,
        )
        db.add(log)
        await db.commit()
    except Exception as e:
        logger.warning("Failed to log query", error=str(e))
