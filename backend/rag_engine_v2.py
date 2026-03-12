"""
RAG Engine V2 - Menggunakan Gemini Embedding 2 + ChromaDB
Menggantikan rag_engine.py yang pakai sentence-transformers
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

import chromadb
from embedding_service import embed_text, embed_texts_batch

logger = logging.getLogger("FieldGuide-RAG-V2")

# ChromaDB persistent storage
CHROMA_DIR = Path(__file__).resolve().parent / "chroma_db"
_chroma_client = None
_knowledge_collection = None
_chunks_collection = None
_KNOWLEDGE_DB: List[Dict] = []  # Raw data untuk formatting
_LOADED = False


def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        CHROMA_DIR.mkdir(exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        logger.info(f"ChromaDB initialized at {CHROMA_DIR}")
    return _chroma_client


def _get_collections():
    global _knowledge_collection, _chunks_collection
    client = _get_chroma_client()
    
    if _knowledge_collection is None:
        _knowledge_collection = client.get_or_create_collection(
            name="equipment_knowledge_v2",
            metadata={"hnsw:space": "cosine"}
        )
    if _chunks_collection is None:
        _chunks_collection = client.get_or_create_collection(
            name="text_chunks_v2",
            metadata={"hnsw:space": "cosine"}
        )
    return _knowledge_collection, _chunks_collection


def _build_searchable_text(kb: Dict) -> str:
    """Build searchable text from structured knowledge entry."""
    parts = [
        f"Equipment: {kb.get('equipment_type', '')}",
        f"Brand: {kb.get('brand', '')}",
        f"Model: {kb.get('model', '')}",
        f"Components: {', '.join(kb.get('components', []))}",
        f"Symptoms: {', '.join(kb.get('symptoms', []))}",
        f"Safety: {' '.join(kb.get('safety_warnings', [])[:3])}",
        f"Tools: {', '.join(kb.get('tools_required', []))}",
    ]
    
    # Tambah common failures dan diagnostic steps untuk konteks lebih kaya
    failures = kb.get("common_failures", [])
    if failures:
        parts.append(f"Common failures: {'; '.join(failures[:5])}")
    
    diag = kb.get("diagnostic_steps", [])
    if diag:
        parts.append(f"Diagnostics: {'; '.join(diag[:5])}")
    
    return " ".join(parts)


def load_knowledge_base(base_dir: str = None):
    """Load knowledge base dan index ke ChromaDB dengan Gemini Embedding 2."""
    global _KNOWLEDGE_DB, _LOADED
    
    if _LOADED:
        logger.info("Knowledge base already loaded, skipping.")
        return
    
    # --- Cari directory knowledge ---
    if base_dir is None:
        candidates = [
            Path("knowledge"),
            Path("structured_knowledge"),
            Path("../structured_knowledge"),
        ]
        for c in candidates:
            if c.exists():
                base_dir = str(c)
                break
    
    if base_dir is None:
        logger.warning("No knowledge base directory found")
        return
    
    knowledge_dir = Path(base_dir)
    knowledge_collection, chunks_collection = _get_collections()
    
    # --- Cek apakah sudah ter-index di ChromaDB ---
    existing_count = knowledge_collection.count()
    if existing_count > 0:
        logger.info(f"ChromaDB already has {existing_count} knowledge entries. Loading raw data only.")
        # Tetap load raw data untuk formatting
        _load_raw_knowledge(knowledge_dir)
        _LOADED = True
        return
    
    # --- Load dan index knowledge documents ---
    logger.info("First time indexing - embedding all knowledge with Gemini Embedding 2...")
    _load_raw_knowledge(knowledge_dir)
    
    if _KNOWLEDGE_DB:
        _index_knowledge(knowledge_collection)
    
    # --- Load dan index text chunks ---
    chunks = _load_chunks(knowledge_dir)
    if chunks:
        _index_chunks(chunks_collection, chunks)
    
    _LOADED = True
    logger.info(
        f"Knowledge base loaded and indexed: {knowledge_collection.count()} documents, "
        f"{chunks_collection.count()} text chunks"
    )


def _load_raw_knowledge(knowledge_dir: Path):
    """Load raw knowledge data dari files."""
    global _KNOWLEDGE_DB
    
    jsonl_file = knowledge_dir / "knowledge_base.jsonl"
    if jsonl_file.exists():
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        _KNOWLEDGE_DB.append(data)
            logger.info(f"Loaded {len(_KNOWLEDGE_DB)} entries from knowledge_base.jsonl")
        except Exception as e:
            logger.warning(f"Failed to load knowledge_base.jsonl: {e}")
    else:
        for jf in knowledge_dir.glob("*_knowledge.json"):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    _KNOWLEDGE_DB.append(data)
                logger.info(f"Loaded knowledge: {jf.name}")
            except Exception as e:
                logger.warning(f"Failed to load {jf}: {e}")


def _index_knowledge(collection):
    """Embed dan index semua knowledge ke ChromaDB."""
    texts = []
    ids = []
    metadatas = []
    
    for i, kb in enumerate(_KNOWLEDGE_DB):
        searchable = _build_searchable_text(kb)
        texts.append(searchable)
        
        eq_id = f"kb_{kb.get('brand', 'unknown')}_{kb.get('model', 'unknown')}_{i}".replace(" ", "_").lower()
        ids.append(eq_id)
        
        metadatas.append({
            "equipment_type": kb.get("equipment_type", ""),
            "brand": kb.get("brand", ""),
            "model": kb.get("model", ""),
            "index": i,  # Index ke _KNOWLEDGE_DB untuk retrieve full data
        })
    
    # Batch embed semua sekaligus
    embeddings = embed_texts_batch(texts, task_type="RETRIEVAL_DOCUMENT")
    
    # Filter out failed embeddings
    valid_ids = []
    valid_embeddings = []
    valid_metadatas = []
    valid_documents = []
    
    for j, emb in enumerate(embeddings):
        if emb is not None:
            valid_ids.append(ids[j])
            valid_embeddings.append(emb)
            valid_metadatas.append(metadatas[j])
            valid_documents.append(texts[j])
    
    if valid_ids:
        # VALIDATE: pastikan setiap embedding adalah flat list of float
        clean_embeddings = []
        for emb in valid_embeddings:
            if isinstance(emb[0], (list, tuple)):
                clean_embeddings.append([float(x) for x in emb[0]])
            else:
                clean_embeddings.append([float(x) for x in emb])
        
        collection.add(
            ids=valid_ids,
            embeddings=clean_embeddings,
            metadatas=valid_metadatas,
            documents=valid_documents,
        )
        logger.info(f"Indexed {len(valid_ids)} knowledge entries to ChromaDB")


def _load_chunks(knowledge_dir: Path) -> List[Dict]:
    """Load text chunks dari JSONL files."""
    chunks = []
    for cf in knowledge_dir.glob("*_chunks.jsonl"):
        try:
            with open(cf, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        chunk = json.loads(line)
                        chunks.append(chunk)
        except Exception as e:
            logger.warning(f"Failed to load chunks {cf}: {e}")
    logger.info(f"Loaded {len(chunks)} text chunks")
    return chunks


def _index_chunks(collection, chunks: List[Dict]):
    """Embed dan index text chunks ke ChromaDB."""
    texts = []
    ids = []
    metadatas = []
    
    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        if not text:
            continue
        # Potong teks terlalu panjang (Gemini Embedding 2 max 8192 tokens)
        texts.append(text[:3000])
        ids.append(f"chunk_{i}")
        metadatas.append({
            "source_file": chunk.get("source_file", ""),
            "chunk_index": i,
        })
    
    if not texts:
        return
    
    # Batch embed
    embeddings = embed_texts_batch(texts, task_type="RETRIEVAL_DOCUMENT")
    
    valid_ids = []
    valid_embeddings = []
    valid_metadatas = []
    valid_documents = []
    
    for j, emb in enumerate(embeddings):
        if emb is not None:
            valid_ids.append(ids[j])
            valid_embeddings.append(emb)
            valid_metadatas.append(metadatas[j])
            valid_documents.append(texts[j])
    
    if valid_ids:
        clean_embeddings = []
        for emb in valid_embeddings:
            if isinstance(emb[0], (list, tuple)):
                clean_embeddings.append([float(x) for x in emb[0]])
            else:
                clean_embeddings.append([float(x) for x in emb])
        
        collection.add(
            ids=valid_ids,
            embeddings=clean_embeddings,
            metadatas=valid_metadatas,
            documents=valid_documents,
        )
        logger.info(f"Indexed {len(valid_ids)} text chunks to ChromaDB")


def search_knowledge(
    query: str,
    top_k: int = 5,
    knowledge_type: str = None,
) -> List[Dict]:
    """
    Search knowledge base menggunakan Gemini Embedding 2 + ChromaDB.
    Jauh lebih cepat dan akurat dari versi lama (brute-force loop).
    """
    knowledge_collection, chunks_collection = _get_collections()
    results = []
    
    # Embed query dengan task_type RETRIEVAL_QUERY (beda dari RETRIEVAL_DOCUMENT)
    query_embedding = embed_text(query, task_type="RETRIEVAL_QUERY")
    
    # Validate query embedding format
    if query_embedding and isinstance(query_embedding[0], (list, tuple)):
        query_embedding = [float(x) for x in query_embedding[0]]
    
    if query_embedding is None:
        logger.warning("Failed to embed query, falling back to keyword search")
        return _keyword_fallback(query, top_k)
    
    # --- Search structured knowledge ---
    if knowledge_collection.count() > 0:
        try:
            kb_results = knowledge_collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, knowledge_collection.count()),
            )
            
            if kb_results and kb_results["ids"] and kb_results["ids"][0]:
                for i, doc_id in enumerate(kb_results["ids"][0]):
                    metadata = kb_results["metadatas"][0][i] if kb_results["metadatas"] else {}
                    distance = kb_results["distances"][0][i] if kb_results["distances"] else 1.0
                    score = 1.0 - distance  # ChromaDB cosine distance -> similarity
                    
                    # Retrieve full knowledge data
                    kb_index = metadata.get("index", -1)
                    kb_data = _KNOWLEDGE_DB[kb_index] if 0 <= kb_index < len(_KNOWLEDGE_DB) else {}
                    
                    results.append({
                        "type": "structured_knowledge",
                        "score": score,
                        "equipment_type": metadata.get("equipment_type", ""),
                        "brand": metadata.get("brand", ""),
                        "model": metadata.get("model", ""),
                        "data": kb_data,
                    })
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
    
    # --- Search text chunks ---
    if chunks_collection.count() > 0:
        try:
            chunk_results = chunks_collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, chunks_collection.count()),
            )
            
            if chunk_results and chunk_results["ids"] and chunk_results["ids"][0]:
                for i, doc_id in enumerate(chunk_results["ids"][0]):
                    distance = chunk_results["distances"][0][i] if chunk_results["distances"] else 1.0
                    score = 1.0 - distance
                    document = chunk_results["documents"][0][i] if chunk_results["documents"] else ""
                    metadata = chunk_results["metadatas"][0][i] if chunk_results["metadatas"] else {}
                    
                    results.append({
                        "type": "text_chunk",
                        "score": score,
                        "text": document[:800],
                        "source": metadata.get("source_file", ""),
                    })
        except Exception as e:
            logger.error(f"Chunks search failed: {e}")
    
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def _keyword_fallback(query: str, top_k: int) -> List[Dict]:
    """Fallback ke keyword search jika embedding gagal (misalnya API down)."""
    results = []
    query_words = set(query.lower().split())
    
    for kb in _KNOWLEDGE_DB:
        searchable = _build_searchable_text(kb).lower()
        text_words = set(searchable.split())
        overlap = query_words & text_words
        score = len(overlap) / max(len(query_words), 1)
        
        results.append({
            "type": "structured_knowledge",
            "score": score,
            "equipment_type": kb.get("equipment_type", ""),
            "brand": kb.get("brand", ""),
            "model": kb.get("model", ""),
            "data": kb,
        })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def get_context_for_query(query: str, max_tokens: int = 2000) -> str:
    """
    Main entry point - dipanggil dari gemini_live.py.
    Signature SAMA PERSIS dengan rag_engine.py lama supaya tidak perlu ubah gemini_live.py.
    """
    results = search_knowledge(query, top_k=5)
    
    if not results:
        return ""
    
    context_parts = []
    char_count = 0
    
    for r in results:
        if r["type"] == "structured_knowledge":
            kb = r["data"]
            part = _format_knowledge_entry(kb)
        else:
            part = f"[Reference]\n{r['text'][:600]}"
        
        if char_count + len(part) > max_tokens * 4:
            break
        context_parts.append(part)
        char_count += len(part)
    
    if not context_parts:
        return ""
    
    return (
        "\n\n=== RELEVANT KNOWLEDGE BASE CONTEXT ===\n\n"
        + "\n\n---\n\n".join(context_parts)
        + "\n\n=== END CONTEXT ==="
    )


def _format_knowledge_entry(kb: Dict) -> str:
    """Format knowledge entry untuk konteks. SAMA dengan rag_engine.py lama."""
    parts = []
    eq = kb.get("equipment_type", "")
    brand = kb.get("brand", "")
    model_name = kb.get("model", "")
    header = " ".join(filter(None, [brand, model_name, eq])).strip()
    if header:
        parts.append(f"[Equipment: {header}]")
    
    components = kb.get("components", [])
    if components:
        parts.append(f"Components: {', '.join(components[:15])}")
    
    symptoms = kb.get("symptoms", [])
    if symptoms:
        parts.append(f"Common symptoms: {', '.join(symptoms[:8])}")
    
    failures = kb.get("common_failures", [])
    if failures:
        parts.append(f"Common failures: {'; '.join(failures[:5])}")
    
    diag = kb.get("diagnostic_steps", [])
    if diag:
        steps_str = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(diag[:8]))
        parts.append(f"Diagnostic steps:\n{steps_str}")
    
    repair = kb.get("repair_steps", [])
    if repair:
        steps_str = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(repair[:10]))
        parts.append(f"Repair procedure:\n{steps_str}")
    
    tools = kb.get("tools_required", [])
    if tools:
        parts.append(f"Tools required: {', '.join(tools[:10])}")
    
    safety = kb.get("safety_warnings", [])
    if safety:
        parts.append("SAFETY WARNINGS:\n" + "\n".join(f"  !! {w}" for w in safety[:5]))
    
    specs = kb.get("specifications", {})
    if specs:
        spec_str = ", ".join(f"{k}: {v}" for k, v in specs.items())
        parts.append(f"Specifications: {spec_str}")
    
    torque = kb.get("torque_specs", [])
    if torque:
        t_str = ", ".join(
            f"{t.get('component','')}: {t.get('value','')} {t.get('unit','')}"
            for t in torque[:5]
        )
        parts.append(f"Torque specs: {t_str}")
    
    maint = kb.get("maintenance_schedule", [])
    if maint:
        m_str = "; ".join(m.get("interval", "") for m in maint[:5])
        parts.append(f"Maintenance schedule: {m_str}")
    
    trouble = kb.get("troubleshooting_table", [])
    if trouble:
        for t in trouble[:3]:
            parts.append(
                f"Troubleshooting: Problem={t.get('problem','')} | "
                f"Cause={t.get('cause','')} | "
                f"Solution={t.get('solution','')}"
            )
    
    return "\n".join(parts)


def get_equipment_list() -> List[Dict]:
    """Return list equipment. SAMA signature dengan rag_engine.py lama."""
    equipment = []
    for kb in _KNOWLEDGE_DB:
        equipment.append({
            "equipment_type": kb.get("equipment_type", ""),
            "brand": kb.get("brand", ""),
            "model": kb.get("model", ""),
            "confidence": kb.get("confidence_scores", {}).get("overall", 0),
        })
    return equipment


def force_reindex():
    """Hapus ChromaDB collections dan re-index dari awal. Untuk migrasi/debug."""
    global _LOADED, _KNOWLEDGE_DB, _knowledge_collection, _chunks_collection
    
    client = _get_chroma_client()
    
    # Hapus collections lama
    try:
        client.delete_collection("equipment_knowledge_v2")
        logger.info("Deleted old knowledge collection")
    except Exception:
        pass
    try:
        client.delete_collection("text_chunks_v2")
        logger.info("Deleted old chunks collection")
    except Exception:
        pass
    
    # Reset state
    _knowledge_collection = None
    _chunks_collection = None
    _KNOWLEDGE_DB = []
    _LOADED = False
    
    # Re-load dan re-index
    load_knowledge_base()
    logger.info("Force re-index completed!")


# Auto-load on import
load_knowledge_base()

