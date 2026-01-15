# RAG Knowledge Indexing System

A high-performance, production-ready Retrieval-Augmented Generation (RAG) knowledge indexing system built with Python, FastAPI, PostgreSQL with pgvector, and Next.js.

## 🌟 Features

- **Multi-Source Ingestion**: Support for Confluence, Slack, and file uploads (PDF, DOCX, TXT, MD, HTML)
- **Intelligent Chunking**: Semantic chunking with NO overlap during storage, configurable sliding window at query time
- **Vector Search**: High-performance semantic search using pgvector with HNSW indexes
- **Real-time Sync**: Scheduled and on-demand synchronization of knowledge sources
- **Modern Admin UI**: Beautiful Next.js 14 dashboard for system management
- **Enterprise Security**: JWT authentication, RBAC, API tokens, and encrypted credentials
- **Scalable Architecture**: Docker-ready microservices with horizontal scaling support

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Nginx                                │
│                   (Reverse Proxy)                           │
└─────────────┬──────────────┬──────────────┬────────────────┘
              │              │              │
              ▼              ▼              ▼
        ┌─────────┐    ┌──────────┐   ┌────────────┐
        │Admin UI │    │Query API │   │Management  │
        │(Next.js)│    │ (x2)     │   │   API      │
        └─────────┘    └────┬─────┘   └──────┬─────┘
                            │                │
              ┌─────────────┴────────────────┤
              │                              │
              ▼                              ▼
        ┌──────────┐                  ┌─────────────┐
        │PostgreSQL│◄─────────────────│  Ingestion  │
        │+pgvector │                  │  Service    │
        └──────────┘                  └──────┬──────┘
              ▲                              │
              │                              ▼
        ┌─────┴─────┐                 ┌─────────────┐
        │   Redis   │◄────────────────│   Celery    │
        │(Cache/Q)  │                 │  Workers    │
        └───────────┘                 └─────────────┘
```

## 📦 Services

| Service        | Port | Description                                     |
| -------------- | ---- | ----------------------------------------------- |
| Admin UI       | 3000 | Next.js 14 administrative dashboard             |
| Management API | 8001 | Authentication, source management, tokens, jobs |
| Query API      | 8002 | Semantic search with sliding window support     |
| Ingestion API  | 8003 | Document ingestion and processing               |

## 🚀 Quick Start

### Prerequisites

- Docker 24.0+
- Docker Compose 2.20+
- Node.js 20+ (for local development)
- Python 3.11+ (for local development)
- OpenAI API key

### Development Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd rag-knowledge-system
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

3. **Start the development environment**

   On Linux/macOS:

   ```bash
   ./scripts/setup-dev.sh
   ```

   On Windows:

   ```cmd
   scripts\setup-dev.bat
   ```

4. **Access the services**

   - Admin UI: http://localhost:3000
   - Management API: http://localhost:8001/docs
   - Query API: http://localhost:8002/docs
   - MinIO Console: http://localhost:9001

5. **Default admin credentials**
   - Email: `admin@example.com`
   - Password: `admin123!`

### Manual Setup

If you prefer manual setup:

```bash
# Start infrastructure
docker compose -f docker-compose.dev.yml up -d postgres redis minio

# Wait for PostgreSQL
docker compose -f docker-compose.dev.yml exec postgres pg_isready -U raguser

# Run migrations
docker compose -f docker-compose.dev.yml run --rm management-api alembic upgrade head

# Start all services
docker compose -f docker-compose.dev.yml up -d
```

## 📖 Documentation

- [System Overview](project_requirements/SYSTEM_OVERVIEW.md)
- [Database Schema](project_requirements/DATABASE_SCHEMA.md)
- [Chunking Strategy](project_requirements/CHUNKING_STRATEGY.md)
- [Deployment Guide](project_requirements/DEPLOYMENT.md)
- [Environment Configuration](project_requirements/ENVIRONMENT_CONFIG.md)

### API Documentation

Each service provides interactive API documentation:

- Management API: http://localhost:8001/docs
- Query API: http://localhost:8002/docs
- Ingestion API: http://localhost:8003/docs

## 🔧 Configuration

### Environment Variables

| Variable                    | Description                            | Default                    |
| --------------------------- | -------------------------------------- | -------------------------- |
| `DATABASE_URL`              | PostgreSQL connection string           | Required                   |
| `REDIS_URL`                 | Redis connection string                | `redis://localhost:6379/0` |
| `OPENAI_API_KEY`            | OpenAI API key for embeddings          | Required                   |
| `JWT_SECRET_KEY`            | Secret for JWT tokens                  | Required                   |
| `CREDENTIAL_ENCRYPTION_KEY` | 32-char key for encrypting credentials | Required                   |

