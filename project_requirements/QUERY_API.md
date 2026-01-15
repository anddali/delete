# Query API - Requirements & Features

## Overview
High-performance semantic search API with token-based access control. Optimized for low latency and high throughput with intelligent caching and connection pooling.

## Core Responsibilities
- Semantic search using vector similarity
- Token-based authentication and authorization
- Source-based access control (scoped tokens)
- Query result ranking and filtering
- Response caching for performance
- Rate limiting per token

## Technology Stack
- **Runtime**: Python 3.11+
- **Framework**: FastAPI (async/await)
- **Database**: asyncpg + SQLAlchemy 2.0 (async)
- **Cache**: Redis with async client
- **Embedding**: OpenAI Python SDK
- **Vector Search**: pgvector (HNSW index)

## Performance Requirements

### Latency Targets
- **Query Response Time (p50)**: <100ms
- **Query Response Time (p95)**: <200ms
- **Query Response Time (p99)**: <500ms
- **Embedding Generation**: <50ms
- **Vector Search**: <20ms
- **Token Validation**: <5ms (cached)

### Throughput Targets
- **Concurrent Requests**: 500+ req/sec per instance
- **Token Validation**: 10,000+ validations/sec (Redis cached)
- **Query Cache Hit Rate**: >60%

### Optimization Strategies
- Aggressive Redis caching for:
  - Token validation results (TTL: 5 minutes)
  - Query embeddings (TTL: 1 hour)
  - Query results (TTL: 15 minutes)
- Database connection pooling (25 connections per instance)
- Read replicas for vector search
- Prepared statements for frequent queries
- Async I/O throughout
- Response streaming for large result sets

## API Endpoints

### Search Endpoints

#### Semantic Search
```
POST /api/v1/search
Authorization: Bearer <token>

Request:
{
  "query": "How do I configure SSO?",
  "top_k": 10,
  "sliding_window": 1,  # Include N adjacent chunks before/after each result
  "filters": {
    "source_types": ["confluence", "slack"],
    "source_ids": ["uuid1", "uuid2"],  # Optional, overrides token scope
    "date_range": {
      "start": "2024-01-01T00:00:00Z",
      "end": "2024-12-31T23:59:59Z"
    }
  },
  "options": {
    "include_content": true,
    "include_metadata": true,
    "min_score": 0.7,
    "deduplicate_chunks": true  # Remove duplicate chunks in sliding window
  }
}

Response:
{
  "query_id": "uuid",
  "results": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "score": 0.92,
      "content": "To configure SSO...",  # Main matching chunk
      "extended_content": "...context before... To configure SSO... ...context after...",  # With sliding window
      "document": {
        "id": "uuid",
        "title": "SSO Configuration Guide",
        "url": "https://confluence.../sso-config",
        "source_type": "confluence",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-06-20T14:30:00Z"
      },
      "metadata": {
        "chunk_position": 2,
        "total_chunks": 5,
        "window_size": 1,
        "included_positions": [1, 2, 3]  # Positions included in extended_content
      },
      "highlights": [
        "configure <em>SSO</em> by navigating to..."
      ]
    }
  ],
  "total": 47,
  "took_ms": 85,
  "cached": false
}
```

#### Hybrid Search (Semantic + Keyword)
```
POST /api/v1/search/hybrid
Authorization: Bearer <token>

Request:
{
  "query": "docker configuration",
  "semantic_weight": 0.7,
  "keyword_weight": 0.3,
  "top_k": 10
}

Response: Same as semantic search
```

#### Multi-Query Search
```
POST /api/v1/search/multi
Authorization: Bearer <token>

Request:
{
  "queries": [
    "How to deploy?",
    "What are the requirements?",
    "Configuration options?"
  ],
  "top_k_per_query": 5,
  "deduplicate": true
}

Response:
{
  "results": {
    "query_0": [...],
    "query_1": [...],
    "query_2": [...]
  },
  "took_ms": 120
}
```

