# Database Schema - Requirements & Design

## Overview
PostgreSQL 15+ database with pgvector extension for high-performance vector similarity search. Optimized for read-heavy workloads with appropriate indexing strategy.

## Technology Requirements
- **PostgreSQL**: 15.0+
- **Extensions**:
  - `pgvector`: Vector similarity search
  - `uuid-ossp`: UUID generation
  - `pg_trgm`: Fuzzy text search
  - `btree_gin`: Composite indexes

## Performance Optimizations
- HNSW indexes for vector search (faster than IVFFlat)
- Partial indexes for filtered queries
- Materialized views for analytics
- Table partitioning for large document tables
- Connection pooling (pgbouncer)
- Read replicas for query API

## Schema Design

### Core Tables

#### 1. admin_users
Admin users who can access the management interface.

```sql
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,  -- Argon2 hash
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'operator', 'viewer')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_admin_users_email ON admin_users(email);
CREATE INDEX idx_admin_users_role ON admin_users(role);
CREATE INDEX idx_admin_users_is_active ON admin_users(is_active);
```

#### 2. sources
Knowledge sources (Confluence spaces, Slack channels, file collections).

```sql
CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL CHECK (type IN ('confluence', 'slack', 'file_upload')),
    config JSONB NOT NULL,  -- Plugin-specific configuration (encrypted credentials)
    is_active BOOLEAN DEFAULT true,
    sync_frequency VARCHAR(100),  -- Cron expression
    last_sync_at TIMESTAMP WITH TIME ZONE,
    next_sync_at TIMESTAMP WITH TIME ZONE,
    last_sync_status VARCHAR(50),  -- success, failed, running
    document_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sources_type ON sources(type);
CREATE INDEX idx_sources_is_active ON sources(is_active);
CREATE INDEX idx_sources_next_sync ON sources(next_sync_at) WHERE is_active = true;
CREATE INDEX idx_sources_created_by ON sources(created_by);
```

#### 3. documents
Individual documents from sources.

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id VARCHAR(500) NOT NULL,  -- ID in external system
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64),  -- SHA-256 for change detection
    url TEXT,
    metadata JSONB,  -- Source-specific metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_id, external_id)
);

CREATE INDEX idx_documents_source_id ON documents(source_id);
CREATE INDEX idx_documents_content_hash ON documents(content_hash);
CREATE INDEX idx_documents_updated_at ON documents(updated_at DESC);
CREATE INDEX idx_documents_metadata ON documents USING gin(metadata);

-- Full-text search index
CREATE INDEX idx_documents_content_fts ON documents USING gin(to_tsvector('english', content));
CREATE INDEX idx_documents_title_fts ON documents USING gin(to_tsvector('english', title));

-- Partitioning for large tables (optional, if documents > 10M)
-- CREATE TABLE documents_partition_2024 PARTITION OF documents
--     FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

#### 4. document_chunks
Chunked document content with embeddings (no overlap).

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI text-embedding-3-small
    position INTEGER NOT NULL,  -- Sequential position for sliding window retrieval
    char_start INTEGER NOT NULL,  -- Character offset in original document
    char_end INTEGER NOT NULL,    -- Character offset end
    char_count INTEGER NOT NULL,  -- Length of this chunk in characters
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure no duplicate positions per document
    UNIQUE(document_id, position)
);

CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_position ON document_chunks(document_id, position);

-- Index for efficient sliding window queries
CREATE INDEX idx_chunks_doc_position_range ON document_chunks(document_id, position) 
    WHERE position IS NOT NULL;

-- HNSW index for fast vector similarity search
-- m: number of connections (16 is good default)
-- ef_construction: quality of index (64 is good default)
CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Alternative: IVFFlat index (faster build, slower search)
-- CREATE INDEX idx_chunks_embedding_ivf ON document_chunks 
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);

COMMENT ON COLUMN document_chunks.position IS 'Sequential chunk position (0-indexed) for sliding window retrieval';
COMMENT ON COLUMN document_chunks.char_start IS 'Character offset where chunk starts in original document';
COMMENT ON COLUMN document_chunks.char_end IS 'Character offset where chunk ends in original document';
```
```

