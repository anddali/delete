# RAG Knowledge Indexing System - Architecture Overview

## System Philosophy

This system is built with three core principles:

1. **Performance First**: Every algorithmic choice optimized for throughput and latency
2. **Extensibility**: Plugin-based architecture for easy integration additions
3. **Production Ready**: Clean separation of concerns, proper error handling, observability

## High-Level Architecture

```
┌─────────────────┐
│   Admin UI      │
│   (Next.js)     │
└────────┬────────┘
         │
    ┌────┴────┐
    │  Nginx  │ (Reverse Proxy, Rate Limiting)
    └────┬────┘
         │
    ┌────┴──────────────────────┐
    │                           │
┌───▼─────────────┐   ┌────────▼────────┐
│ Management API  │   │   Query API     │
│  (FastAPI)      │   │   (FastAPI)     │
└───┬─────────────┘   └────────┬────────┘
    │                          │
    │    ┌────────────────────┬┘
    │    │                    │
┌───▼────▼──────┐   ┌─────────▼────────┐
│  PostgreSQL   │   │      Redis       │
│  (+ pgvector) │   │  (Cache/Queue)   │
└───────┬───────┘   └─────────┬────────┘
        │                     │
    ┌───▼─────────────────────▼───┐
    │   Ingestion Service         │
    │   ┌──────────────────────┐  │
    │   │  API + Workers       │  │
    │   │  (FastAPI + Celery)  │  │
    │   └──────────────────────┘  │
    │   ┌──────────────────────┐  │
    │   │  Integration Plugins │  │
    │   │  - Confluence        │  │
    │   │  - Slack            │  │
    │   │  - File Upload      │  │
    │   └──────────────────────┘  │
    └─────────────────────────────┘
```

## Component Breakdown

### 1. Ingestion Service

- **Language**: Python 3.11+ (performance optimized)
- **Framework**: FastAPI (async I/O)
- **Task Queue**: Celery with Redis backend
- **Purpose**: Document ingestion, embedding generation, change detection

### 2. Management API

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Purpose**: Administrative operations, source management, token management

### 3. Query API

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Purpose**: High-throughput semantic search with token-based access control

### 4. Admin UI

- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript
- **Purpose**: Web interface for system administration

### 5. Data Layer

- **Primary DB**: PostgreSQL 15+ with pgvector extension
- **Cache/Queue**: Redis 7+
- **File Storage**: Local disk storage (`/app/uploads/`) - simplified architecture without S3 dependency

## Performance Optimizations

### Database

- pgvector with HNSW indexes for sub-millisecond similarity search
- Connection pooling (pgbouncer or SQLAlchemy pool)
- Read replicas for query scaling
- Partitioning for large document tables

### Caching Strategy

- Redis for:
  - Query result caching (TTL-based)
  - Token validation caching
  - Rate limiting counters
  - Embedding cache for frequent queries

### Async Processing

- All I/O operations are async (database, HTTP, Redis)
- Parallel embedding generation for batches
- Concurrent API calls to external services (Confluence, Slack)

### Query Optimization

- Pre-filter by source_ids using indexes before vector search
- Batch embedding generation
- Connection pooling for all external services
- Streaming responses for large result sets

## Extensibility Features

### Plugin System

```
services/ingestion/plugins/
├── base.py              # Abstract base class
├── confluence.py        # Confluence implementation
├── slack.py            # Slack implementation
├── file_upload.py      # File upload implementation
└── __init__.py         # Plugin registry
```

Each integration plugin implements:

- `fetch_initial()`: Initial data pull
- `fetch_updates()`: Incremental updates
- `parse_content()`: Content extraction
- `get_metadata()`: Source-specific metadata

### Adding New Integrations

1. Create new plugin class extending `BaseIntegrationPlugin`
2. Implement required methods
3. Register in plugin registry
4. Add configuration schema to management API
5. Deploy (no core code changes needed)

## Security Model

### Token Types

1. **Admin Tokens**: Full access to management API
2. **Query Tokens**: Scoped read access to specific sources
3. **Service Tokens**: Internal service-to-service communication

### Token Structure

