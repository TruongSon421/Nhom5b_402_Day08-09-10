"""
rag_answer.py — Sprint 2 + Sprint 3: Retrieval & Grounded Answer
================================================================
Sprint 2 (60 phút): Baseline RAG
  - Dense retrieval từ ChromaDB
  - Grounded answer function với prompt ép citation
  - Trả lời được ít nhất 3 câu hỏi mẫu, output có source

Sprint 3 (60 phút): Tuning tối thiểu
  - Hybrid retrieval (dense + BM25) với Reciprocal Rank Fusion
  - Lý do chọn: corpus lẫn lộn câu tự nhiên VÀ keyword/mã lỗi (ERR-403, P1, Level 3)
  - Bảng so sánh baseline vs variant qua compare_retrieval_strategies()

Definition of Done Sprint 2:
  ✓ rag_answer("SLA ticket P1?") trả về câu trả lời có citation
  ✓ rag_answer("Câu hỏi không có trong docs") trả về "Không đủ dữ liệu"

Definition of Done Sprint 3:
  ✓ Hybrid retrieval (dense + BM25 RRF) chạy được end-to-end
  ✓ Giải thích được tại sao chọn hybrid (ghi vào docs/tuning-log.md)
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CẤU HÌNH
# =============================================================================

TOP_K_SEARCH = 10    # Số chunk lấy từ vector store trước rerank (search rộng)
TOP_K_SELECT = 3     # Số chunk gửi vào prompt sau rerank/select (top-3 sweet spot)

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


# =============================================================================
# RETRIEVAL — DENSE (Vector Search)
# =============================================================================

def retrieve_dense(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Dense retrieval: tìm kiếm theo embedding similarity trong ChromaDB.

    Args:
        query: Câu hỏi của người dùng
        top_k: Số chunk tối đa trả về

    Returns:
        List các dict, mỗi dict là một chunk với:
          - "text": nội dung chunk
          - "metadata": metadata (source, section, effective_date, ...)
          - "score": cosine similarity score (1 - distance)
    """
    import chromadb
    from index import get_embedding, CHROMA_DB_DIR

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("rag_lab")

    query_embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "metadata": meta,
            "score": 1.0 - dist,   # ChromaDB cosine distance → similarity
        })

    return chunks


# =============================================================================
# RETRIEVAL — SPARSE / BM25 (Keyword Search)
# Sprint 3: Hybrid variant
# =============================================================================

def _load_all_chunks() -> List[Dict[str, Any]]:
    """Load toàn bộ chunks từ ChromaDB để build BM25 index."""
    import chromadb
    from index import CHROMA_DB_DIR

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("rag_lab")
    results = collection.get(include=["documents", "metadatas"])

    chunks = []
    for doc_id, doc, meta in zip(
        results["ids"], results["documents"], results["metadatas"]
    ):
        chunks.append({"id": doc_id, "text": doc, "metadata": meta, "score": 0.0})
    return chunks


def retrieve_sparse(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Sparse retrieval: tìm kiếm theo keyword (BM25).

    Mạnh ở: exact term, mã lỗi, tên riêng (ERR-403, P1, Level 3)
    Hay hụt: câu hỏi paraphrase, đồng nghĩa
    """
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        print("[retrieve_sparse] rank-bm25 chưa cài. Chạy: pip install rank-bm25")
        return []

    all_chunks = _load_all_chunks()
    if not all_chunks:
        return []

    corpus = [chunk["text"] for chunk in all_chunks]
    tokenized_corpus = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results = []
    for idx in top_indices:
        chunk = all_chunks[idx].copy()
        chunk["score"] = float(scores[idx])
        results.append(chunk)

    return results


# =============================================================================
# RETRIEVAL — HYBRID (Dense + Sparse với Reciprocal Rank Fusion)
# Sprint 3: Variant được chọn
# =============================================================================

def retrieve_hybrid(
    query: str,
    top_k: int = TOP_K_SEARCH,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: kết hợp dense và sparse bằng Reciprocal Rank Fusion (RRF).

    Lý do chọn variant này (Sprint 3):
    - Corpus có cả câu tự nhiên (chính sách, quy trình) VÀ keyword/mã lỗi (P1, ERR-403, Level 3)
    - Dense tốt cho câu hỏi paraphrase ("hoàn tiền" ↔ "refund")
    - BM25 tốt cho exact match ("ERR-403-AUTH", "Level 3", "P1")
    - RRF kết hợp cả hai mà không cần normalize score

    RRF formula: score(doc) = dense_weight / (60 + dense_rank)
                            + sparse_weight / (60 + sparse_rank)
    60 là hằng số RRF tiêu chuẩn (Cormack et al. 2009)
    """
    dense_results = retrieve_dense(query, top_k=top_k)
    sparse_results = retrieve_sparse(query, top_k=top_k)

    # Nếu sparse không có kết quả (chưa cài rank-bm25), fallback về dense
    if not sparse_results:
        print("[retrieve_hybrid] Sparse rỗng — fallback về dense")
        return dense_results

    # Build lookup: chunk text → chunk dict
    all_chunks: Dict[str, Dict[str, Any]] = {}
    for chunk in dense_results + sparse_results:
        key = chunk["text"]
        if key not in all_chunks:
            all_chunks[key] = chunk

    # Tính RRF score
    rrf_scores: Dict[str, float] = {key: 0.0 for key in all_chunks}

    for rank, chunk in enumerate(dense_results):
        key = chunk["text"]
        rrf_scores[key] += dense_weight / (60 + rank + 1)

    for rank, chunk in enumerate(sparse_results):
        key = chunk["text"]
        rrf_scores[key] += sparse_weight / (60 + rank + 1)

    # Sort theo RRF score giảm dần
    sorted_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)

    results = []
    for key in sorted_keys[:top_k]:
        chunk = all_chunks[key].copy()
        chunk["score"] = rrf_scores[key]
        results.append(chunk)

    return results