#### 5. api_tokens
API tokens for accessing the query API.

```sql
CREATE TABLE api_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL CHECK (type IN ('query', 'admin', 'service')),
    token_hash TEXT NOT NULL UNIQUE,  -- Argon2 hash
    token_preview VARCHAR(16),  -- First 8 chars for display
    scopes JSONB NOT NULL,  -- {source_ids: [...], operations: [...]}
    rate_limit JSONB,  -- {per_minute: 100, per_day: 10000}
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count BIGINT DEFAULT 0,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tokens_token_hash ON api_tokens(token_hash);
CREATE INDEX idx_tokens_type ON api_tokens(type);
CREATE INDEX idx_tokens_is_active ON api_tokens(is_active);
CREATE INDEX idx_tokens_expires_at ON api_tokens(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_tokens_scopes ON api_tokens USING gin(scopes);
```

#### 6. token_scopes
Junction table for token access to specific sources (normalized).

```sql
CREATE TABLE token_scopes (
    token_id UUID NOT NULL REFERENCES api_tokens(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (token_id, source_id)
);

CREATE INDEX idx_token_scopes_source_id ON token_scopes(source_id);
```

#### 7. ingestion_jobs
Track ingestion job history and status.

```sql
CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY,  -- Celery task ID
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL CHECK (type IN ('full_sync', 'incremental')),
    status VARCHAR(50) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    progress JSONB,  -- {processed: 0, total: null, current_step: "..."}
    result JSONB,  -- {documents_added: 10, documents_updated: 5, documents_deleted: 2}
    error TEXT,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_source_id ON ingestion_jobs(source_id);
CREATE INDEX idx_jobs_status ON ingestion_jobs(status);
CREATE INDEX idx_jobs_created_at ON ingestion_jobs(created_at DESC);
CREATE INDEX idx_jobs_type ON ingestion_jobs(type);
```

#### 8. audit_logs
Comprehensive audit trail for all operations.

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES admin_users(id),
    user_email VARCHAR(255),
    action VARCHAR(100) NOT NULL,  -- create, update, delete, read
    resource_type VARCHAR(100) NOT NULL,  -- source, token, user, job
    resource_id UUID,
    resource_name VARCHAR(255),
    changes JSONB,  -- Before/after values for updates
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(100),
    status VARCHAR(50) NOT NULL CHECK (status IN ('success', 'failure')),
    error TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_status ON audit_logs(status);

-- Partitioning for audit logs (recommended for high-volume systems)
-- Partition by month
CREATE TABLE audit_logs_2024_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

#### 9. system_settings
System-wide configuration.

```sql
CREATE TABLE system_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_by UUID REFERENCES admin_users(id),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default settings
INSERT INTO system_settings (key, value, description) VALUES
('embedding', '{"model": "text-embedding-3-small", "dimensions": 1536}', 'Embedding model configuration'),
('chunking', '{"default_chunk_size_chars": 1000, "default_respect_boundaries": true, "default_min_chunk_size_chars": 200, "chunk_size_range": [500, 4000]}', 'Document chunking parameters (no overlap)'),
('search', '{"default_top_k": 10, "max_top_k": 100, "min_similarity_score": 0.7, "default_sliding_window": 0, "max_sliding_window": 3}', 'Search configuration with sliding window support'),
('rate_limiting', '{"default_per_minute": 100, "default_per_day": 10000}', 'Default rate limits'),
('retention', '{"audit_log_days": 90, "job_log_days": 30}', 'Data retention policies');
```

### Analytics & Reporting Tables

#### 10. query_logs
Log all queries for analytics (optional, high volume).

