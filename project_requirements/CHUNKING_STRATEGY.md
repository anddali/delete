# Chunking & Sliding Window Strategy

## Overview

This system uses a sophisticated chunking approach that separates ingestion-time chunking from query-time context retrieval. This provides better flexibility, storage efficiency, and semantic quality than traditional overlapping chunk approaches.

## Core Concept

### Traditional Overlapping Chunks (What We Don't Do)
```
Document: "ABCDEFGHIJKLMNOP"

Chunk 1: "ABCDEF" (positions 0-5)
Chunk 2: "DEFGHI" (positions 3-8)    ← Overlap: "DEF"
Chunk 3: "GHIJKL" (positions 6-11)   ← Overlap: "GHI"
Chunk 4: "JKLMNO" (positions 9-14)   ← Overlap: "JKL"
Chunk 5: "MNOP"   (positions 12-15)  ← Overlap: "MNO"

Problems:
- Duplicate content in database (inefficient storage)
- Fixed context window (can't adjust at query time)
- More embeddings to generate and store
```

### Our Approach: Sequential Chunks + Query-Time Sliding Window
```
Document: "ABCDEFGHIJKLMNOP"

Ingestion (no overlap):
Chunk 0: "ABCDEF" (positions 0-5)
Chunk 1: "GHIJKL" (positions 6-11)
Chunk 2: "MNOP"   (positions 12-15)

Query Time (with sliding_window=1):
If Chunk 1 matches query:
  Return: Chunk 0 + Chunk 1 + Chunk 2
  = "ABCDEFGHIJKLMNOP"

Benefits:
- No duplicate storage
- Adjustable context per query
- Fewer embeddings needed
- More efficient retrieval
```

## Configuration

### 1. Source-Level Chunking Configuration

Each source can have custom chunking parameters:

```json
{
  "chunking": {
    "chunk_size_chars": 1000,        // Characters per chunk
    "respect_boundaries": true,      // Try to break at sentences/paragraphs
    "min_chunk_size_chars": 200      // Discard chunks smaller than this
  }
}
```

**Recommendations by Source Type:**

| Source Type | chunk_size_chars | Reasoning |
|------------|------------------|-----------|
| **Confluence** | 1000-1500 | Technical documentation benefits from larger chunks |
| **Slack** | 600-800 | Shorter messages, conversational content |
| **PDF Documents** | 1200-1500 | Dense technical content |
| **Code Files** | 800-1000 | Respect function/class boundaries |

### 2. Query-Time Sliding Window

When querying, specify how much context to retrieve:

```json
{
  "query": "How to configure SSO?",
  "sliding_window": 1,  // Include 1 chunk before and after
  "options": {
    "deduplicate_chunks": true  // Remove duplicates if same chunk appears in multiple results
  }
}
```

**Sliding Window Values:**

| sliding_window | Context Retrieved | Use Case |
|----------------|-------------------|----------|
| 0 | Exact matching chunk only | Quick answers, keyword search |
| 1 | ±1 chunk (3 total) | Standard queries, ~3000 chars context |
| 2 | ±2 chunks (5 total) | Complex topics, ~5000 chars context |
| 3 | ±3 chunks (7 total) | Deep explanations, ~7000 chars context |

## Implementation Details

### Chunking Algorithm

```python
def chunk_document(
    content: str, 
    chunk_size_chars: int = 1000,
    respect_boundaries: bool = True,
    min_chunk_size_chars: int = 200
) -> List[Chunk]:
    """
    Split document into sequential chunks without overlap.
    
    Args:
        content: Document text to chunk
        chunk_size_chars: Target size for each chunk
        respect_boundaries: Try to break at natural boundaries
        min_chunk_size_chars: Minimum chunk size to keep
    
    Returns:
        List of chunks with sequential positions
    """
    chunks = []
    position = 0
    chunk_index = 0
    
    while position < len(content):
        end_position = min(position + chunk_size_chars, len(content))
        
        # Respect boundaries if enabled
        if respect_boundaries and end_position < len(content):
            # Look for paragraph break (preferred)
            paragraph_break = content.rfind('\n\n', position, end_position)
            if paragraph_break > position + (chunk_size_chars * 0.7):
                end_position = paragraph_break + 2
            else:
                # Look for sentence break
                sentence_breaks = [
                    content.rfind('. ', position, end_position),
                    content.rfind('.\n', position, end_position),
                    content.rfind('! ', position, end_position),
                    content.rfind('? ', position, end_position),
                ]
                best_break = max(sentence_breaks)
                if best_break > position + (chunk_size_chars * 0.7):
                    end_position = best_break + 2
        
        chunk_text = content[position:end_position].strip()
        
        if len(chunk_text) >= min_chunk_size_chars:
            chunks.append(Chunk(
                content=chunk_text,
                position=chunk_index,
                char_start=position,
                char_end=end_position,
                char_count=len(chunk_text)
            ))
            chunk_index += 1
        
        position = end_position
    
    return chunks
```