### Document Retrieval

#### Get Document by ID
```
GET /api/v1/documents/{document_id}
Authorization: Bearer <token>

Response:
{
  "id": "uuid",
  "title": "...",
  "content": "full document content",
  "source_type": "confluence",
  "source_id": "uuid",
  "url": "https://...",
  "metadata": {...},
  "chunks": [
    {
      "id": "uuid",
      "content": "...",
      "position": 0
    }
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

#### Get Similar Documents
```
POST /api/v1/documents/{document_id}/similar
Authorization: Bearer <token>

Request:
{
  "top_k": 10,
  "min_score": 0.75
}

Response: List of similar documents
```

### Health & Monitoring

```
GET /health
- Database read replica connectivity
- Redis connectivity
- OpenAI API availability

GET /metrics
- Prometheus metrics endpoint
- Query latency histograms
- Cache hit rates
- Active connections
- Token usage stats

GET /api/v1/stats
Authorization: Bearer <admin_token>
- Per-token usage statistics
- Query volume trends
- Top queries
- Cache performance
```

## Authentication & Authorization

### Token Structure
```json
{
  "token_id": "uuid",
  "token_hash": "argon2$...",
  "type": "query",
  "name": "Mobile App Production",
  "scopes": {
    "source_ids": ["uuid1", "uuid2", "uuid3"],
    "source_types": ["confluence", "slack"],
    "operations": ["read"]
  },
  "rate_limit": {
    "requests_per_minute": 100,
    "requests_per_day": 10000
  },
  "metadata": {
    "app_name": "mobile-app",
    "environment": "production"
  },
  "created_at": "2024-01-01T00:00:00Z",
  "expires_at": "2025-01-01T00:00:00Z",
  "last_used_at": "2024-06-15T10:30:00Z"
}
```

### Token Validation Middleware
```python
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from functools import lru_cache
import hashlib

security = HTTPBearer()

class TokenValidator:
    def __init__(self, redis_client, db_session):
        self.redis = redis_client
        self.db = db_session
    
    async def validate_token(
        self,
        credentials: HTTPAuthorizationCredentials = Security(security)
    ) -> TokenData:
        """Validate token and return token data with caching"""
        
        token = credentials.credentials
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Check Redis cache first (5 min TTL)
        cache_key = f"token:valid:{token_hash}"
        cached = await self.redis.get(cache_key)
        
        if cached:
            return TokenData.parse_raw(cached)
        
        # Query database
        token_data = await self._validate_from_db(token_hash)
        
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Cache validation result
        await self.redis.setex(
            cache_key,
            300,  # 5 minutes
            token_data.json()
        )
        
        return token_data
    
    async def _validate_from_db(self, token_hash: str) -> Optional[TokenData]:
        """Validate token against database"""
        
        query = select(tokens).where(
            and_(
                tokens.c.token_hash == token_hash,
                tokens.c.expires_at > datetime.utcnow(),
                tokens.c.is_active == True
            )
        )
        
        result = await self.db.execute(query)
        token_row = result.fetchone()
        
        if not token_row:
            return None
        
        # Update last_used_at (async, don't await)
        asyncio.create_task(
            self._update_last_used(token_row.id)
        )
        
        return TokenData.from_orm(token_row)
    
    async def check_scopes(
        self,
        token_data: TokenData,
        requested_source_ids: List[str] = None
    ) -> List[str]:
        """Return list of source_ids token has access to"""
        
        allowed_ids = token_data.scopes.get('source_ids', [])
        
        if not requested_source_ids:
            return allowed_ids
        
        # Filter to only allowed sources
        return [
            sid for sid in requested_source_ids
            if sid in allowed_ids
        ]