```sql
CREATE TABLE query_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_id UUID REFERENCES api_tokens(id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    query_embedding_hash VARCHAR(64),  -- Hash for deduplication
    results_count INTEGER,
    latency_ms INTEGER,
    cached BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_query_logs_token_id ON query_logs(token_id);
CREATE INDEX idx_query_logs_created_at ON query_logs(created_at DESC);
CREATE INDEX idx_query_logs_cached ON query_logs(cached);

-- Partition by date for efficient queries and cleanup
CREATE TABLE query_logs_2024_01 PARTITION OF query_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

#### 11. Materialized Views for Analytics

```sql
-- Source statistics
CREATE MATERIALIZED VIEW source_stats AS
SELECT 
    s.id,
    s.name,
    s.type,
    COUNT(DISTINCT d.id) as document_count,
    COUNT(dc.id) as chunk_count,
    SUM(LENGTH(d.content)) as total_content_size,
    MAX(d.updated_at) as last_document_update,
    AVG(LENGTH(d.content)) as avg_document_size
FROM sources s
LEFT JOIN documents d ON s.id = d.source_id
LEFT JOIN document_chunks dc ON d.id = dc.document_id
GROUP BY s.id, s.name, s.type;

CREATE UNIQUE INDEX idx_source_stats_id ON source_stats(id);

-- Refresh materialized view (schedule via cron or app)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY source_stats;

-- Token usage statistics
CREATE MATERIALIZED VIEW token_usage_stats AS
SELECT 
    t.id,
    t.name,
    t.type,
    COUNT(ql.id) as query_count,
    AVG(ql.latency_ms) as avg_latency_ms,
    SUM(CASE WHEN ql.cached THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(ql.id), 0) as cache_hit_rate,
    MAX(ql.created_at) as last_query_at
FROM api_tokens t
LEFT JOIN query_logs ql ON t.id = ql.token_id
WHERE ql.created_at > NOW() - INTERVAL '30 days'
GROUP BY t.id, t.name, t.type;

CREATE UNIQUE INDEX idx_token_usage_stats_id ON token_usage_stats(id);
```

## Database Functions

### Auto-update timestamp trigger
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to relevant tables
CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_users_updated_at BEFORE UPDATE ON admin_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_tokens_updated_at BEFORE UPDATE ON api_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### Update document counts on source
```sql
CREATE OR REPLACE FUNCTION update_source_counts()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE sources 
        SET document_count = document_count + 1
        WHERE id = NEW.source_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE sources 
        SET document_count = GREATEST(document_count - 1, 0)
        WHERE id = OLD.source_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_source_document_count 
    AFTER INSERT OR DELETE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_source_counts();
