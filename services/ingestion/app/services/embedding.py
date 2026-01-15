"""
Embedding generation service using OpenAI API.
"""

import asyncio
import hashlib
import json
from typing import List, Optional

import httpx
import structlog
from openai import AsyncOpenAI

from app.config import settings

logger = structlog.get_logger()


class EmbeddingService:
    """Service for generating embeddings using OpenAI API."""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            organization=settings.OPENAI_ORG_ID,
        )
        self.model = settings.EMBEDDING_MODEL
        self.dimensions = settings.EMBEDDING_DIMENSIONS
        self.batch_size = settings.EMBEDDING_BATCH_SIZE
        self._cache: dict[str, List[float]] = {}
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = await self.generate_embeddings_batch([text])
        return embeddings[0] if embeddings else []
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        OpenAI supports up to 2048 inputs per request, but we use
        smaller batches for better reliability.
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use caching for identical texts
        
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Check cache for each text
        results: List[Optional[List[float]]] = [None] * len(texts)
        texts_to_embed: List[tuple[int, str]] = []
        
        for i, text in enumerate(texts):
            if use_cache:
                text_hash = self._hash_text(text)
                if text_hash in self._cache:
                    results[i] = self._cache[text_hash]
                    continue
            texts_to_embed.append((i, text))
        
        # Generate embeddings for uncached texts
        if texts_to_embed:
            for batch_start in range(0, len(texts_to_embed), self.batch_size):
                batch_items = texts_to_embed[batch_start:batch_start + self.batch_size]
                batch_texts = [text for _, text in batch_items]
                
                embeddings = await self._call_openai_embeddings(batch_texts)
                
                for (original_idx, text), embedding in zip(batch_items, embeddings):
                    results[original_idx] = embedding
                    
                    # Cache the result
                    if use_cache:
                        text_hash = self._hash_text(text)
                        self._cache[text_hash] = embedding
        
        return [r for r in results if r is not None]
    
    async def _call_openai_embeddings(
        self,
        texts: List[str],
        max_retries: int = 3,
    ) -> List[List[float]]:
        """Call OpenAI embeddings API with retry logic."""
        retry_delays = [1, 5, 15]
        
        for attempt in range(max_retries):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                )
                
                # Sort by index to ensure correct order
                embeddings = sorted(response.data, key=lambda x: x.index)
                return [e.embedding for e in embeddings]
                
            except Exception as e:
                logger.warning(
                    "OpenAI embedding request failed",
                    attempt=attempt + 1,
                    error=str(e),
                )
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delays[attempt])
                else:
                    raise
        
        return []
    
    def _hash_text(self, text: str) -> str:
        """Generate hash for text caching."""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()


# Global instance
embedding_service = EmbeddingService()


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Convenience function to generate embeddings."""
    return await embedding_service.generate_embeddings_batch(texts)
