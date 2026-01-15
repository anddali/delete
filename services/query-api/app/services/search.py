"""
Search service with sliding window retrieval.

CRITICAL: This is the core search implementation that uses:
- pgvector HNSW index for fast similarity search
- Sliding window (0-3) for adjacent chunk retrieval at query time
- NO overlap during indexing, context assembled at query time
"""

from typing import List, Optional
from uuid import UUID

import structlog
from openai import AsyncOpenAI
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from shared.database.models import Document, DocumentChunk, Source
from shared.database.connection import session_manager

logger = structlog.get_logger()


class SearchService:
    """Semantic search service with sliding window context retrieval."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def search(
        self,
        query: str,
        sliding_window: int = 1,
        limit: int = 10,
        source_ids: Optional[List[UUID]] = None,
        source_types: Optional[List[str]] = None,
        min_similarity: float = 0.5,
        include_metadata: bool = True,
    ) -> List[dict]:
        """
        Perform semantic search with sliding window context.
        
        Args:
            query: Search query text
            sliding_window: Number of adjacent chunks to include (0-3)
            limit: Maximum results
            source_ids: Filter by source IDs
            source_types: Filter by source types
            min_similarity: Minimum similarity threshold
            include_metadata: Include document/chunk metadata
        
        Returns:
            List of search results with extended context
        """
        # Generate query embedding
        embedding = await self._generate_embedding(query)
        
        if not embedding:
            logger.error("Failed to generate query embedding")
            return []
        
        # Use the database function for sliding window search
        results = await self._search_with_sliding_window(
            embedding=embedding,
            sliding_window=sliding_window,
            limit=limit,
            source_ids=source_ids,
            source_types=source_types,
            min_similarity=min_similarity,
        )
        
        # Format results with extended content
        formatted = await self._format_results(results, include_metadata)
        
        return formatted
    
    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for query text."""
        try:
            response = await self._openai.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=text,
            )
            return response.data[0].embedding
        
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            return None
    
    async def _search_with_sliding_window(
        self,
        embedding: List[float],
        sliding_window: int,
        limit: int,
        source_ids: Optional[List[UUID]],
        source_types: Optional[List[str]],
        min_similarity: float,
    ) -> List[dict]:
        """
        Search using pgvector and retrieve adjacent chunks.
        
        Uses the search_similar_chunks database function for efficient
        sliding window retrieval.
        """
        # Build embedding string for pgvector
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        
        # Build source filter
        source_filter = ""
        
        if source_ids:
            # Format UUIDs as PostgreSQL array literal
            uuid_list = ",".join(f"'{str(s)}'" for s in source_ids)
            source_filter += f" AND d.source_id IN ({uuid_list})"
        
        if source_types:
            type_list = ",".join(f"'{t}'" for t in source_types)
            source_filter += f" AND s.type IN ({type_list})"
        
        # Main similarity search query
        # This finds the best matching chunks
        # Building complete SQL with embedded embedding to avoid parameter binding issues
        sql_str = f"""
            SELECT 
                c.id AS chunk_id,
                c.document_id,
                c.content,
                c.position,
                c.char_start,
                c.char_end,
                c.char_count,
                c.metadata AS chunk_metadata,
                d.id AS doc_id,
                d.title AS doc_title,
                d.url AS doc_url,
                d.metadata AS doc_metadata,
                s.id AS source_id,
                s.name AS source_name,
                s.type AS source_type,
                (1 - (c.embedding <=> '{embedding_str}'::vector)) AS similarity
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            JOIN sources s ON d.source_id = s.id
            WHERE s.is_active = true
                AND (1 - (c.embedding <=> '{embedding_str}'::vector)) >= {min_similarity}
                {source_filter}
            ORDER BY c.embedding <=> '{embedding_str}'::vector
            LIMIT {limit}
        """
        query = text(sql_str)
        
        try:
            # Use session_manager directly for a fresh connection
            async with session_manager.session() as session:
                result = await session.execute(query)
                rows = result.mappings().all()
        except Exception as e:
            logger.error("Search query failed", error=str(e))
            rows = []
        
        # For each match, get adjacent chunks for sliding window
        results_with_context = []
        
        for row in rows:
            match_chunk = dict(row)
            
            # Get adjacent chunks if sliding_window > 0
            chunks = await self._get_adjacent_chunks(
                document_id=row["document_id"],
                match_position=row["position"],
                window_size=sliding_window,
            )
            
            # Add the matching chunk info
            match_chunk["chunks"] = chunks
            results_with_context.append(match_chunk)
        
        return results_with_context
    
    async def _get_adjacent_chunks(
        self,
        document_id: UUID,
        match_position: int,
        window_size: int,
    ) -> List[dict]:
        """
        Get adjacent chunks for sliding window context.
        
        Args:
            document_id: Document containing the matched chunk
            match_position: Position of the matched chunk
            window_size: Number of chunks before and after to include
        
        Returns:
            List of chunks ordered by position
        """
        if window_size == 0:
            # Just return the matching chunk
            query = text("""
                SELECT id, content, position, char_start, char_end, char_count
                FROM document_chunks
                WHERE document_id = :doc_id AND position = :position
            """)
            async with session_manager.session() as session:
                result = await session.execute(query, {
                    "doc_id": str(document_id),
                    "position": match_position,
                })
                rows = result.mappings().all()
            
            return [
                {
                    "chunk_id": row["id"],
                    "content": row["content"],
                    "position": row["position"],
                    "char_start": row["char_start"],
                    "char_end": row["char_end"],
                    "similarity": 1.0,  # It's the match
                    "is_match": True,
                }
                for row in rows
            ]
        
        # Get chunks in range [position - window, position + window]
        min_pos = max(0, match_position - window_size)
        max_pos = match_position + window_size
        
        query = text("""
            SELECT id, content, position, char_start, char_end, char_count
            FROM document_chunks
            WHERE document_id = :doc_id
                AND position >= :min_pos
                AND position <= :max_pos
            ORDER BY position
        """)
        
        async with session_manager.session() as session:
            result = await session.execute(query, {
                "doc_id": str(document_id),
                "min_pos": min_pos,
                "max_pos": max_pos,
            })
            rows = result.mappings().all()
        
        return [
            {
                "chunk_id": row["id"],
                "content": row["content"],
                "position": row["position"],
                "char_start": row["char_start"],
                "char_end": row["char_end"],
                "similarity": 1.0 if row["position"] == match_position else 0.0,
                "is_match": row["position"] == match_position,
            }
            for row in rows
        ]
    
    async def _format_results(
        self,
        results: List[dict],
        include_metadata: bool,
    ) -> List[dict]:
        """Format search results for API response."""
        formatted = []
        
        for result in results:
            chunks = result.get("chunks", [])
            
            # Build extended content from all chunks
            extended_content = "\n\n".join(
                chunk["content"] for chunk in sorted(chunks, key=lambda c: c["position"])
            )
            
            formatted_result = {
                "document_id": result["document_id"],
                "document_title": result["doc_title"],
                "document_url": result["doc_url"],
                "source_id": result["source_id"],
                "source_name": result["source_name"],
                "source_type": result["source_type"],
                "similarity": float(result["similarity"]),
                "chunks": chunks,
                "extended_content": extended_content,
            }
            
            if include_metadata:
                formatted_result["metadata"] = {
                    "document": result.get("doc_metadata"),
                    "chunk": result.get("chunk_metadata"),
                }
            
            formatted.append(formatted_result)
        
        return formatted
    
    async def get_extended_content(
        self,
        chunk_id: UUID,
        window_size: int = 1,
    ) -> Optional[str]:
        """
        Get extended content for a specific chunk.
        
        Useful for expanding context after initial search.
        """
        # Get the chunk
        result = await self.db.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk_id)
        )
        chunk = result.scalar_one_or_none()
        
        if not chunk:
            return None
        
        # Get adjacent chunks
        chunks = await self._get_adjacent_chunks(
            document_id=chunk.document_id,
            match_position=chunk.position,
            window_size=window_size,
        )
        
        # Build extended content
        return "\n\n".join(
            c["content"] for c in sorted(chunks, key=lambda c: c["position"])
        )
