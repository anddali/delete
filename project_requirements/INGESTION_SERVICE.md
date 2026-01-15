# Ingestion Service - Requirements & Features

## Overview

High-performance document ingestion service with plugin-based architecture for processing and indexing documents from multiple sources. Optimized for throughput and extensibility.

## Core Responsibilities

- Fetch documents from external sources via plugins
- Parse and chunk documents for optimal retrieval
- Generate embeddings using OpenAI API
- Store documents and embeddings in PostgreSQL
- Schedule and execute periodic sync jobs
- Handle incremental updates efficiently

## Technology Stack

- **Runtime**: Python 3.11+
- **Framework**: FastAPI (async/await)
- **Task Queue**: Celery 5.3+
- **Message Broker**: Redis
- **HTTP Client**: httpx (async)
- **Database**: asyncpg + SQLAlchemy 2.0 (async)
- **Embedding**: OpenAI Python SDK

## Performance Requirements

### Throughput Targets

- **Initial Ingestion**: Process 1000+ documents/minute
- **Embedding Generation**: Batch 100 embeddings in single API call
- **Concurrent Workers**: Support 5-10 parallel workers
- **API Response Time**: <200ms for ingestion triggers
- **Change Detection**: <5 minutes for detecting updates

### Optimization Strategies

- Async I/O for all external API calls
- Batch processing for embeddings (reduce API overhead)
- Connection pooling for database and Redis
- Parallel document processing per source
- Incremental sync using timestamps/checksums
- Rate limiting with exponential backoff

## API Endpoints

### Ingestion Control

```
POST   /api/v1/ingest/trigger
  - Body: {source_id: uuid, full_sync: bool}
  - Triggers immediate ingestion for source
  - Returns: job_id for tracking

GET    /api/v1/ingest/status/{job_id}
  - Returns: Job status, progress, errors

POST   /api/v1/ingest/cancel/{job_id}
  - Cancels running ingestion job

GET    /api/v1/ingest/sources/{source_id}/stats
  - Returns: Document count, last sync time, errors
```

### Health & Monitoring

```
GET    /health
  - Database connectivity
  - Redis connectivity
  - OpenAI API availability
  - Queue status

GET    /metrics
  - Prometheus-compatible metrics
  - Queue depth, processing rate, error count
```

## Plugin Architecture

### Base Plugin Interface

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any

