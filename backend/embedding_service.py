"""
Gemini Embedding 2 Service untuk FieldGuide Agent
"""

import os
import logging
from typing import List, Optional
from google import genai
from google.genai import types

logger = logging.getLogger("FieldGuide-Embedding")

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            logger.error("GEMINI_API_KEY not set!")
            return None
        _client = genai.Client(api_key=api_key)
        logger.info("Gemini Embedding client initialized")
    return _client


def _normalize_embedding(raw) -> Optional[List[float]]:
    """
    Normalize any embedding format to flat List[float].
    Handles: object with .values, nested list, direct list, numpy array.
    """
    if raw is None:
        return None
    
    # If it has .values attribute (Pydantic model)
    if hasattr(raw, 'values'):
        raw = raw.values
    
    # Convert to list if needed (numpy, tuple, etc)
    if not isinstance(raw, list):
        raw = list(raw)
    
    if len(raw) == 0:
        return None
    
    # If nested: [[0.1, 0.2, ...]] -> [0.1, 0.2, ...]
    if isinstance(raw[0], (list, tuple)):
        raw = [float(x) for x in raw[0]]
    
    # Ensure all elements are float
    result = [float(x) for x in raw]
    return result


def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> Optional[List[float]]:
    """Embed satu teks menggunakan Gemini Embedding 2."""
    client = _get_client()
    if not client:
        return None
    try:
        result = client.models.embed_content(
            model="gemini-embedding-2-preview",
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=768
            )
        )
        return _normalize_embedding(result.embeddings[0])
    except Exception as e:
        logger.error(f"Embedding failed for text: {e}")
        return None


def embed_texts_batch(texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[Optional[List[float]]]:
    """Batch embed multiple texts."""
    client = _get_client()
    if not client:
        return [None] * len(texts)
    
    results = []
    for i in range(0, len(texts), 100):
        batch = texts[i:i+100]
        try:
            result = client.models.embed_content(
                model="gemini-embedding-2-preview",
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=768
                )
            )
            for emb in result.embeddings:
                normalized = _normalize_embedding(emb)
                results.append(normalized)
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            results.extend([None] * len(batch))
    
    return results