```

### Rate Limiting
```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_client):
        super().__init__(app)
        self.redis = redis_client
    
    async def dispatch(self, request: Request, call_next):
        # Extract token from request
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return await call_next(request)
        
        token = auth_header.replace('Bearer ', '')
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Check rate limit
        rate_key_min = f"rate:{token_hash}:min"
        rate_key_day = f"rate:{token_hash}:day"
        
        # Increment counters
        pipe = self.redis.pipeline()
        pipe.incr(rate_key_min)
        pipe.expire(rate_key_min, 60)
        pipe.incr(rate_key_day)
        pipe.expire(rate_key_day, 86400)
        results = await pipe.execute()
        
        requests_this_min = results[0]
        requests_today = results[2]
        
        # Get token limits (from cache or DB)
        limits = await self._get_token_limits(token_hash)
        
        if requests_this_min > limits['per_minute']:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "limit": limits['per_minute'],
                    "reset_at": int(time.time()) + 60
                }
            )
        
        if requests_today > limits['per_day']:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Daily quota exceeded",
                    "limit": limits['per_day'],
                    "reset_at": int(time.time()) + 86400
                }
            )
        
        # Add rate limit headers
        response = await call_next(request)
        response.headers['X-RateLimit-Limit-Minute'] = str(limits['per_minute'])
        response.headers['X-RateLimit-Remaining-Minute'] = str(
            limits['per_minute'] - requests_this_min
        )
        
        return response
```

## Vector Search Implementation

### Search Algorithm: HNSW + Pre-filtering

**Strategy**: Pre-filter by source_ids before vector search
- Use PostgreSQL indexes for source_id filtering
- Then perform vector similarity search on filtered set
- HNSW index for approximate nearest neighbor search

### Query Execution
```python
async def semantic_search(
    query_text: str,
    allowed_source_ids: List[str],
    top_k: int = 10,
    min_score: float = 0.0,
    sliding_window: int = 0,
    filters: Dict = None,
    deduplicate_chunks: bool = True
) -> List[SearchResult]:
    """Execute semantic search with scope filtering and optional sliding window"""
    
    # 1. Generate query embedding (with caching)
    embedding = await get_cached_embedding(query_text)
    
    # 2. Build filtered query
    query = select(
        document_chunks.c.id,
        document_chunks.c.document_id,
        document_chunks.c.content,
        document_chunks.c.position,
        documents.c.title,
        documents.c.url,
        documents.c.source_type,
        documents.c.source_id,
        # Vector similarity score
        document_chunks.c.embedding.cosine_distance(embedding).label('distance')
    ).select_from(
        document_chunks.join(documents)
    ).where(
        # Pre-filter by allowed sources
        documents.c.source_id.in_(allowed_source_ids)
    )
    
    # Apply additional filters
    if filters:
        if 'source_types' in filters:
            query = query.where(
                documents.c.source_type.in_(filters['source_types'])
            )
        
        if 'date_range' in filters:
            dr = filters['date_range']
            query = query.where(
                and_(
                    documents.c.updated_at >= dr['start'],
                    documents.c.updated_at <= dr['end']
                )
            )
    
    # Order by similarity and limit
    query = query.order_by(text('distance')).limit(top_k)
    
    # Execute query
    start_time = time.time()
    result = await db.execute(query)
    rows = result.fetchall()
    query_time_ms = (time.time() - start_time) * 1000
    
    # Convert distance to similarity score
    results = []
    for row in rows:
        score = 1 - row.distance  # Cosine distance to similarity
        
        if score >= min_score:
            # Get extended content if sliding window requested
            extended_content = None
            included_positions = [row.position]
            
            if sliding_window > 0:
                extended_content, included_positions = await get_extended_content(
                    document_id=row.document_id,
                    center_position=row.position,
                    window_size=sliding_window,
                    deduplicate=deduplicate_chunks
                )
            
            results.append(SearchResult(
                chunk_id=row.id,
                document_id=row.document_id,
                score=score,
                content=row.content,
                extended_content=extended_content,
                document=DocumentInfo(
                    id=row.document_id,
                    title=row.title,
                    url=row.url,
                    source_type=row.source_type,
                    source_id=row.source_id
                ),
                metadata={
                    'chunk_position': row.position,
                    'query_time_ms': query_time_ms,
                    'window_size': sliding_window,
                    'included_positions': included_positions
                }
            ))
    
    return results

