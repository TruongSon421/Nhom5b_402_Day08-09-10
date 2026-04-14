"""
workers/synthesis.py — Synthesis Worker
Sprint 2: Tổng hợp câu trả lời từ retrieved_chunks và policy_result.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: evidence từ retrieval_worker
    - policy_result: kết quả từ policy_tool_worker

Output (vào AgentState):
    - final_answer: câu trả lời cuối với citation
    - sources: danh sách nguồn tài liệu được cite
    - confidence: mức độ tin cậy (0.0 - 1.0)

Gọi độc lập để test:
    python workers/synthesis.py
"""
import os
import json

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

WORKER_NAME = "synthesis_worker"

SYSTEM_PROMPT = """Bạn là trợ lý IT Helpdesk nội bộ.

Quy tắc nghiêm ngặt:
1. CHỈ trả lời dựa vào context được cung cấp. KHÔNG dùng kiến thức ngoài.
2. Nếu context không đủ để trả lời → nói rõ "Không đủ thông tin trong tài liệu nội bộ".
3. Trích dẫn nguồn cuối mỗi câu quan trọng: [tên_file].
4. Trả lời súc tích, có cấu trúc. Không dài dòng.
5. Nếu có exceptions/ngoại lệ → nêu rõ ràng trước khi kết luận.

QUAN TRỌNG: ĐỊNH DẠNG ĐẦU RA
Bạn BẮT BUỘC phải trả kết quả theo đúng chuẩn JSON với cấu trúc dưới đây (KHÔNG dùng markdown backticks, KHÔNG in ra text nào khác ngoài JSON):
{
    "answer": "Câu trả lời của bạn, có thể xuống dòng bằng ký tự \\n"
}
"""


def _call_llm(messages: list) -> str:
    """
    Gọi LLM để tổng hợp câu trả lời.
    TODO Sprint 2: Implement với OpenAI hoặc Gemini.
    """
    # Option A: OpenAI
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.1,  # Low temperature để grounded
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception:
        pass

    # Option B: Gemini
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-1.5-flash")
        combined = "\n".join([m["content"] for m in messages])
        response = model.generate_content(combined)
        return response.text
    except Exception:
        pass

    # Fallback: trả về message báo lỗi (không hallucinate)
    return "[SYNTHESIS ERROR] Không thể gọi LLM. Kiểm tra API key trong .env."