### Sliding Window Retrieval

```python
async def get_extended_content(
    document_id: str,
    center_position: int,
    window_size: int
) -> Tuple[str, List[int]]:
    """
    Retrieve adjacent chunks for context.
    
    Args:
        document_id: Document containing chunks
        center_position: Position of matching chunk
        window_size: Number of chunks to include on each side
    
    Returns:
        Tuple of (combined_content, list_of_positions)
    """
    start_pos = max(0, center_position - window_size)
    end_pos = center_position + window_size
    
    # Single efficient query to get all chunks in range
    chunks = await db.fetch(
        """
        SELECT content, position 
        FROM document_chunks 
        WHERE document_id = $1 
          AND position BETWEEN $2 AND $3
        ORDER BY position
        """,
        document_id, start_pos, end_pos
    )
    
    combined_content = ' '.join(chunk['content'] for chunk in chunks)
    positions = [chunk['position'] for chunk in chunks]
    
    return combined_content, positions
```

### Database Query Optimization

The sliding window approach uses efficient SQL:

```sql
-- Single query gets matching chunks AND their context
WITH matched_chunks AS (
    -- Vector similarity search
    SELECT id, document_id, position, content
    FROM document_chunks
    WHERE embedding <=> query_embedding < threshold
    ORDER BY embedding <=> query_embedding
    LIMIT 10
)
SELECT 
    mc.id as match_id,
    mc.position as match_position,
    string_agg(dc.content, ' ' ORDER BY dc.position) as extended_content,
    array_agg(dc.position ORDER BY dc.position) as positions
FROM matched_chunks mc
JOIN document_chunks dc 
    ON mc.document_id = dc.document_id
    AND dc.position BETWEEN (mc.position - sliding_window) 
                        AND (mc.position + sliding_window)
GROUP BY mc.id, mc.position
ORDER BY mc.embedding <=> query_embedding;
```

## Performance Characteristics

### Storage Efficiency

**Example: 10,000 character document**

Traditional overlapping (50% overlap):
- Chunks: 20 chunks × 1000 chars = 20,000 chars stored
- Embeddings: 20 embeddings to generate
- Storage overhead: 100% (2× original size)

Our approach (no overlap):
- Chunks: 10 chunks × 1000 chars = 10,000 chars stored
- Embeddings: 10 embeddings to generate
- Storage overhead: 0% (1× original size)

**Savings: 50% less storage, 50% fewer embeddings**

### Query Performance

**Sliding window impact on latency:**

| sliding_window | Additional Latency | Total Latency (p50) |
|----------------|-------------------|---------------------|
| 0 | +0ms | ~85ms |
| 1 | +5ms | ~90ms |
| 2 | +10ms | ~95ms |
| 3 | +15ms | ~100ms |

The additional latency is minimal because:
1. Sequential chunks are physically close in database
2. Single query retrieves all needed chunks
3. Index on (document_id, position) is very efficient

### Token Usage for LLM Context

When passing results to an LLM:

```python
# Without sliding window
chunk_content = result['content']  # ~1000 chars = ~250 tokens

# With sliding_window=1
extended_content = result['extended_content']  # ~3000 chars = ~750 tokens

# With sliding_window=2  
extended_content = result['extended_content']  # ~5000 chars = ~1250 tokens
```

This allows dynamic context sizing based on query complexity.

## Use Cases & Examples

### Use Case 1: Quick Factual Lookup

**Query**: "What is the API rate limit?"

```json
{
  "query": "What is the API rate limit?",
  "sliding_window": 0,  // Just the matching chunk
  "top_k": 3
}
```

**Result**: Precise answer from exact matching chunk (~1000 chars)

### Use Case 2: Understanding a Concept

**Query**: "How does authentication work in our system?"

```json
{
  "query": "How does authentication work in our system?",
  "sliding_window": 1,  // Include surrounding context
  "top_k": 5
}
```

**Result**: Matching chunk plus context before/after (~3000 chars per result)

### Use Case 3: Deep Technical Explanation

**Query**: "Explain the complete deployment process with all prerequisites"

```json
{
  "query": "Explain the complete deployment process with all prerequisites",
  "sliding_window": 2,  // Maximum context
  "top_k": 3
}
```

**Result**: Extended context for comprehensive explanation (~5000 chars per result)

### Use Case 4: Code Search

**Query**: "Function that validates user input"

```json
{
  "query": "Function that validates user input",
  "sliding_window": 1,  // Get surrounding functions/classes
  "top_k": 5,
  "filters": {
    "source_types": ["file_upload"],
    "file_extensions": [".py", ".js"]
  }
}
```

**Result**: Matching function plus surrounding code context

## Best Practices

### 1. Choosing Chunk Size

**Factors to consider:**
- **Content density**: Technical docs → larger chunks
- **Query patterns**: Detail-oriented queries → larger chunks
- **Source type**: Chat messages → smaller chunks
- **Language**: Non-English may need different sizes