```

### Efficient vector search function with sliding window
```sql
CREATE OR REPLACE FUNCTION search_similar_chunks(
    query_embedding vector(1536),
    allowed_source_ids UUID[],
    limit_count INTEGER DEFAULT 10,
    min_score FLOAT DEFAULT 0.0,
    sliding_window INTEGER DEFAULT 0  -- Number of adjacent chunks to include
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    similarity FLOAT,
    content TEXT,
    extended_content TEXT,  -- Content with sliding window
    document_title TEXT,
    document_url TEXT,
    source_type VARCHAR,
    chunk_position INTEGER,
    included_positions INTEGER[]  -- Positions included in extended_content
) AS $$
BEGIN
    IF sliding_window = 0 THEN
        -- Simple case: no sliding window
        RETURN QUERY
        SELECT 
            dc.id as chunk_id,
            dc.document_id,
            1 - (dc.embedding <=> query_embedding) as similarity,
            dc.content,
            dc.content as extended_content,
            d.title as document_title,
            d.url as document_url,
            s.type as source_type,
            dc.position as chunk_position,
            ARRAY[dc.position] as included_positions
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        JOIN sources s ON d.source_id = s.id
        WHERE 
            d.source_id = ANY(allowed_source_ids)
            AND s.is_active = true
            AND 1 - (dc.embedding <=> query_embedding) >= min_score
        ORDER BY dc.embedding <=> query_embedding
        LIMIT limit_count;
    ELSE
        -- With sliding window: get adjacent chunks
        RETURN QUERY
        WITH matched_chunks AS (
            SELECT 
                dc.id as chunk_id,
                dc.document_id,
                1 - (dc.embedding <=> query_embedding) as similarity,
                dc.content,
                d.title as document_title,
                d.url as document_url,
                s.type as source_type,
                dc.position as chunk_position
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            JOIN sources s ON d.source_id = s.id
            WHERE 
                d.source_id = ANY(allowed_source_ids)
                AND s.is_active = true
                AND 1 - (dc.embedding <=> query_embedding) >= min_score
            ORDER BY dc.embedding <=> query_embedding
            LIMIT limit_count
        ),
        adjacent_chunks AS (
            SELECT 
                mc.chunk_id,
                mc.document_id,
                mc.similarity,
                mc.content,
                mc.document_title,
                mc.document_url,
                mc.source_type,
                mc.chunk_position,
                dc2.position as adj_position,
                dc2.content as adj_content
            FROM matched_chunks mc
            JOIN document_chunks dc2 ON mc.document_id = dc2.document_id
            WHERE dc2.position BETWEEN (mc.chunk_position - sliding_window) 
                                   AND (mc.chunk_position + sliding_window)
            ORDER BY mc.chunk_id, dc2.position
        )
        SELECT 
            ac.chunk_id,
            ac.document_id,
            ac.similarity,
            ac.content,
            string_agg(ac.adj_content, ' ' ORDER BY ac.adj_position) as extended_content,
            ac.document_title,
            ac.document_url,
            ac.source_type,
            ac.chunk_position,
            array_agg(ac.adj_position ORDER BY ac.adj_position) as included_positions
        FROM adjacent_chunks ac
        GROUP BY 
            ac.chunk_id, ac.document_id, ac.similarity, ac.content,
            ac.document_title, ac.document_url, ac.source_type, ac.chunk_position
        ORDER BY ac.similarity DESC;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Usage examples:
-- Without sliding window:
-- SELECT * FROM search_similar_chunks(
--     '[0.1, 0.2, ...]'::vector(1536),
--     ARRAY['uuid1', 'uuid2']::UUID[],
--     10,
--     0.7,
--     0
-- );

-- With sliding window of 1 (include 1 chunk before and after):
-- SELECT * FROM search_similar_chunks(
--     '[0.1, 0.2, ...]'::vector(1536),
--     ARRAY['uuid1', 'uuid2']::UUID[],
--     10,
--     0.7,
--     1
-- );
```
```

## Indexes Strategy

### Composite Indexes for Common Queries

```sql
-- Sources: Active sources due for sync
CREATE INDEX idx_sources_active_sync ON sources(is_active, next_sync_at) 
    WHERE is_active = true;

-- Documents: Source + updated time (for incremental sync)
CREATE INDEX idx_documents_source_updated ON documents(source_id, updated_at DESC);

-- Chunks: Document + position (for ordered retrieval)
CREATE INDEX idx_chunks_doc_position ON document_chunks(document_id, position);

-- Jobs: Source + status + created_at (for job monitoring)
CREATE INDEX idx_jobs_source_status_created ON ingestion_jobs(source_id, status, created_at DESC);

-- Audit: User + created_at (for user activity)
CREATE INDEX idx_audit_user_created ON audit_logs(user_id, created_at DESC);
```

### Partial Indexes for Efficiency

```sql
-- Only index active sources
CREATE INDEX idx_sources_active_only ON sources(id) WHERE is_active = true;

-- Only index non-expired tokens
CREATE INDEX idx_tokens_active_only ON api_tokens(id) 
    WHERE is_active = true AND (expires_at IS NULL OR expires_at > NOW());

-- Only index running jobs
CREATE INDEX idx_jobs_running ON ingestion_jobs(source_id, created_at) 
    WHERE status = 'running';
```

## Performance Tuning

### PostgreSQL Configuration (postgresql.conf)

```ini
# Memory
shared_buffers = 4GB                    # 25% of RAM
effective_cache_size = 12GB             # 75% of RAM
work_mem = 64MB                         # Per query operation
maintenance_work_mem = 1GB              # For VACUUM, index creation

# Query Planning
random_page_cost = 1.1                  # SSD optimization
effective_io_concurrency = 200          # SSD optimization

# Connection Pooling
max_connections = 200

# Vector Search
hnsw.ef_search = 40                     # Balance speed/accuracy

# Logging
log_min_duration_statement = 1000       # Log slow queries (>1s)
log_line_prefix = '%t [%p] %u@%d '
```

