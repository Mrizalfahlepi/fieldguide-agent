import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional


logger = logging.getLogger("FieldGuide-RAG")


_EMBEDDING_MODEL = None
_KNOWLEDGE_DB: List[Dict] = []
_CHUNK_DB: List[Dict] = []
_LOADED = False


def _get_embedding_model():
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers embedding model")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "RAG will use keyword search fallback."
            )
            _EMBEDDING_MODEL = False
    return _EMBEDDING_MODEL if _EMBEDDING_MODEL is not False else None


def _cosine_sim(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb + 1e-9)


def load_knowledge_base(base_dir: str = None):
    global _KNOWLEDGE_DB, _CHUNK_DB, _LOADED

    if _LOADED:
        logger.info("Knowledge base already loaded, skipping.")
        return

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

    # --- Load from knowledge_base.jsonl ONLY (not individual JSONs) ---
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
        # Fallback: load individual *_knowledge.json files
        for jf in knowledge_dir.glob("*_knowledge.json"):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                _KNOWLEDGE_DB.append(data)
                logger.info(f"Loaded knowledge: {jf.name}")
            except Exception as e:
                logger.warning(f"Failed to load {jf}: {e}")

    # --- Load text chunks from same directory ---
    for cf in knowledge_dir.glob("*_chunks.jsonl"):
        try:
            with open(cf, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        chunk = json.loads(line)
                        _CHUNK_DB.append(chunk)
        except Exception as e:
            logger.warning(f"Failed to load chunks {cf}: {e}")

    _LOADED = True
    logger.info(
        f"Knowledge base loaded: {len(_KNOWLEDGE_DB)} documents, "
        f"{len(_CHUNK_DB)} text chunks"
    )


def _keyword_score(query: str, text: str) -> float:
    query_words = set(query.lower().split())
    text_words = set(text.lower().split())
    if not query_words:
        return 0.0
    overlap = query_words & text_words
    return len(overlap) / len(query_words)


def search_knowledge(
    query: str,
    top_k: int = 5,
    knowledge_type: str = None,
) -> List[Dict]:
    results = []
    model = _get_embedding_model()

    # Cache query embedding so we don't re-encode per item
    q_emb = None
    if model:
        q_emb = model.encode(query).tolist()

    # --- Search structured knowledge ---
    for kb in _KNOWLEDGE_DB:
        searchable_parts = [
            f"Equipment: {kb.get('equipment_type', '')}",
            f"Brand: {kb.get('brand', '')}",
            f"Model: {kb.get('model', '')}",
            f"Components: {', '.join(kb.get('components', []))}",
            f"Symptoms: {', '.join(kb.get('symptoms', []))}",
            f"Safety: {' '.join(kb.get('safety_warnings', [])[:3])}",
            f"Tools: {', '.join(kb.get('tools_required', []))}",
        ]
        searchable_text = " ".join(searchable_parts)

        if q_emb:
            d_emb = model.encode(searchable_text).tolist()
            score = _cosine_sim(q_emb, d_emb)
        else:
            score = _keyword_score(query, searchable_text)

        results.append({
            "type": "structured_knowledge",
            "score": score,
            "equipment_type": kb.get("equipment_type", ""),
            "brand": kb.get("brand", ""),
            "model": kb.get("model", ""),
            "data": kb,
        })

    # --- Search text chunks ---
    for chunk in _CHUNK_DB:
        text = chunk.get("text", "")
        if not text:
            continue

        if q_emb:
            c_emb = model.encode(text[:500]).tolist()
            score = _cosine_sim(q_emb, c_emb)
        else:
            score = _keyword_score(query, text)

        results.append({
            "type": "text_chunk",
            "score": score,
            "text": text[:800],
            "source": chunk.get("source_file", ""),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def get_context_for_query(query: str, max_tokens: int = 2000) -> str:
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
    equipment = []
    for kb in _KNOWLEDGE_DB:
        equipment.append({
            "equipment_type": kb.get("equipment_type", ""),
            "brand": kb.get("brand", ""),
            "model": kb.get("model", ""),
            "confidence": kb.get("confidence_scores", {}).get("overall", 0),
        })
    return equipment


# Auto-load on import
load_knowledge_base()