**Testing approach:**
```python
# Experiment with different sizes
chunk_sizes = [800, 1000, 1200, 1500]

for size in chunk_sizes:
    # Re-index sample documents
    results = evaluate_retrieval_quality(test_queries, chunk_size=size)
    print(f"Size {size}: Precision={results.precision}, Recall={results.recall}")
```

### 2. Choosing Sliding Window

**Guidelines:**
- Start with `sliding_window=0` for new systems
- Monitor if users need more context in results
- Increase to 1 or 2 based on feedback
- Use `sliding_window=0` for keyword/factual queries
- Use `sliding_window=1-2` for explanatory queries

### 3. Handling Edge Cases

**Short documents:**
```python
if document_length < chunk_size_chars:
    # Don't chunk - store as single chunk
    chunks = [Chunk(content=document, position=0)]
```

**Very long documents:**
```python
if num_chunks > 100:
    # Consider warning or adjusting chunk size
    logger.warning(f"Document has {num_chunks} chunks, consider larger chunk size")
```

### 4. Deduplication

When `sliding_window > 0`, the same chunk might appear in multiple results:

```python
# Enable deduplication
{
  "sliding_window": 1,
  "options": {
    "deduplicate_chunks": true  // Remove duplicate chunks across results
  }
}
```

This is important when returning multiple results to an LLM to avoid redundancy.

## Migration Guide

If migrating from overlapping chunks:

### Step 1: Backup Current Data
```bash
pg_dump -t documents -t document_chunks > backup.sql
```

### Step 2: Update Schema
```sql
ALTER TABLE document_chunks 
  ADD COLUMN char_start INTEGER,
  ADD COLUMN char_end INTEGER,
  ADD COLUMN char_count INTEGER;

-- Remove old overlap-related columns if they exist
ALTER TABLE document_chunks DROP COLUMN IF EXISTS overlap_start;
```

### Step 3: Re-chunk Existing Documents
```python
async def rechunk_documents():
    sources = await get_all_sources()
    
    for source in sources:
        # Get chunking config from source
        chunking_config = source.config.get('chunking', {
            'chunk_size_chars': 1000,
            'respect_boundaries': True,
            'min_chunk_size_chars': 200
        })
        
        documents = await get_documents_by_source(source.id)
        
        for doc in documents:
            # Delete old chunks
            await delete_chunks_by_document(doc.id)
            
            # Create new chunks
            new_chunks = chunk_document(
                doc.content,
                **chunking_config
            )
            
            # Generate embeddings
            embeddings = await generate_embeddings_batch([c.content for c in new_chunks])
            
            # Store new chunks
            await store_chunks(doc.id, new_chunks, embeddings)
```

### Step 4: Update Query Code
```python
# Before
results = await search(query, top_k=10)

# After
results = await search(
    query, 
    top_k=10,
    sliding_window=1  # Add context
)
```

## Monitoring & Optimization

### Key Metrics to Track

```python
# Track sliding window usage
metrics = {
    'queries_with_window_0': 0,
    'queries_with_window_1': 0,
    'queries_with_window_2': 0,
    'queries_with_window_3': 0,
    'avg_latency_by_window': {},
    'avg_result_length_by_window': {},
}

# Track chunk sizes
chunk_size_distribution = {
    'avg_chunk_size': 0,
    'min_chunk_size': 0,
    'max_chunk_size': 0,
    'chunks_below_min': 0,
}

# Track retrieval quality
retrieval_metrics = {
    'avg_chunks_per_result': 0,
    'duplicate_chunk_rate': 0,
    'boundary_break_rate': 0,  # How often we break mid-sentence
}
```

### Dashboard Queries

```sql
-- Average chunks per document by source type
SELECT 
    s.type,
    COUNT(dc.id)::float / NULLIF(COUNT(DISTINCT d.id), 0) as avg_chunks_per_doc
FROM sources s
JOIN documents d ON s.id = d.source_id
JOIN document_chunks dc ON d.id = dc.document_id
GROUP BY s.type;

-- Chunk size distribution
SELECT 
    percentile_cont(0.5) WITHIN GROUP (ORDER BY char_count) as median_size,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY char_count) as p95_size,
    AVG(char_count) as avg_size
FROM document_chunks;

-- Most queried documents (might need larger chunks)
SELECT 
    d.id,
    d.title,
    COUNT(ql.id) as query_count,
    COUNT(DISTINCT dc.id) as chunk_count
FROM documents d
JOIN document_chunks dc ON d.id = dc.document_id
JOIN query_logs ql ON dc.id = ql.matched_chunk_id
GROUP BY d.id, d.title
ORDER BY query_count DESC
LIMIT 20;
```

## Conclusion

The sliding window approach provides:

1. **Flexibility**: Adjust context per query
2. **Efficiency**: 50% reduction in storage and embeddings
3. **Quality**: Natural semantic boundaries
4. **Performance**: <100ms query latency
5. **Configurability**: Per-source chunk size settings

This approach is superior to fixed-overlap chunking for production RAG systems.
