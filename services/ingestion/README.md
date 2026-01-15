# Ingestion Service

High-performance document ingestion service with plugin-based architecture for processing and indexing documents from multiple sources.

## Features

- **Plugin Architecture**: Extensible plugin system for different data sources

  - Confluence integration
  - Slack integration
  - File upload support (PDF, DOCX, TXT, MD)

- **Sequential Chunking (No Overlap)**: Documents are split into sequential chunks without overlap

  - Configurable chunk size per source
  - Respects natural boundaries (sentences, paragraphs)
  - Sliding window retrieval at query time for context

- **Batch Embedding Generation**: Efficient embedding generation using OpenAI API

  - Batches of 100 embeddings per API call
  - Caching for identical chunks

- **Async Task Processing**: Celery workers for background processing
  - Parallel document processing
  - Retry logic with exponential backoff
  - Progress tracking

## API Endpoints

### Ingestion Control

```
POST /api/v1/ingest/trigger
  - Trigger ingestion for a source
  - Body: { "source_id": "uuid", "full_sync": false }

GET /api/v1/ingest/status/{job_id}
  - Get job status and progress

POST /api/v1/ingest/cancel/{job_id}
  - Cancel running job

GET /api/v1/ingest/sources/{source_id}/stats
  - Get source ingestion statistics
```

### Health

```
GET /health
  - Service health check

GET /metrics
  - Prometheus metrics
```

## Environment Variables

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://redis:6379/0
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...
MAX_WORKERS=5
BATCH_SIZE=100
EMBEDDING_BATCH_SIZE=100
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run worker
celery -A app.workers.celery_app worker --loglevel=info

# Run beat scheduler
celery -A app.workers.celery_app beat --loglevel=info
```

## Docker

```bash
docker build -t rag-ingestion .
docker run -p 8000:8000 rag-ingestion
```