# =============================================================================
# RERANK (Sprint 3 alternative — không dùng, đã chọn hybrid)
# =============================================================================

def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = TOP_K_SELECT,
) -> List[Dict[str, Any]]:
    """
    Rerank các candidate chunks bằng cross-encoder.
    Hiện tại trả về top_k đầu tiên (không rerank) vì Sprint 3 dùng hybrid.
    """
    return candidates[:top_k]


# =============================================================================
# QUERY TRANSFORMATION (Sprint 3 alternative — không dùng, đã chọn hybrid)
# =============================================================================

def transform_query(query: str, strategy: str = "expansion") -> List[str]:
    """
    Biến đổi query để tăng recall.
    Hiện tại trả về query gốc vì Sprint 3 dùng hybrid.
    """
    return [query]


# =============================================================================
# GENERATION — GROUNDED ANSWER FUNCTION
# =============================================================================

def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """
    Đóng gói danh sách chunks thành context block để đưa vào prompt.

    Format: structured snippets với source, section, score.
    Mỗi chunk có số thứ tự [1], [2], ... để model dễ trích dẫn.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "unknown")
        section = meta.get("section", "")
        score = chunk.get("score", 0)
        text = chunk.get("text", "")

        header = f"[{i}] {source}"
        if section:
            header += f" | {section}"
        if score > 0:
            header += f" | score={score:.3f}"

        context_parts.append(f"{header}\n{text}")

    return "\n\n".join(context_parts)


def build_grounded_prompt(query: str, context_block: str) -> str:
    """
    Grounded prompt theo 4 quy tắc:
    1. Evidence-only: Chỉ trả lời từ retrieved context
    2. Abstain: Thiếu context thì nói không đủ dữ liệu
    3. Citation: Gắn source/section khi có thể
    4. Short, clear, stable: Output ngắn, rõ, nhất quán
    """
    prompt = f"""You are a strict grounded QA assistant.

Rules:
1) Use ONLY the retrieved context. Never infer or add facts not present in context.
2) If the question has multiple requirements, answer ALL requirements in a structured way.
3) If context is insufficient for the entire question, respond exactly:
"Không đủ dữ liệu trong tài liệu hiện có."
4) If context is sufficient for some requirements but missing for others, answer available parts and explicitly state which part is missing.
5) Cite source numbers in brackets (e.g. [1], [2]) for each key claim.
6) Respond in the same language as the question.
7) Keep the answer concise, clear, and factual.

Output format:
- If question has one requirement: one short paragraph.
- If question has multiple requirements: bullet points, one bullet per requirement.

Question: {query}

Context:
{context_block}