### Query Optimization Tips

1. **Use EXPLAIN ANALYZE** for slow queries
```sql
EXPLAIN ANALYZE
SELECT * FROM search_similar_chunks(
    '[...]'::vector(1536),
    ARRAY['uuid1']::UUID[],
    10,
    0.7
);
```

2. **Maintain index health**
```sql
-- Rebuild indexes periodically
REINDEX INDEX CONCURRENTLY idx_chunks_embedding_hnsw;

-- Update statistics
ANALYZE document_chunks;
```

3. **Monitor table bloat**
```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Backup & Recovery

### Backup Strategy
```bash
# Full backup (daily)
pg_dump -Fc rag_db > backup_$(date +%Y%m%d).dump

# WAL archiving for point-in-time recovery
archive_mode = on
archive_command = 'cp %p /backup/wal_archive/%f'
```

### Restore
```bash
# Restore from backup
pg_restore -d rag_db backup_20240101.dump
```

## Migration Management

Use Alembic for schema migrations:

```python
# alembic/versions/001_initial_schema.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'admin_users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        # ... other columns
    )

def downgrade():
    op.drop_table('admin_users')
```

## Monitoring Queries

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Long-running queries
SELECT 
    pid,
    now() - query_start as duration,
    state,
    query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

-- Cache hit rate (should be >99%)
SELECT 
    sum(heap_blks_read) as heap_read,
    sum(heap_blks_hit) as heap_hit,
    sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as cache_hit_ratio
FROM pg_statio_user_tables;

-- Index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

## Data Retention

### Automated Cleanup Jobs

```sql
-- Delete old audit logs (run daily)
DELETE FROM audit_logs 
WHERE created_at < NOW() - INTERVAL '90 days';

-- Delete old job logs (run daily)
DELETE FROM ingestion_jobs 
WHERE created_at < NOW() - INTERVAL '30 days'
AND status IN ('completed', 'failed', 'cancelled');

-- Delete old query logs (run daily)
DELETE FROM query_logs 
WHERE created_at < NOW() - INTERVAL '30 days';

-- Vacuum after large deletes
VACUUM ANALYZE audit_logs;
VACUUM ANALYZE ingestion_jobs;
VACUUM ANALYZE query_logs;
```

## Testing

### Sample Data
```sql
-- Insert test admin user
INSERT INTO admin_users (email, password_hash, full_name, role)
VALUES ('admin@test.com', '$argon2...', 'Test Admin', 'admin');

-- Insert test source
INSERT INTO sources (name, type, config, is_active)
VALUES ('Test Confluence', 'confluence', '{"base_url": "https://test.atlassian.net"}', true);

-- Insert test document
INSERT INTO documents (source_id, external_id, title, content)
VALUES (
    (SELECT id FROM sources WHERE name = 'Test Confluence'),
    'test-page-1',
    'Test Page',
    'This is test content'
);
```

## Security

### Row-Level Security (Optional)
```sql
-- Enable RLS on sensitive tables
ALTER TABLE api_tokens ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own tokens
CREATE POLICY token_isolation ON api_tokens
    FOR SELECT
    USING (created_by = current_setting('app.user_id')::UUID);
```

### Audit Trigger for Sensitive Tables
```sql
CREATE OR REPLACE FUNCTION audit_trigger()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_logs (
        action,
        resource_type,
        resource_id,
        changes,
        created_at
    ) VALUES (
        TG_OP,
        TG_TABLE_NAME,
        NEW.id,
        jsonb_build_object('old', to_jsonb(OLD), 'new', to_jsonb(NEW)),
        NOW()
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_api_tokens 
    AFTER UPDATE OR DELETE ON api_tokens
    FOR EACH ROW EXECUTE FUNCTION audit_trigger();
```
