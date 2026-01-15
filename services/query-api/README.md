# Query API Service

Production-ready query API for semantic search with sliding window context retrieval.

## Features

- **Semantic Search**: Vector similarity search using pgvector HNSW indexes
- **Sliding Window Retrieval**: Adjacent chunk fetching (0-3 chunks) at query time
- **Token Authentication**: API token validation with scope checking
- **Redis Caching**: Query result caching with configurable TTL
- **Source Filtering**: Filter results by source or source type
- **Metadata Filtering**: Filter by document/chunk metadata

## API Endpoints

### Search

- `POST /query/search` - Semantic search with sliding window
- `POST /query/search/batch` - Batch search (multiple queries)

### Source Info

- `GET /query/sources` - List accessible sources

### Health

- `GET /health` - Health check
- `GET /health/ready` - Readiness probe

## Configuration

| Variable                 | Description                  | Default  |
| ------------------------ | ---------------------------- | -------- |
| `DATABASE_URL`           | PostgreSQL connection string | required |
| `REDIS_URL`              | Redis connection string      | required |
| `OPENAI_API_KEY`         | OpenAI API key               | required |
| `CACHE_TTL_SECONDS`      | Query cache TTL              | 300      |
| `MAX_RESULTS`            | Maximum results per query    | 20       |
| `DEFAULT_SLIDING_WINDOW` | Default sliding window size  | 1        |

## Sliding Window

The sliding window parameter (0-3) retrieves adjacent chunks at query time:

- `0`: Only the matching chunk
- `1`: Matching chunk + 1 before + 1 after
- `2`: Matching chunk + 2 before + 2 after
- `3`: Matching chunk + 3 before + 3 after

This provides flexible context without storage overhead.

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## Docker

```bash
docker build -t query-api .
docker run -p 8001:8001 --env-file .env query-api
```