Answer:"""
    return prompt


def call_llm(prompt: str, model: Optional[str] = None) -> str:
    """
    Gọi OpenAI để sinh câu trả lời.
    Dùng temperature=0 để output ổn định cho evaluation.
    """
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model or LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=512,
    )
    return response.choices[0].message.content


def rag_answer(
    query: str,
    retrieval_mode: str = "dense",
    top_k_search: int = TOP_K_SEARCH,
    top_k_select: int = TOP_K_SELECT,
    use_rerank: bool = False,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Pipeline RAG hoàn chỉnh: query → retrieve → (rerank) → generate.

    Args:
        query: Câu hỏi
        retrieval_mode: "dense" | "sparse" | "hybrid"
        top_k_search: Số chunk lấy từ vector store (search rộng)
        top_k_select: Số chunk đưa vào prompt (sau rerank/select)
        use_rerank: Có dùng cross-encoder rerank không
        dense_weight: Trọng số dense trong hybrid RRF
        sparse_weight: Trọng số sparse trong hybrid RRF
        verbose: In thêm thông tin debug

    Returns:
        Dict với:
          - "answer": câu trả lời grounded
          - "sources": list source names trích dẫn
          - "chunks_used": list chunks đã dùng
          - "query": query gốc
          - "config": cấu hình pipeline đã dùng
    """
    config = {
        "retrieval_mode": retrieval_mode,
        "top_k_search": top_k_search,
        "top_k_select": top_k_select,
        "use_rerank": use_rerank,
        "dense_weight": dense_weight,
        "sparse_weight": sparse_weight,
    }

    # --- Bước 1: Retrieve ---
    if retrieval_mode == "dense":
        candidates = retrieve_dense(query, top_k=top_k_search)
    elif retrieval_mode == "sparse":
        candidates = retrieve_sparse(query, top_k=top_k_search)
    elif retrieval_mode == "hybrid":
        candidates = retrieve_hybrid(
            query,
            top_k=top_k_search,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
        )
    else:
        raise ValueError(f"retrieval_mode không hợp lệ: {retrieval_mode}")

    if verbose:
        print(f"\n[RAG] Query: {query}")
        print(f"[RAG] Retrieved {len(candidates)} candidates (mode={retrieval_mode})")
        for i, c in enumerate(candidates[:3]):
            print(f"  [{i+1}] score={c.get('score', 0):.3f} | {c['metadata'].get('source', '?')}")

    # --- Bước 2: Rerank (optional) ---
    if use_rerank:
        candidates = rerank(query, candidates, top_k=top_k_select)
    else:
        candidates = candidates[:top_k_select]

    if verbose:
        print(f"[RAG] After select: {len(candidates)} chunks")

    # --- Bước 3: Build context và prompt ---
    context_block = build_context_block(candidates)
    prompt = build_grounded_prompt(query, context_block)

    if verbose:
        print(f"\n[RAG] Prompt (first 500 chars):\n{prompt[:500]}...\n")

    # --- Bước 4: Generate ---
    answer = call_llm(prompt)

    # --- Bước 5: Extract sources ---
    sources = list({
        c["metadata"].get("source", "unknown")
        for c in candidates
    })

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "chunks_used": candidates,
        "config": config,
    }


# =============================================================================
# SPRINT 3: SO SÁNH BASELINE VS VARIANT
# =============================================================================

def compare_retrieval_strategies(query: str) -> None:
    """
    So sánh dense vs hybrid với cùng một query.
    A/B Rule: chỉ đổi retrieval_mode, giữ nguyên mọi thứ khác.
    """
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print('='*60)

    strategies = ["dense", "hybrid"]

    for strategy in strategies:
        print(f"\n--- Strategy: {strategy} ---")
        try:
            result = rag_answer(query, retrieval_mode=strategy, verbose=False)
            print(f"Answer: {result['answer']}")
            print(f"Sources: {result['sources']}")
        except Exception as e:
            print(f"Lỗi: {e}")


# =============================================================================
# MAIN — Demo và Test
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 2 + 3: RAG Answer Pipeline")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?",
        "Ai phải phê duyệt để cấp quyền Level 3?",
        "ERR-403-AUTH là lỗi gì?",   # Không có trong docs → kiểm tra abstain
    ]

    print("\n--- Sprint 2: Test Baseline (Dense) ---")
    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = rag_answer(query, retrieval_mode="dense", verbose=True)
            print(f"Answer: {result['answer']}")
            print(f"Sources: {result['sources']}")
        except Exception as e:
            print(f"Lỗi: {e}")

    print("\n--- Sprint 3: So sánh Dense vs Hybrid ---")
    compare_retrieval_strategies("Approval Matrix để cấp quyền hệ thống là tài liệu nào?")
    compare_retrieval_strategies("ERR-403-AUTH")