async def get_extended_content(
    document_id: str,
    center_position: int,
    window_size: int,
    deduplicate: bool = True
) -> Tuple[str, List[int]]:
    """
    Retrieve adjacent chunks to provide context around matching chunk.
    
    Args:
        document_id: Document containing the chunks
        center_position: Position of the matching chunk
        window_size: Number of chunks to include before and after
        deduplicate: Remove chunks if they appear in multiple results
    
    Returns:
        Tuple of (extended_content, list of included positions)
    """
    # Calculate position range
    start_position = max(0, center_position - window_size)
    end_position = center_position + window_size
    
    # Fetch adjacent chunks
    query = select(
        document_chunks.c.content,
        document_chunks.c.position
    ).where(
        and_(
            document_chunks.c.document_id == document_id,
            document_chunks.c.position >= start_position,
            document_chunks.c.position <= end_position
        )
    ).order_by(document_chunks.c.position)
    
    result = await db.execute(query)
    chunks = result.fetchall()
    
    # Combine chunks
    extended_content = ' '.join(chunk.content for chunk in chunks)
    included_positions = [chunk.position for chunk in chunks]
    
    return extended_content, included_positions
```

### Embedding Cache
```python
class EmbeddingCache:
    """Cache embeddings for frequent queries"""
    
    def __init__(self, redis_client, openai_client):
        self.redis = redis_client
        self.openai = openai_client
        self.ttl = 3600  # 1 hour
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding with caching"""
        
        # Create cache key from text hash
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        cache_key = f"embedding:{text_hash}"
        
        # Try cache first
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Generate new embedding
        response = await self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        embedding = response.data[0].embedding
        
        # Cache result
        await self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps(embedding)
        )
        
        return embedding
```

### Hybrid Search (Semantic + Keyword)
```python
async def hybrid_search(
    query_text: str,
    allowed_source_ids: List[str],
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
    top_k: int = 10
) -> List[SearchResult]:
    """Combine semantic and keyword search with weighted scoring"""
    
    # 1. Semantic search
    semantic_results = await semantic_search(
        query_text,
        allowed_source_ids,
        top_k=top_k * 2  # Get more for merging
    )
    
    # 2. Keyword search using PostgreSQL full-text search
    keyword_results = await keyword_search(
        query_text,
        allowed_source_ids,
        top_k=top_k * 2
    )
    
    # 3. Merge and re-rank
    merged = {}
    
    # Add semantic results
    for i, result in enumerate(semantic_results):
        score = result.score * semantic_weight
        merged[result.chunk_id] = {
            'result': result,
            'semantic_score': result.score,
            'semantic_rank': i,
            'combined_score': score
        }
    
    # Add keyword results
    for i, result in enumerate(keyword_results):
        score = result.score * keyword_weight
        
        if result.chunk_id in merged:
            merged[result.chunk_id]['keyword_score'] = result.score
            merged[result.chunk_id]['keyword_rank'] = i
            merged[result.chunk_id]['combined_score'] += score
        else:
            merged[result.chunk_id] = {
                'result': result,
                'keyword_score': result.score,
                'keyword_rank': i,
                'combined_score': score
            }
    
    # Sort by combined score
    sorted_results = sorted(
        merged.values(),
        key=lambda x: x['combined_score'],
        reverse=True
    )
    
    # Return top_k
    return [item['result'] for item in sorted_results[:top_k]]
```

## Caching Strategy

### Multi-Level Caching
1. **Token validation**: Redis, 5 min TTL
2. **Query embeddings**: Redis, 1 hour TTL
3. **Query results**: Redis, 15 min TTL
4. **Document metadata**: Redis, 30 min TTL

### Result Caching
```python
class QueryCache:
    """Cache query results for identical searches"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 900  # 15 minutes
    
    def _cache_key(
        self,
        query: str,
        source_ids: List[str],
        filters: Dict,
        top_k: int
    ) -> str:
        """Generate cache key from query parameters"""
        
        # Normalize parameters
        sorted_sources = sorted(source_ids)
        filters_str = json.dumps(filters, sort_keys=True)
        
        # Create hash
        key_data = f"{query}:{sorted_sources}:{filters_str}:{top_k}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()
        
        return f"query_result:{key_hash}"
    
    async def get(self, query: str, source_ids: List[str], **params) -> Optional[List]:
        """Get cached results"""
        
        cache_key = self._cache_key(query, source_ids, **params)
        cached = await self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        return None
    
    async def set(self, query: str, source_ids: List[str], results: List, **params):
        """Cache query results"""
        
        cache_key = self._cache_key(query, source_ids, **params)
        await self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps([r.dict() for r in results])
        )
