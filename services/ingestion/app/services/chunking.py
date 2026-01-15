"""
Chunking service for document processing.

This implements the NO OVERLAP chunking strategy where documents are split
into sequential chunks and context is retrieved via sliding window at query time.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class Chunk:
    """Represents a document chunk."""
    
    content: str
    position: int  # Sequential position (0-indexed)
    char_start: int  # Character offset in original document
    char_end: int  # Character offset end
    char_count: int  # Length of this chunk
    metadata: Optional[dict] = None


def chunk_document(
    content: str,
    chunk_size_chars: int = 1000,
    respect_boundaries: bool = True,
    min_chunk_size_chars: int = 200,
    metadata: Optional[dict] = None,
) -> List[Chunk]:
    """
    Split document into sequential chunks WITHOUT overlap.
    
    This is the core chunking algorithm that creates non-overlapping chunks.
    Context is retrieved via sliding window at query time instead of
    storing overlapping content.
    
    Args:
        content: Document text to chunk
        chunk_size_chars: Target size for each chunk in characters
        respect_boundaries: Try to break at natural boundaries (sentences, paragraphs)
        min_chunk_size_chars: Minimum chunk size to keep
        metadata: Optional metadata to attach to each chunk
    
    Returns:
        List of Chunk objects with sequential positions
    
    Benefits:
        - No duplicate content in database (efficient storage)
        - Configurable chunk size per source
        - Adjacent chunks retrieved via sliding window at query time
        - Better semantic coherence per chunk
    """
    if not content or not content.strip():
        return []
    
    # Normalize whitespace
    content = content.strip()
    
    chunks: List[Chunk] = []
    position = 0
    chunk_index = 0
    
    while position < len(content):
        # Calculate target end position
        end_position = min(position + chunk_size_chars, len(content))
        
        # Try to respect natural boundaries if enabled and not at document end
        if respect_boundaries and end_position < len(content):
            end_position = _find_best_break_point(
                content, position, end_position, chunk_size_chars
            )
        
        # Extract chunk text
        chunk_text = content[position:end_position].strip()
        
        # Only keep chunks that meet minimum size
        if len(chunk_text) >= min_chunk_size_chars:
            chunk = Chunk(
                content=chunk_text,
                position=chunk_index,
                char_start=position,
                char_end=end_position,
                char_count=len(chunk_text),
                metadata={
                    **(metadata or {}),
                    "chunk_position": chunk_index,
                    "total_chars": len(content),
                },
            )
            chunks.append(chunk)
            chunk_index += 1
        elif chunk_text and chunks:
            # Append small final chunk to previous chunk
            last_chunk = chunks[-1]
            combined_content = last_chunk.content + " " + chunk_text
            chunks[-1] = Chunk(
                content=combined_content,
                position=last_chunk.position,
                char_start=last_chunk.char_start,
                char_end=end_position,
                char_count=len(combined_content),
                metadata=last_chunk.metadata,
            )
        
        # Move to next position
        position = end_position
    
    logger.debug(
        "Document chunked",
        total_chunks=len(chunks),
        avg_chunk_size=sum(c.char_count for c in chunks) / len(chunks) if chunks else 0,
        original_length=len(content),
    )
    
    return chunks


def _find_best_break_point(
    content: str,
    start_pos: int,
    target_end: int,
    chunk_size: int,
) -> int:
    """
    Find the best break point respecting natural boundaries.
    
    Priority:
    1. Paragraph break (\\n\\n)
    2. Sentence break (. ! ?)
    3. Line break (\\n)
    4. Word break (space)
    5. Original target position
    """
    # Minimum acceptable position (70% of chunk size)
    min_acceptable = start_pos + int(chunk_size * 0.7)
    
    # Look for paragraph break (preferred)
    paragraph_break = content.rfind('\n\n', start_pos, target_end)
    if paragraph_break > min_acceptable:
        return paragraph_break + 2  # Include the newlines
    
    # Look for sentence breaks
    sentence_patterns = ['. ', '.\n', '! ', '!\n', '? ', '?\n']
    best_sentence_break = -1
    
    for pattern in sentence_patterns:
        pos = content.rfind(pattern, start_pos, target_end)
        if pos > best_sentence_break:
            best_sentence_break = pos
    
    if best_sentence_break > min_acceptable:
        return best_sentence_break + 2  # Include punctuation and space
    
    # Look for single line break
    line_break = content.rfind('\n', start_pos, target_end)
    if line_break > min_acceptable:
        return line_break + 1
    
    # Look for word break (space)
    word_break = content.rfind(' ', start_pos, target_end)
    if word_break > min_acceptable:
        return word_break + 1
    
    # Fall back to original target
    return target_end


def estimate_chunk_count(
    content_length: int,
    chunk_size_chars: int = 1000,
) -> int:
    """Estimate the number of chunks for a document."""
    if content_length <= 0:
        return 0
    return max(1, (content_length + chunk_size_chars - 1) // chunk_size_chars)


def get_chunking_config(source_config: dict) -> dict:
    """
    Get chunking configuration from source config with defaults.
    
    Args:
        source_config: Source configuration dictionary
    
    Returns:
        Chunking configuration with defaults applied
    """
    chunking = source_config.get("chunking", {})
    
    return {
        "chunk_size_chars": chunking.get("chunk_size_chars", 1000),
        "respect_boundaries": chunking.get("respect_boundaries", True),
        "min_chunk_size_chars": chunking.get("min_chunk_size_chars", 200),
    }