```json
{
  "token_id": "uuid",
  "type": "query|admin|service",
  "scopes": {
    "source_ids": ["uuid1", "uuid2"],
    "operations": ["read", "write"]
  },
  "expires_at": "timestamp",
  "rate_limit": 1000
}
```

### Security Layers

- Token hashing (argon2)
- Rate limiting per token
- API request validation with pydantic
- SQL injection prevention (parameterized queries)
- CORS configuration
- TLS/SSL in production

## Deployment Architecture

### Production (docker-compose.prod.yml)

- Multi-replica query API (horizontal scaling)
- Multiple Celery workers
- Redis Sentinel for HA
- External RDS PostgreSQL
- CloudWatch logging
- Health checks and auto-restart

### Development (docker-compose.dev.yml)

- Single instance of each service
- Local PostgreSQL and Redis
- Hot reload enabled
- Debug logging
- Volume mounts for live code updates

## Monitoring & Observability

### Metrics (Prometheus/CloudWatch)

- Request latency (p50, p95, p99)
- Throughput (requests/sec)
- Queue depth
- Embedding generation time
- Vector search latency
- Error rates

### Logging

- Structured JSON logging
- Request tracing with correlation IDs
- Separate log streams per service
- Error tracking and alerting

### Health Checks

- `/health` endpoints on all services
- Dependency checks (DB, Redis connectivity)
- Queue worker status
- Disk space monitoring

## Scalability Considerations

### Horizontal Scaling

- Query API: Stateless, scale to N replicas
- Ingestion Workers: Scale based on queue depth
- Admin UI: Static assets on CDN

### Vertical Scaling

- PostgreSQL: Larger instance for more connections
- Redis: More memory for larger cache

### Optimization Points

- Batch embedding generation (reduce API calls)
- Asynchronous ingestion (non-blocking)
- Query result pagination
- Connection pooling everywhere
- Prepared statements for frequent queries

## Technology Choices Rationale

### FastAPI over Flask/Django

- Native async support (critical for performance)
- Automatic OpenAPI docs
- Pydantic validation (faster than marshmallow)
- Type safety

### PostgreSQL + pgvector over Pinecone/Weaviate

- Single database for all data (reduced complexity)
- HNSW index performance comparable to specialized DBs
- Cost effective
- Familiar operations tooling

### Celery over Cloud Functions

- Better control over parallelism
- Persistent connections to external APIs
- Retry logic and error handling
- Local development parity

### Redis over RabbitMQ

- Simpler operations
- Multi-purpose (cache + queue + rate limiting)
- Faster for our use case (in-memory)

## Project Structure

```
rag-knowledge-system/
├── docker-compose.yml          # Production compose
├── docker-compose.dev.yml      # Development compose
├── .env.example
├── nginx/
│   └── nginx.conf
├── services/
│   ├── ingestion/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   ├── workers/
│   │   │   ├── plugins/
│   │   │   ├── models/
│   │   │   └── utils/
│   │   └── tests/
│   ├── management-api/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   ├── models/
│   │   │   ├── services/
│   │   │   └── middleware/
│   │   └── tests/
│   ├── query-api/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   ├── models/
│   │   │   ├── search/
│   │   │   └── middleware/
│   │   └── tests/
│   └── admin-ui/
│       ├── Dockerfile
│       ├── package.json
│       ├── next.config.js
│       ├── src/
│       │   ├── app/
│       │   ├── components/
│       │   ├── lib/
│       │   └── types/
│       └── tests/
├── shared/
│   ├── python/           # Shared Python utilities
│   └── typescript/       # Shared TS types
└── docs/
    ├── API.md
    ├── DEPLOYMENT.md
    └── DEVELOPMENT.md
```

## Development Workflow

1. Clone repository
2. Copy `.env.example` to `.env`
3. Run `docker-compose -f docker-compose.dev.yml up`
4. Access services:
   - Admin UI: http://localhost:3000
   - Management API: http://localhost:8001
   - Query API: http://localhost:8002
   - Ingestion API: http://localhost:8003

## Next Steps

Refer to individual component requirement documents:

- `INGESTION_SERVICE.md`
- `MANAGEMENT_API.md`
- `QUERY_API.md`
- `ADMIN_UI.md`
- `DATABASE_SCHEMA.md`
- `DEPLOYMENT.md`
