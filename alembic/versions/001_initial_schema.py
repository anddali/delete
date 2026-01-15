"""Initial schema with pgvector

Revision ID: 001_initial_schema
Revises: 
Create Date: 2024-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gin"')
    
    # Create admin_users table
    op.create_table(
        'admin_users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'operator', 'viewer')", name='admin_users_role_check'),
    )
    op.create_index('idx_admin_users_email', 'admin_users', ['email'])
    op.create_index('idx_admin_users_role', 'admin_users', ['role'])
    op.create_index('idx_admin_users_is_active', 'admin_users', ['is_active'])
    
    # Create sources table
    op.create_table(
        'sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('sync_frequency', sa.String(100), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_status', sa.String(50), nullable=True),
        sa.Column('document_count', sa.Integer(), default=0, nullable=False),
        sa.Column('chunk_count', sa.Integer(), default=0, nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint("type IN ('confluence', 'slack', 'file_upload')", name='sources_type_check'),
    )
    op.create_index('idx_sources_type', 'sources', ['type'])
    op.create_index('idx_sources_is_active', 'sources', ['is_active'])
    op.create_index('idx_sources_created_by', 'sources', ['created_by'])
    
    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_id', sa.String(500), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('indexed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('source_id', 'external_id', name='uq_documents_source_external'),
    )
    op.create_index('idx_documents_source_id', 'documents', ['source_id'])
    op.create_index('idx_documents_content_hash', 'documents', ['content_hash'])
    op.create_index('idx_documents_updated_at', 'documents', ['updated_at'], postgresql_ops={'updated_at': 'DESC'})
    
    # Create document_chunks table with pgvector
    op.execute('''
        CREATE TABLE document_chunks (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            embedding vector(1536),
            position INTEGER NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            char_count INTEGER NOT NULL,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            UNIQUE(document_id, position)
        )
    ''')
    
    # Add comments
    op.execute("COMMENT ON COLUMN document_chunks.position IS 'Sequential chunk position (0-indexed) for sliding window retrieval'")
    op.execute("COMMENT ON COLUMN document_chunks.char_start IS 'Character offset where chunk starts in original document'")
    op.execute("COMMENT ON COLUMN document_chunks.char_end IS 'Character offset where chunk ends in original document'")
    
    # Create indexes for document_chunks
    op.create_index('idx_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index('idx_chunks_position', 'document_chunks', ['document_id', 'position'])
    
    # Create HNSW index for vector search
    op.execute('''
        CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks 
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    ''')
    
    # Create api_tokens table
    op.create_table(
        'api_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('token_hash', sa.Text(), unique=True, nullable=False),
        sa.Column('token_preview', sa.String(16), nullable=True),
        sa.Column('scopes', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('rate_limit', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('usage_count', sa.BigInteger(), default=0, nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint("type IN ('query', 'admin', 'service')", name='api_tokens_type_check'),
    )
    op.create_index('idx_tokens_token_hash', 'api_tokens', ['token_hash'])
    op.create_index('idx_tokens_type', 'api_tokens', ['type'])
    op.create_index('idx_tokens_is_active', 'api_tokens', ['is_active'])
    
    # Create token_scopes junction table
    op.create_table(
        'token_scopes',
        sa.Column('token_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('api_tokens.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sources.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('idx_token_scopes_source_id', 'token_scopes', ['source_id'])
    
    # Create ingestion_jobs table
    op.create_table(
        'ingestion_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('progress', postgresql.JSONB(), nullable=True, server_default='{}'),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint("type IN ('full_sync', 'incremental')", name='ingestion_jobs_type_check'),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled')", name='ingestion_jobs_status_check'),
    )
    op.create_index('idx_jobs_source_id', 'ingestion_jobs', ['source_id'])
    op.create_index('idx_jobs_status', 'ingestion_jobs', ['status'])
    op.create_index('idx_jobs_type', 'ingestion_jobs', ['type'])
    op.create_index('idx_jobs_created_at', 'ingestion_jobs', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resource_name', sa.String(255), nullable=True),
        sa.Column('changes', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='success'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint("status IN ('success', 'failure')", name='audit_logs_status_check'),
    )
    op.create_index('idx_audit_user_id', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_action', 'audit_logs', ['action'])
    op.create_index('idx_audit_status', 'audit_logs', ['status'])
    op.create_index('idx_audit_created_at', 'audit_logs', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    
    # Create system_settings table
    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', postgresql.JSONB(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    # Create query_logs table
    op.create_table(
        'query_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('token_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('api_tokens.id', ondelete='SET NULL'), nullable=True),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('query_embedding_hash', sa.String(64), nullable=True),
        sa.Column('results_count', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('cached', sa.Boolean(), default=False, nullable=False),
        sa.Column('sliding_window', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('idx_query_logs_token_id', 'query_logs', ['token_id'])
    op.create_index('idx_query_logs_created_at', 'query_logs', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    op.create_index('idx_query_logs_cached', 'query_logs', ['cached'])
    
    # Create updated_at trigger function
    op.execute('''
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    ''')
    
    # Apply trigger to relevant tables
    for table in ['sources', 'admin_users', 'api_tokens', 'documents']:
        op.execute(f'''
            CREATE TRIGGER update_{table}_updated_at 
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        ''')
    
    # Create vector search function with sliding window
    op.execute('''
        CREATE OR REPLACE FUNCTION search_similar_chunks(
            query_embedding vector(1536),
            allowed_source_ids UUID[],
            limit_count INTEGER DEFAULT 10,
            min_score FLOAT DEFAULT 0.0,
            sliding_window INTEGER DEFAULT 0
        )
        RETURNS TABLE (
            chunk_id UUID,
            document_id UUID,
            similarity FLOAT,
            content TEXT,
            extended_content TEXT,
            document_title TEXT,
            document_url TEXT,
            source_type VARCHAR,
            chunk_position INTEGER,
            included_positions INTEGER[]
        ) AS $$
        BEGIN
            IF sliding_window = 0 THEN
                RETURN QUERY
                SELECT 
                    dc.id as chunk_id,
                    dc.document_id,
                    (1 - (dc.embedding <=> query_embedding))::FLOAT as similarity,
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
                    AND (1 - (dc.embedding <=> query_embedding)) >= min_score
                ORDER BY dc.embedding <=> query_embedding
                LIMIT limit_count;
            ELSE
                RETURN QUERY
                WITH matched_chunks AS (
                    SELECT 
                        dc.id as chunk_id,
                        dc.document_id,
                        (1 - (dc.embedding <=> query_embedding))::FLOAT as similarity,
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
                        AND (1 - (dc.embedding <=> query_embedding)) >= min_score
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
        $$ LANGUAGE plpgsql
    ''')
    
    # Insert default system settings
    op.execute('''
        INSERT INTO system_settings (key, value, description) VALUES
        ('embedding', '{"model": "text-embedding-3-small", "dimensions": 1536}', 'Embedding model configuration'),
        ('chunking', '{"default_chunk_size_chars": 1000, "default_respect_boundaries": true, "default_min_chunk_size_chars": 200, "chunk_size_range": [500, 4000]}', 'Document chunking parameters (no overlap)'),
        ('search', '{"default_top_k": 10, "max_top_k": 100, "min_similarity_score": 0.7, "default_sliding_window": 0, "max_sliding_window": 3}', 'Search configuration with sliding window support'),
        ('rate_limiting', '{"default_per_minute": 100, "default_per_day": 10000}', 'Default rate limits'),
        ('retention', '{"audit_log_days": 90, "job_log_days": 30}', 'Data retention policies')
    ''')


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('query_logs')
    op.drop_table('system_settings')
    op.drop_table('audit_logs')
    op.drop_table('ingestion_jobs')
    op.drop_table('token_scopes')
    op.drop_table('api_tokens')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('sources')
    op.drop_table('admin_users')
    
    # Drop function
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE')
    op.execute('DROP FUNCTION IF EXISTS search_similar_chunks(vector(1536), UUID[], INTEGER, FLOAT, INTEGER) CASCADE')