class BaseIntegrationPlugin(ABC):
    """Base class for all integration plugins"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rate_limiter = self._setup_rate_limiter()

    @abstractmethod
    async def validate_config(self) -> bool:
        """Validate configuration and credentials"""
        pass

    @abstractmethod
    async def fetch_initial(self) -> AsyncIterator[Document]:
        """Fetch all documents for initial sync"""
        pass

    @abstractmethod
    async def fetch_updates(self, since: datetime) -> AsyncIterator[Document]:
        """Fetch documents modified since timestamp"""
        pass

    @abstractmethod
    async def parse_content(self, raw_content: Any) -> str:
        """Parse raw content into plain text"""
        pass

    @abstractmethod
    def get_metadata(self, raw_doc: Any) -> Dict[str, Any]:
        """Extract metadata from document"""
        pass

    async def check_health(self) -> bool:
        """Check if integration is accessible"""
        pass
```

### Plugin Registry

```python
# services/ingestion/app/plugins/__init__.py

PLUGIN_REGISTRY = {
    'confluence': ConfluencePlugin,
    'slack': SlackPlugin,
    'file_upload': FileUploadPlugin,
}

def get_plugin(source_type: str, config: dict) -> BaseIntegrationPlugin:
    plugin_class = PLUGIN_REGISTRY.get(source_type)
    if not plugin_class:
        raise ValueError(f"Unknown source type: {source_type}")
    return plugin_class(config)
```

## Integration Plugins

### 1. Confluence Plugin

**Features**:

- Space-level synchronization
- Page hierarchy preservation
- Attachment indexing
- Version tracking for change detection
- HTML to markdown conversion

**Configuration**:

```json
{
  "type": "confluence",
  "base_url": "https://company.atlassian.net",
  "space_key": "DOCS",
  "credentials": {
    "email": "user@company.com",
    "api_token": "encrypted"
  },
  "options": {
    "include_attachments": true,
    "include_archived": false,
    "sync_frequency": "1h"
  },
  "chunking": {
    "chunk_size_chars": 1000,
    "respect_boundaries": true,
    "min_chunk_size_chars": 200
  }
}
```

**Performance Optimizations**:

- Paginated API calls (100 pages per request)
- Parallel page content fetching
- CQL queries for modified pages only
- Checksum-based change detection

**API Methods**:

- `GET /rest/api/content` - List pages
- `GET /rest/api/content/{id}?expand=body.storage,version` - Get content
- `GET /rest/api/content/search?cql=lastModified>=...` - Find updates

### 2. Slack Plugin

**Features**:

- Channel-based synchronization
- Thread preservation
- User mention resolution
- File attachment indexing
- Reaction and reply metadata

**Configuration**:

```json
{
  "type": "slack",
  "workspace_id": "T1234567890",
  "channel_ids": ["C1234567890", "C0987654321"],
  "credentials": {
    "bot_token": "xoxb-encrypted"
  },
  "options": {
    "include_threads": true,
    "include_files": true,
    "min_message_length": 10,
    "sync_frequency": "15m"
  },
  "chunking": {
    "chunk_size_chars": 800,
    "respect_boundaries": true,
    "min_chunk_size_chars": 150
  }
}
```

**Performance Optimizations**:

- Conversations API with cursor pagination
- Bulk message fetching (200 per request)
- Timestamp-based incremental sync
- Parallel channel processing

**API Methods**:

- `conversations.history` - Get messages
- `conversations.replies` - Get thread replies
- `users.info` - Resolve user names

### 3. File Upload Plugin

**Features**:

- Support for multiple file types (PDF, DOCX, TXT, MD, HTML, JSON, CSV, XML)
- Batch upload processing
- Automatic file type detection
- Text extraction from binary formats
- Local file storage (simplified architecture)

**Architecture**:

```
Upload Flow:
┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Admin UI   │────▶│  Management API  │────▶│ Ingestion Service │
│  (Upload)   │     │  (Parse + Store) │     │ (Chunk + Embed)   │
└─────────────┘     └──────────────────┘     └───────────────────┘
                           │                          │
                           ▼                          ▼
                    ┌─────────────┐           ┌─────────────┐
                    │ Local Disk  │           │  PostgreSQL │
                    │ /app/uploads│           │  (pgvector) │
                    └─────────────┘           └─────────────┘
```

1. **Management API** handles upload:

   - Receives file via multipart form
   - Parses content using file-type-specific parsers
   - Saves original file to local disk (`/app/uploads/{source_id}/`)
   - Creates Document record with parsed text content
   - Triggers Ingestion Service to chunk and embed

2. **Ingestion Service** processes document:
   - Receives document ID via `/ingest/process-document`
   - Chunks the parsed text content
   - Generates embeddings via OpenAI API
   - Stores chunks with embeddings in PostgreSQL

**Configuration**:

```json
{
  "type": "file_upload",
  "processing": {
    "max_file_size_mb": 100,
    "allowed_extensions": [
      ".pdf",
      ".docx",
      ".txt",
      ".md",
      ".html",
      ".json",
      ".csv",
      ".xml"
    ]
  },
  "chunking": {
    "chunk_size_chars": 1200,
    "respect_boundaries": true,
    "min_chunk_size_chars": 250
  }
}
```

**File Parsers** (in Management API):

- **PDF**: pdfplumber (fast, accurate text extraction)
- **DOCX**: python-docx (paragraphs + tables)
- **HTML**: BeautifulSoup with lxml (removes scripts/styles)
- **TXT/MD**: Direct UTF-8 read with fallback encodings
- **JSON**: Recursive text extraction from structure
- **CSV**: Row-by-row with header labels
- **XML**: Element text extraction

**API Endpoints**:

```
POST /sources/{source_id}/upload
  - Single file upload
  - Parses content, stores document, triggers processing
  - Returns: document_id, filename, size, text_length

POST /sources/{source_id}/upload-multiple
  - Multiple file upload
  - Same processing per file
  - Returns: uploaded[], errors[], totals

POST /ingest/process-document (Ingestion Service)
  - Chunks and embeds a parsed document
  - Called by Management API after upload
  - Body: {source_id, document_id}
```

**Performance Optimizations**:

- Streaming file reads (avoid memory issues)
- Parallel file processing for batch uploads
- Content hash deduplication
- HTML: BeautifulSoup with lxml parser
- TXT/MD: Direct read

## Document Processing Pipeline

### 1. Content Extraction

```python
async def extract_content(plugin: BaseIntegrationPlugin, raw_doc: Any) -> Document:
    # Parse content to plain text
    content = await plugin.parse_content(raw_doc)

    # Extract metadata
    metadata = plugin.get_metadata(raw_doc)

    # Create document object
    return Document(
        source_id=metadata['source_id'],
        external_id=metadata['id'],
        title=metadata['title'],
        content=content,
        metadata=metadata,
        url=metadata.get('url'),
        created_at=metadata['created_at'],
        updated_at=metadata['updated_at']
    )
```

### 2. Chunking Strategy

**Algorithm**: Sequential Character-Based Chunking (No Overlap)

- Configurable chunk size per source (character count)
- No overlap during chunking (overlap handled at query time via sliding window)
- Preserves natural boundaries when possible (paragraphs, sentences)
- Sequential position tracking for adjacent chunk retrieval

**Configurable Parameters** (per source):

- `chunk_size_chars`: Character count per chunk (default: 1000, range: 500-4000)
- `respect_boundaries`: Try to break at sentence/paragraph boundaries (default: true)
- `min_chunk_size_chars`: Minimum chunk size (default: 200)

**Implementation**:

```python
from typing import List
import re

def chunk_document(
    content: str,
    metadata: dict,
    chunk_size_chars: int = 1000,
    respect_boundaries: bool = True
) -> List[Chunk]:
    """Split document into sequential chunks without overlap"""
    chunks = []
    position = 0
    chunk_index = 0

    while position < len(content):
        # Calculate end position
        end_position = min(position + chunk_size_chars, len(content))

        # Try to respect boundaries if enabled
        if respect_boundaries and end_position < len(content):
            # Look for paragraph break first
            paragraph_break = content.rfind('\n\n', position, end_position)
            if paragraph_break > position + (chunk_size_chars * 0.7):  # At least 70% of chunk size
                end_position = paragraph_break + 2
            else:
                # Look for sentence break
                sentence_break = max(
                    content.rfind('. ', position, end_position),
                    content.rfind('.\n', position, end_position),
                    content.rfind('! ', position, end_position),
                    content.rfind('? ', position, end_position)
                )
                if sentence_break > position + (chunk_size_chars * 0.7):
                    end_position = sentence_break + 2

        # Extract chunk
        chunk_text = content[position:end_position].strip()

        if len(chunk_text) > 0:
            chunks.append(Chunk(
                content=chunk_text,
                position=chunk_index,  # Sequential position for sliding window
                char_start=position,   # Character offset in document
                char_end=end_position,
                char_count=len(chunk_text),
                metadata={
                    **metadata,
                    'chunk_position': chunk_index,
                    'total_chars': len(content)
                }
            ))
            chunk_index += 1

        position = end_position

    return chunks
```

**Benefits**:

- No duplicate content across chunks (more efficient storage)
- Configurable per source type (technical docs might need larger chunks)
- Adjacent chunks retrieved via sliding window at query time
- Better semantic coherence per chunk
- Process 1000-character document in <10ms

**Database Storage**:
Chunks store sequential position to enable efficient adjacent chunk retrieval:

```sql
-- Retrieve chunk with sliding window
SELECT * FROM document_chunks
WHERE document_id = $1
AND position BETWEEN $chunk_position - $window_size
                 AND $chunk_position + $window_size
ORDER BY position;
```

### 3. Embedding Generation

**Provider**: OpenAI `text-embedding-3-small` (1536 dimensions)

- Cost effective: $0.02 per 1M tokens
- Fast: ~3000 embeddings/sec
- High quality for retrieval

**Batch Processing**:

```python
async def generate_embeddings_batch(chunks: List[str]) -> List[List[float]]:
    """Generate embeddings in batches for efficiency"""

    # OpenAI supports up to 2048 inputs per request
    batch_size = 100
    all_embeddings = []

    async with httpx.AsyncClient() as client:
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "input": batch,
                    "model": "text-embedding-3-small"
                },
                timeout=30.0
            )

            data = response.json()
            embeddings = [item['embedding'] for item in data['data']]
            all_embeddings.extend(embeddings)

    return all_embeddings
```

**Error Handling**:

- Retry with exponential backoff (3 attempts)
- Rate limit handling (429 errors)
- Fallback to smaller batches on timeout
- Cache embeddings for identical chunks

### 4. Storage

**Database Operations**:

```python
async def store_document_with_chunks(
    db: AsyncSession,
    document: Document,
    chunks: List[Chunk],
    embeddings: List[List[float]]
):
    """Store document, chunks, and embeddings atomically"""

    async with db.begin():
        # Insert document
        doc_result = await db.execute(
            insert(documents).values(**document.dict()).returning(documents.c.id)
        )
        doc_id = doc_result.scalar_one()

        # Prepare bulk insert for chunks and embeddings
        chunk_values = []
        for chunk, embedding in zip(chunks, embeddings):
            chunk_values.append({
                'document_id': doc_id,
                'content': chunk.content,
                'embedding': embedding,  # pgvector handles this
                'position': chunk.position,
                'token_count': chunk.token_count,
                'metadata': chunk.metadata
            })

        # Bulk insert (much faster than individual inserts)
        await db.execute(insert(document_chunks).values(chunk_values))
```

**Performance**: Bulk insert 1000 chunks in <100ms

## Celery Worker Configuration

### Task Definitions

```python
# services/ingestion/app/workers/tasks.py

from celery import Celery, Task
from celery.schedules import crontab

celery_app = Celery('ingestion')

class CallbackTask(Task):
    """Base task with error handling and retry logic"""

    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

@celery_app.task(bind=True, base=CallbackTask)
async def ingest_source(self, source_id: str, full_sync: bool = False):
    """Main ingestion task"""

    # Update job status to 'running'
    await update_job_status(self.request.id, 'running')

    try:
        # Get source configuration
        source = await get_source(source_id)
        plugin = get_plugin(source.type, source.config)

        # Fetch documents
        if full_sync:
            docs = plugin.fetch_initial()
        else:
            last_sync = source.last_sync_at or datetime.min
            docs = plugin.fetch_updates(since=last_sync)

        # Process documents
        processed = 0
        async for doc in docs:
            await process_document(doc, plugin)
            processed += 1

            # Update progress every 10 documents
            if processed % 10 == 0:
                self.update_state(
                    state='PROGRESS',
                    meta={'processed': processed}
                )

        # Update source last_sync_at
        await update_source_sync_time(source_id)
        await update_job_status(self.request.id, 'completed', processed)

    except Exception as e:
        await update_job_status(self.request.id, 'failed', error=str(e))
        raise

@celery_app.task
async def process_document(doc: Document, plugin: BaseIntegrationPlugin):
    """Process single document: chunk, embed, store"""

    # Check if document already exists and hasn't changed
    existing = await get_document_by_external_id(doc.external_id)
    if existing and existing.checksum == doc.checksum:
        return  # Skip unchanged document

    # Extract and chunk content
    content = await plugin.parse_content(doc.raw_content)
    chunks = chunk_document(content, doc.metadata)

    # Generate embeddings
    chunk_texts = [c.content for c in chunks]
    embeddings = await generate_embeddings_batch(chunk_texts)

    # Store in database
    await store_document_with_chunks(doc, chunks, embeddings)

@celery_app.task
async def cleanup_deleted_documents(source_id: str, current_ids: List[str]):
    """Remove documents that no longer exist in source"""
    await delete_documents_not_in_list(source_id, current_ids)
```

### Beat Schedule

```python
# Periodic task scheduling
celery_app.conf.beat_schedule = {
    'sync-confluence-spaces': {
        'task': 'workers.tasks.scheduled_sync',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'args': ('confluence',)
    },
    'sync-slack-channels': {
        'task': 'workers.tasks.scheduled_sync',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'args': ('slack',)
    },
    'cleanup-old-jobs': {
        'task': 'workers.tasks.cleanup_jobs',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}

@celery_app.task
async def scheduled_sync(source_type: str):
    """Find all sources of type and trigger sync"""
    sources = await get_sources_by_type(source_type)
    for source in sources:
        ingest_source.delay(source.id, full_sync=False)
```

### Worker Configuration

```python
# celeryconfig.py

broker_url = 'redis://redis:6379/0'
result_backend = 'redis://redis:6379/0'

# Performance settings
worker_prefetch_multiplier = 4  # Prefetch 4 tasks per worker
worker_max_tasks_per_child = 1000  # Restart worker after 1000 tasks
worker_disable_rate_limits = False

# Concurrency
worker_concurrency = 4  # 4 concurrent task executions per worker

# Task routing
task_routes = {
    'workers.tasks.ingest_source': {'queue': 'ingestion'},
    'workers.tasks.process_document': {'queue': 'processing'},
    'workers.tasks.cleanup_*': {'queue': 'maintenance'},
}

# Result expiration
result_expires = 3600  # Results expire after 1 hour

# Task time limits
task_time_limit = 3600  # Hard limit: 1 hour
task_soft_time_limit = 3300  # Soft limit: 55 minutes

# Retry configuration
task_acks_late = True  # Acknowledge after task completion
task_reject_on_worker_lost = True
```

## Error Handling & Resilience

### Retry Strategy

```python
class RetryConfig:
    max_retries = 3
    retry_delays = [1, 5, 15]  # seconds

    @staticmethod
    async def execute_with_retry(func, *args, **kwargs):
        for attempt in range(RetryConfig.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == RetryConfig.max_retries - 1:
                    raise
                await asyncio.sleep(RetryConfig.retry_delays[attempt])
```

### Circuit Breaker

```python
class CircuitBreaker:
    """Prevent cascading failures to external services"""

    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open

    async def call(self, func, *args, **kwargs):
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'half_open'
            else:
                raise CircuitBreakerOpen()

        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
```

### Rate Limiting

```python
class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, rate: int, per: int):
        self.rate = rate  # tokens
        self.per = per  # seconds
        self.allowance = rate
        self.last_check = time.time()

    async def acquire(self):
        current = time.time()
        time_passed = current - self.last_check
        self.last_check = current

        self.allowance += time_passed * (self.rate / self.per)
        if self.allowance > self.rate:
            self.allowance = self.rate

        if self.allowance < 1.0:
            sleep_time = (1.0 - self.allowance) * (self.per / self.rate)
            await asyncio.sleep(sleep_time)
            self.allowance = 0.0
        else:
            self.allowance -= 1.0
```

## Monitoring & Observability

### Logging

```python
import structlog

logger = structlog.get_logger()

# Structured logging example
logger.info(
    "document_processed",
    document_id=doc.id,
    source_type=source.type,
    chunk_count=len(chunks),
    processing_time_ms=elapsed * 1000
)
```

### Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
documents_processed = Counter(
    'ingestion_documents_processed_total',
    'Total documents processed',
    ['source_type', 'status']
)

processing_duration = Histogram(
    'ingestion_processing_duration_seconds',
    'Document processing duration',
    ['source_type']
)

queue_depth = Gauge(
    'ingestion_queue_depth',
    'Current queue depth',
    ['queue_name']
)

# Usage
with processing_duration.labels(source_type='confluence').time():
    await process_document(doc)

documents_processed.labels(
    source_type='confluence',
    status='success'
).inc()
```

## Testing Strategy

### Unit Tests

- Plugin interface compliance
- Chunking algorithm correctness
- Embedding batch processing
- Error handling and retries

### Integration Tests

- Database operations
- Redis queue operations
- External API mocking
- End-to-end ingestion flow

### Performance Tests

- Throughput benchmarks
- Concurrent processing load
- Memory usage profiling
- Embedding generation latency

## Configuration Management

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/ragdb

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...

# S3 (optional)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=rag-uploads

# Performance
MAX_WORKERS=5
BATCH_SIZE=100
EMBEDDING_BATCH_SIZE=100

# Monitoring
LOG_LEVEL=INFO
SENTRY_DSN=https://...
```

## File Structure

```
services/ingestion/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── celeryconfig.py
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Configuration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py           # API endpoints
│   │   └── dependencies.py     # FastAPI dependencies
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── celery_app.py       # Celery setup
│   │   └── tasks.py            # Celery tasks
│   ├── plugins/
│   │   ├── __init__.py
│   │   ├── base.py             # Base plugin class
│   │   ├── confluence.py
│   │   ├── slack.py
│   │   └── file_upload.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── document.py
│   │   └── job.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chunking.py
│   │   ├── embedding.py
│   │   └── storage.py
│   └── utils/
│       ├── __init__.py
│       ├── retry.py
│       ├── rate_limit.py
│       └── logging.py
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

## Dependencies

```
# Core
fastapi==0.109.0
uvicorn[standard]==0.27.0
celery==5.3.6
redis==5.0.1

# Database
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0
pgvector==0.2.4

# HTTP & External APIs
httpx==0.26.0
atlassian-python-api==3.41.0  # Confluence
slack-sdk==3.26.2

# Document processing
beautifulsoup4==4.12.3
lxml==5.1.0
pypdf2==3.0.1
python-docx==1.1.0
tiktoken==0.5.2

# OpenAI
openai==1.10.0

# Monitoring
structlog==24.1.0
prometheus-client==0.19.0

# Utilities
pydantic==2.5.3
pydantic-settings==2.1.0
python-dotenv==1.0.1
```
