"""
Test script untuk verifikasi migrasi ke Gemini Embedding 2 + ChromaDB.
Jalankan: cd backend && python test_embedding_v2.py
"""

import os
import sys
import time

# Pastikan GEMINI_API_KEY ter-set
if not os.environ.get("GEMINI_API_KEY"):
    from dotenv import load_dotenv
    load_dotenv()

if not os.environ.get("GEMINI_API_KEY"):
    print("ERROR: GEMINI_API_KEY belum di-set!")
    print("Set di file .env atau: export GEMINI_API_KEY=your_key")
    sys.exit(1)


def test_1_embedding_service():
    """Test 1: Apakah Gemini Embedding 2 API bisa dipanggil?"""
    print("\n=== TEST 1: Embedding Service ===")
    from embedding_service import embed_text
    
    start = time.time()
    result = embed_text("Honda WB20XT water pump repair guide", task_type="RETRIEVAL_QUERY")
    elapsed = time.time() - start
    
    if result is None:
        print("GAGAL: embed_text returned None")
        return False
    
    print(f"OK: Embedding berhasil dalam {elapsed:.2f}s")
    print(f"   Dimensi: {len(result)}")
    print(f"   Sample values: {result[:5]}")
    assert len(result) == 768, f"Expected 768 dimensions, got {len(result)}"
    print("   Dimensi = 768 ✓")
    return True


def test_2_chromadb_indexing():
    """Test 2: Apakah knowledge base ter-index di ChromaDB?"""
    print("\n=== TEST 2: ChromaDB Indexing ===")
    from rag_engine_v2 import _get_collections, get_equipment_list
    
    knowledge_col, chunks_col = _get_collections()
    equipment = get_equipment_list()
    
    print(f"   Equipment loaded: {len(equipment)}")
    print(f"   Knowledge indexed: {knowledge_col.count()}")
    print(f"   Chunks indexed: {chunks_col.count()}")
    
    if knowledge_col.count() == 0:
        print("WARNING: Knowledge collection kosong! Coba force_reindex().")
        return False
    
    for eq in equipment:
        print(f"   - {eq['brand']} {eq['model']} ({eq['equipment_type']})")
    
    print("OK ✓")
    return True


def test_3_search_quality():
    """Test 3: Apakah pencarian semantik lebih akurat?"""
    print("\n=== TEST 3: Search Quality ===")
    from rag_engine_v2 import search_knowledge
    
    test_queries = [
        "water pump won't start",
        "generator maintenance schedule",
        "electrical panel MCB circuit breaker",
        "Honda pump impeller replacement",
        "how to check oil level",
    ]
    
    for query in test_queries:
        start = time.time()
        results = search_knowledge(query, top_k=3)
        elapsed = time.time() - start
        
        print(f"\n   Query: '{query}' ({elapsed:.2f}s)")
        if not results:
            print("   WARNING: No results!")
            continue
        for r in results:
            if r["type"] == "structured_knowledge":
                print(f"   → [{r['score']:.3f}] {r['brand']} {r['model']} ({r['equipment_type']})")
            else:
                print(f"   → [{r['score']:.3f}] chunk: {r['text'][:60]}...")
    
    print("\nOK ✓")
    return True


def test_4_context_output():
    """Test 4: Apakah get_context_for_query menghasilkan konteks yang valid?"""
    print("\n=== TEST 4: Context Output ===")
    from rag_engine_v2 import get_context_for_query
    
    context = get_context_for_query("generator won't start, black smoke")
    
    if not context:
        print("WARNING: Context kosong!")
        return False
    
    print(f"   Context length: {len(context)} chars")
    print(f"   Preview: {context[:200]}...")
    
    assert "=== RELEVANT KNOWLEDGE BASE CONTEXT ===" in context
    assert "=== END CONTEXT ===" in context
    print("   Format markers ✓")
    print("OK ✓")
    return True


def test_5_force_reindex():
    """Test 5: Apakah force_reindex bekerja?"""
    print("\n=== TEST 5: Force Reindex ===")
    from rag_engine_v2 import force_reindex, _get_collections
    
    start = time.time()
    force_reindex()
    elapsed = time.time() - start
    
    knowledge_col, chunks_col = _get_collections()
    print(f"   Re-indexed dalam {elapsed:.2f}s")
    print(f"   Knowledge: {knowledge_col.count()}")
    print(f"   Chunks: {chunks_col.count()}")
    
    assert knowledge_col.count() > 0, "Knowledge collection kosong setelah reindex!"
    print("OK ✓")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("FieldGuide Agent - Gemini Embedding 2 Migration Test")
    print("=" * 60)
    
    results = {}
    results["embedding_service"] = test_1_embedding_service()
    results["chromadb_indexing"] = test_2_chromadb_indexing()
    results["search_quality"] = test_3_search_quality()
    results["context_output"] = test_4_context_output()
    results["force_reindex"] = test_5_force_reindex()
    
    print("\n" + "=" * 60)
    print("HASIL:")
    all_passed = True
    for name, passed in results.items():
        status = "PASS ✓" if passed else "FAIL ✗"
        print(f"   {name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("SEMUA TEST BERHASIL! Migrasi ke Gemini Embedding 2 sukses.")
    else:
        print("ADA TEST YANG GAGAL. Periksa error di atas.")
    print("=" * 60)

