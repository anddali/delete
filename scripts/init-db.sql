-- Database initialization script for RAG Knowledge Indexing System
-- This script runs when the PostgreSQL container is first created

-- Create extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE ragdb TO raguser;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS rag;

-- Set default search path
ALTER DATABASE ragdb SET search_path TO public, rag;

-- Optimize for vector operations
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';
ALTER SYSTEM SET work_mem = '16MB';

-- Note: The actual tables are created by Alembic migrations
-- Run: alembic upgrade head