See [.env.example](.env.example) for all configuration options.

### Chunking Configuration

The system uses a **NO OVERLAP** chunking strategy:

- Documents are chunked without overlap during ingestion (storage efficient)
- Sliding window (0-3 chunks) is applied at query time (configurable context)

```python
# Example search with sliding window
response = await client.post("/search", json={
    "query": "What is the company vacation policy?",
    "window_size": 2,  # Include 2 chunks before and after
    "top_k": 10
})
```

## 🔌 Integrations

### Confluence

Connect to Atlassian Confluence to index wiki pages and documentation.

```json
{
  "type": "confluence",
  "config": {
    "base_url": "https://your-company.atlassian.net",
    "email": "user@company.com",
    "api_token": "your-api-token",
    "space_key": "DOCS"
  }
}
```

### Slack

Index Slack channels and threads for searchable knowledge.

```json
{
  "type": "slack",
  "config": {
    "bot_token": "xoxb-your-bot-token",
    "channel_ids": ["C12345678"],
    "include_threads": true
  }
}
```

### File Upload

Upload and index various document formats.

Supported formats:

- PDF (`.pdf`)
- Word Documents (`.docx`)
- Plain Text (`.txt`)
- Markdown (`.md`)
- HTML (`.html`, `.htm`)

## 🛡️ Security

### Authentication

- **Admin UI/Management API**: JWT-based authentication with refresh tokens
- **Query API**: API token authentication with scoped permissions

### Role-Based Access Control (RBAC)

| Role          | Permissions                          |
| ------------- | ------------------------------------ |
| `super_admin` | Full system access                   |
| `editor`      | Manage sources and tokens, view logs |
| `viewer`      | Read-only dashboard access           |

### Credential Encryption

Integration credentials are encrypted at rest using Fernet symmetric encryption.

## 📊 Monitoring

### Health Checks

Each service exposes a `/health` endpoint for monitoring.

### Metrics

Enable Prometheus metrics collection:

```bash
docker compose --profile monitoring up -d
```

Access:

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

### Development Tools

Enable development tools:

```bash
docker compose -f docker-compose.dev.yml --profile tools up -d
```

Access:

- pgAdmin: http://localhost:5050
- Redis Commander: http://localhost:8081
- Flower (Celery): http://localhost:5555

## 🧪 Testing

```bash
# Run all tests
docker compose -f docker-compose.dev.yml run --rm management-api pytest

# Run with coverage
docker compose -f docker-compose.dev.yml run --rm management-api pytest --cov=app

# Run specific service tests
docker compose -f docker-compose.dev.yml run --rm query-api pytest tests/
```

## 🚢 Production Deployment

See [DEPLOYMENT.md](project_requirements/DEPLOYMENT.md) for detailed production deployment instructions.

Quick production start:

```bash
# Build and start production services
docker compose up -d --build

# Scale Query API
docker compose up -d --scale query-api=4
```

## 📁 Project Structure

```
.
├── docker-compose.yml          # Production configuration
├── docker-compose.dev.yml      # Development configuration
├── nginx/
│   ├── nginx.conf              # Production Nginx config
│   └── nginx.dev.conf          # Development Nginx config
├── scripts/
│   ├── setup-dev.sh            # Development setup (Linux/macOS)
│   ├── setup-dev.bat           # Development setup (Windows)
│   ├── init-db.sql             # Database initialization
│   └── create-admin.py         # Admin user creation
├── shared/
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic schemas
│   ├── migrations/             # Alembic migrations
│   └── security.py             # Security utilities
├── services/
│   ├── admin-ui/               # Next.js 14 admin dashboard
│   ├── ingestion/              # Ingestion service + Celery workers
│   ├── management-api/         # Management API
│   └── query-api/              # Query API
├── monitoring/
│   ├── prometheus.yml          # Prometheus configuration
│   └── grafana/                # Grafana dashboards
└── project_requirements/       # Detailed documentation
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [pgvector](https://github.com/pgvector/pgvector) - Open-source vector similarity search for PostgreSQL
- [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast Python web framework
- [Next.js](https://nextjs.org/) - React framework for production
- [OpenAI](https://openai.com/) - Embedding models