```

### Cache Invalidation
```python
async def invalidate_document_cache(document_id: str):
    """Invalidate all cached queries containing this document"""
    
    # Pattern: query_result:*
    # This is expensive, so we use a simpler approach:
    # Set a shorter TTL for query results (15 min)
    # Documents updated less frequently than query cache expires
    
    pass  # Handled by TTL expiration
```

## Connection Pooling

### Database Connection Pool
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Create engine with connection pooling
engine = create_async_engine(
    DATABASE_URL,
    pool_size=25,              # Maintain 25 connections
    max_overflow=10,           # Allow 10 extra during spikes
    pool_pre_ping=True,        # Check connection health
    pool_recycle=3600,         # Recycle connections hourly
    echo=False,
    connect_args={
        "server_settings": {
            "application_name": "query-api",
            "jit": "on"  # PostgreSQL JIT compilation
        }
    }
)

# Session factory
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)
```

### Redis Connection Pool
```python
import redis.asyncio as aioredis

redis_pool = aioredis.ConnectionPool.from_url(
    REDIS_URL,
    max_connections=50,
    decode_responses=True
)

redis_client = aioredis.Redis(connection_pool=redis_pool)
```

## Response Formatting

### Result Highlighting
```python
def highlight_matches(content: str, query: str) -> List[str]:
    """Highlight query terms in content"""
    
    # Simple keyword extraction
    keywords = query.lower().split()
    
    highlighted = content
    for keyword in keywords:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        highlighted = pattern.sub(
            lambda m: f"<em>{m.group()}</em>",
            highlighted
        )
    
    # Extract highlights (surrounding context)
    highlights = []
    for match in re.finditer(r'.{0,50}<em>.*?</em>.{0,50}', highlighted):
        highlights.append(match.group())
    
    return highlights[:3]  # Return top 3 highlights
```

### Response Pagination
```python
@router.post("/api/v1/search")
async def search(
    request: SearchRequest,
    token: TokenData = Depends(token_validator.validate_token),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Paginated search endpoint"""
    
    # Get allowed source IDs
    allowed_sources = await token_validator.check_scopes(
        token,
        request.filters.get('source_ids')
    )
    
    # Execute search with pagination
    results = await semantic_search(
        request.query,
        allowed_sources,
        top_k=offset + limit,  # Fetch up to requested offset + limit
        min_score=request.options.get('min_score', 0.0),
        filters=request.filters
    )
    
    # Slice results for pagination
    paginated_results = results[offset:offset + limit]
    
    return {
        "results": paginated_results,
        "total": len(results),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(results)
    }
```

## Error Handling

### Custom Exceptions
```python
class QueryAPIException(Exception):
    """Base exception for Query API"""
    pass

class TokenInvalidError(QueryAPIException):
    status_code = 401
    detail = "Invalid or expired token"

class TokenInsufficientScopeError(QueryAPIException):
    status_code = 403
    detail = "Token does not have access to requested sources"

class RateLimitExceededError(QueryAPIException):
    status_code = 429
    detail = "Rate limit exceeded"

class SearchTimeoutError(QueryAPIException):
    status_code = 504
    detail = "Search query timed out"
```