def _build_context(chunks: list, policy_result: dict) -> str:
    """Xây dựng context string từ chunks và policy result."""
    parts = []

    if chunks:
        parts.append("=== TÀI LIỆU THAM KHẢO ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)
            parts.append(f"[{i}] Nguồn: {source} (relevance: {score:.2f})\n{text}")

    if policy_result and policy_result.get("exceptions_found"):
        parts.append("\n=== POLICY EXCEPTIONS ===")
        for ex in policy_result["exceptions_found"]:
            parts.append(f"- {ex.get('rule', '')}")

    if policy_result and policy_result.get("policy_version_note"):
        parts.append(f"\n=== POLICY VERSION NOTE ===\n{policy_result['policy_version_note']}")

    if policy_result and policy_result.get("store_credit_info"):
        parts.append(f"\n=== STORE CREDIT INFO ===\n{policy_result['store_credit_info']}")

    if policy_result and policy_result.get("refund_window_info"):
        parts.append(f"\n=== REFUND WINDOW INFO ===\n{policy_result['refund_window_info']}")

    if not parts:
        return "(Không có context)"

    return "\n\n".join(parts)


def _estimate_confidence_llm_judge(chunks: list, answer: str, policy_result: dict, task: str) -> float:
    """
    Sử dụng LLM-as-Judge để đánh giá confidence của câu trả lời.
    
    LLM sẽ đánh giá dựa trên:
    - Evidence quality: Chunks có đủ thông tin không?
    - Answer grounding: Câu trả lời có dựa vào evidence không?
    - Completeness: Câu trả lời có đầy đủ không?
    - Uncertainty indicators: Có dấu hiệu không chắc chắn không?
    
    Returns: confidence score từ 0.0 đến 1.0
    """
    JUDGE_PROMPT = """Bạn là một chuyên gia đánh giá chất lượng câu trả lời RAG (Retrieval-Augmented Generation).

Nhiệm vụ: Đánh giá mức độ tin cậy (confidence) của câu trả lời dựa trên evidence được cung cấp.

Tiêu chí đánh giá:
1. Evidence Quality (0-0.3): Chunks có đủ thông tin để trả lời câu hỏi không?
   - 0.3: Evidence rất đầy đủ, chi tiết, trực tiếp
   - 0.2: Evidence đủ nhưng có thể thiếu một số chi tiết
   - 0.1: Evidence mơ hồ hoặc gián tiếp
   - 0.0: Không có evidence hoặc không liên quan

2. Answer Grounding (0-0.4): Câu trả lời có dựa chặt chẽ vào evidence không?
   - 0.4: Mỗi phần của câu trả lời đều có evidence hỗ trợ
   - 0.3: Phần lớn câu trả lời có evidence
   - 0.2: Một số phần thiếu evidence
   - 0.1: Câu trả lời có thể hallucinate
   - 0.0: Câu trả lời không dựa vào evidence

3. Completeness (0-0.2): Câu trả lời có đầy đủ không?
   - 0.2: Trả lời đầy đủ tất cả khía cạnh của câu hỏi
   - 0.1: Trả lời một phần
   - 0.0: Không trả lời được hoặc abstain

4. Uncertainty Handling (0-0.1): Xử lý sự không chắc chắn
   - 0.1: Thừa nhận rõ ràng khi thiếu thông tin
   - 0.05: Có một số hedging phrases hợp lý
   - 0.0: Không thừa nhận uncertainty khi cần thiết

Trả về JSON với format:
{
    "evidence_quality": 0.0-0.3,
    "answer_grounding": 0.0-0.4,
    "completeness": 0.0-0.2,
    "uncertainty_handling": 0.0-0.1,
    "total_confidence": 0.0-1.0,
    "reasoning": "Giải thích ngắn gọn"
}
"""

    # Build evaluation context
    context_parts = []
    context_parts.append(f"=== CÂU HỎI ===\n{task}")
    context_parts.append(f"\n=== CÂU TRẢ LỜI ===\n{answer}")
    
    if chunks:
        context_parts.append("\n=== EVIDENCE (CHUNKS) ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)
            context_parts.append(f"[{i}] {source} (score: {score:.2f})\n{text}")
    else:
        context_parts.append("\n=== EVIDENCE ===\n(Không có chunks)")
    
    if policy_result and policy_result.get("exceptions_found"):
        context_parts.append(f"\n=== POLICY EXCEPTIONS ===\n{len(policy_result['exceptions_found'])} exceptions found")
    
    eval_context = "\n".join(context_parts)
    
    messages = [
        {"role": "system", "content": JUDGE_PROMPT},
        {"role": "user", "content": eval_context}
    ]
    
    try:
        llm_output = _call_llm(messages)
        print(f"✅ LLM-as-Judge response received (length: {len(llm_output)})")
        
        # Parse JSON response
        cleaned = llm_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        
        judge_result = json.loads(cleaned)
        confidence = float(judge_result.get("total_confidence", 0.0))
        
        # Clamp to valid range
        confidence = max(0.0, min(1.0, confidence))
        
        # Log reasoning for debugging
        reasoning = judge_result.get("reasoning", "")
        print(f"🔍 LLM Judge breakdown: EQ={judge_result.get('evidence_quality', 0)}, AG={judge_result.get('answer_grounding', 0)}, C={judge_result.get('completeness', 0)}, UH={judge_result.get('uncertainty_handling', 0)}")
        if reasoning:
            print(f"� Reasoning: {reasoning}")
        
        return round(confidence, 2)
        
    except Exception as e:
        print(f"⚠️ LLM-as-Judge failed: {e}, falling back to heuristic")
        return _estimate_confidence_heuristic(chunks, answer, policy_result)


def _estimate_confidence_heuristic(chunks: list, answer: str, policy_result: dict) -> float:
    """
    Fallback heuristic method khi LLM-as-Judge không khả dụng.
    Đây là phương pháp cũ, giữ lại để fallback.
    """
    if not chunks:
        return 0.1  # Không có evidence → low confidence

    if "Không đủ thông tin" in answer or "không có trong tài liệu" in answer.lower():
        return 0.3  # Abstain → moderate-low

    # Weighted average của chunk scores
    if chunks:
        avg_score = sum(c.get("score", 0) for c in chunks) / len(chunks)
    else:
        avg_score = 0

    # Penalty nếu có exceptions (phức tạp hơn)
    exception_penalty = 0.05 * len(policy_result.get("exceptions_found", []))

    confidence = min(0.95, avg_score - exception_penalty)
    return round(max(0.1, confidence), 2)


def _estimate_confidence(chunks: list, answer: str, policy_result: dict, task: str = "") -> float:
    """
    Wrapper function để chọn giữa LLM-as-Judge và heuristic.
    
    Mặc định sử dụng LLM-as-Judge, fallback về heuristic nếu có lỗi.
    """
    # Có thể thêm flag để disable LLM judge nếu cần
    use_llm_judge = os.getenv("USE_LLM_JUDGE", "true").lower() == "true"
    
    if use_llm_judge and task:
        print("🤖 Using LLM-as-Judge for confidence estimation...")
        return _estimate_confidence_llm_judge(chunks, answer, policy_result, task)
    else:
        print("📊 Using heuristic method for confidence estimation...")
        return _estimate_confidence_heuristic(chunks, answer, policy_result)


def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    """
    Tổng hợp câu trả lời từ chunks và policy context. Tham khảo LLM làm LLM-as-a-Judge.
    Returns:
        {"answer": str, "sources": list, "confidence": float}
    """
    context = _build_context(chunks, policy_result)

    # Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Câu hỏi: {task}

{context}

Hãy trả lời câu hỏi dựa vào tài liệu (đảm bảo xuất JSON format)."""
        }
    ]

    llm_output = _call_llm(messages)
    
    # Parse JSON để lấy answer (bỏ qua confidence từ model)
    final_answer = llm_output
    
    try:
        cleaned = llm_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
            
        data = json.loads(cleaned)
        final_answer = data.get("answer", llm_output)
    except Exception as e:
        print(f"⚠️ Fail to parse JSON LLM output: {e}")
    
    # LUÔN dùng LLM-as-Judge để đánh giá confidence (không dùng self-assessment)
    print("📝 Answer generated, now evaluating with LLM-as-Judge...")
    confidence = _estimate_confidence(chunks, final_answer, policy_result, task)

    sources = list({c.get("source", "unknown") for c in chunks})

    return {
        "answer": final_answer,
        "sources": sources,
        "confidence": confidence,
    }


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "has_policy": bool(policy_result),
        },
        "output": None,
        "error": None,
    }

    try:
        result = synthesize(task, chunks, policy_result)
        state["final_answer"] = result["answer"]
        state["sources"] = result["sources"]
        state["confidence"] = result["confidence"]

        worker_io["output"] = {
            "answer_length": len(result["answer"]),
            "sources": result["sources"],
            "confidence": result["confidence"],
        }
        state["history"].append(
            f"[{WORKER_NAME}] answer generated, confidence={result['confidence']}, "
            f"sources={result['sources']}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"SYNTHESIS_ERROR: {e}"
        state["confidence"] = 0.0
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Synthesis Worker — Standalone Test")
    print("=" * 50)

    test_state = {
        "task": "SLA ticket P1 là bao lâu?",
        "retrieved_chunks": [
            {
                "text": "Ticket P1: Phản hồi ban đầu 15 phút kể từ khi ticket được tạo. Xử lý và khắc phục 4 giờ. Escalation: tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút.",
                "source": "sla_p1_2026.txt",
                "score": 0.92,
            }
        ],
        "policy_result": {},
    }

    result = run(test_state.copy())
    print(f"\nAnswer:\n{result['final_answer']}")
    print(f"\nSources: {result['sources']}")
    print(f"Confidence: {result['confidence']}")

    print("\n--- Test 2: Exception case ---")
    test_state2 = {
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì lỗi nhà sản xuất.",
        "retrieved_chunks": [
            {
                "text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền theo Điều 3 chính sách v4.",
                "source": "policy_refund_v4.txt",
                "score": 0.88,
            }
        ],
        "policy_result": {
            "policy_applies": False,
            "exceptions_found": [{"type": "flash_sale_exception", "rule": "Flash Sale không được hoàn tiền."}],
        },
    }
    result2 = run(test_state2.copy())
    print(f"\nAnswer:\n{result2['final_answer']}")
    print(f"Confidence: {result2['confidence']}")

    print("\n✅ synthesis_worker test done.")