### Error Handler
```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(QueryAPIException)
async def query_api_exception_handler(request: Request, exc: QueryAPIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "detail": exc.detail,
            "request_id": request.state.request_id
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log error
    logger.exception(
        "unhandled_exception",
        error=str(exc),
        request_id=request.state.request_id,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "detail": "An unexpected error occurred",
            "request_id": request.state.request_id
        }
    )
```

## Monitoring & Observability

### Request Tracing
```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers['X-Request-ID'] = request_id
        
        return response
```

### Metrics Collection
```python
from prometheus_client import Histogram, Counter, Gauge

# Query metrics
query_duration = Histogram(
    'query_api_query_duration_seconds',
    'Query execution duration',
    ['endpoint', 'status'],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
)

query_cache_hits = Counter(
    'query_api_cache_hits_total',
    'Number of cache hits',
    ['cache_type']
)

query_results_count = Histogram(
    'query_api_results_count',
    'Number of results returned per query',
    buckets=[1, 5, 10, 20, 50, 100]
)

active_tokens = Gauge(
    'query_api_active_tokens',
    'Number of active tokens'
)

# Usage
@query_duration.labels(endpoint='search', status='success').time()
async def execute_search():
    # ... search logic
    pass
```

## Testing Strategy

### Unit Tests
- Token validation logic
- Scope checking
- Search algorithm correctness
- Caching behavior
- Rate limiting

### Integration Tests
- End-to-end search flow
- Token authorization
- Database queries
- Redis operations
- Error handling

### Load Tests
- Concurrent request handling
- Cache performance under load
- Database connection pool limits
- Rate limiting accuracy

### Performance Tests
```python
import asyncio
import time
from locust import HttpUser, task, between

class QueryAPIUser(HttpUser):
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        # Get auth token
        self.token = "test-token-here"
    
    @task(10)
    def search(self):
        self.client.post(
            "/api/v1/search",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "query": "test query",
                "top_k": 10
            }
        )
    
    @task(1)
    def get_document(self):
        self.client.get(
            f"/api/v1/documents/{self.random_doc_id()}",
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

## Configuration

### Environment Variables
```bash
# Database (read replica for queries)
DATABASE_URL=postgresql+asyncpg://user:pass@read-replica/ragdb
DATABASE_POOL_SIZE=25
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50

# OpenAI
OPENAI_API_KEY=sk-...

# Caching
QUERY_CACHE_TTL=900
EMBEDDING_CACHE_TTL=3600
TOKEN_CACHE_TTL=300

# Performance
SEARCH_TIMEOUT_SECONDS=5
MAX_RESULTS_PER_QUERY=100

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true
```

## File Structure
```
services/query-api/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── search.py
│   │   │   ├── documents.py
│   │   │   └── health.py
│   │   └── dependencies.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── request.py
│   │   ├── response.py
│   │   └── token.py
│   ├── search/
│   │   ├── __init__.py
│   │   ├── semantic.py
│   │   ├── hybrid.py
│   │   └── ranking.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── rate_limit.py
│   │   └── request_id.py
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── query_cache.py
│   │   └── embedding_cache.py
│   └── utils/
│       ├── __init__.py
│       ├── metrics.py
│       └── logging.py
└── tests/
    ├── unit/
    ├── integration/
    └── load/
```

## Dependencies
```
# Core
fastapi==0.109.0
uvicorn[standard]==0.27.0

# Database
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0
pgvector==0.2.4

# Redis
redis[asyncio]==5.0.1

# OpenAI
openai==1.10.0

# Security
python-jose[cryptography]==3.3.0
passlib[argon2]==1.7.4

# Monitoring
structlog==24.1.0
prometheus-client==0.19.0

# Utilities
pydantic==2.5.3
pydantic-settings==2.1.0
```
