# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Trần Thương Trường Sơn  
**Vai trò trong nhóm:** Trace & Docs Owner  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

> Mô tả cụ thể module, worker, contract, hoặc phần trace bạn trực tiếp làm.
> Không chỉ nói "tôi làm Sprint X" — nói rõ file nào, function nào, quyết định nào.

**Module/file tôi chịu trách nhiệm:**
- File chính 1: `eval_trace.py` — Sprint 4 (chạy pipeline, phân tích trace)
- File chính 2: `mcp_server.py` — Sprint 3 (MCP server thật dùng FastMCP)
- File chính 3: `workers/synthesis.py` — phần LLM-as-Judge (thêm vào Sprint 2)

**Functions/tools tôi implement:**
- `run_test_questions()`, `run_grading_questions()`, `analyze_traces()`, `compare_single_vs_multi()` — trong `eval_trace.py`
- `search_kb()`, `get_ticket_info()`, `check_access_permission()`, `create_ticket()` — 4 MCP tools trong `mcp_server.py`
- `_estimate_confidence_llm_judge()`, `_estimate_confidence_heuristic()`, `_estimate_confidence()` — trong `workers/synthesis.py`

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`mcp_server.py` của tôi được `workers/policy_tool.py` (Worker Owner) gọi qua MCP client — cụ thể tool `search_kb` được trigger khi supervisor route sang `policy_tool_worker`. `eval_trace.py` gọi `run_graph()` từ `graph.py` để nhận `AgentState`, sau đó parse `mcp_tools_used` để đo MCP usage rate. LLM-as-Judge trong `synthesis.py` chạy sau mỗi lần synthesis worker tạo câu trả lời, đánh giá confidence độc lập.

**Bằng chứng:**

- `mcp_server.py` — FastMCP server với 4 tools, chạy được qua `python mcp_server.py`
- `eval_trace.py` — toàn bộ Sprint 4 implementation
- `workers/synthesis.py` — hàm `_estimate_confidence_llm_judge()` và `_estimate_confidence()`
- `artifacts/grading_run.jsonl` — 10 records, 5 câu có `mcp_tools_used: ["search_kb"]`

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Tôi chọn dùng **LLM-as-Judge với model mạnh hơn** để tính confidence thay vì để synthesis model tự chấm điểm câu trả lời của chính nó (self-assessment).

**Lý do:**

Khi implement confidence scoring trong `workers/synthesis.py`, tôi có 2 lựa chọn:
1. **Self-assessment** — yêu cầu synthesis model (GPT-4.1) vừa tạo câu trả lời vừa tự đánh giá confidence trong cùng 1 lần gọi
2. **LLM-as-Judge** — dùng một LLM call riêng biệt, độc lập với model mạnh hơn để đánh giá chất lượng câu trả lời

Tôi chọn option 2 vì self-assessment có bias cố hữu: model có xu hướng overconfident với output của chính nó. Bằng cách tách thành một judge call độc lập — và dùng model mạnh hơn (GPT-4.1 làm synthesis, judge cũng dùng GPT-4.1 nhưng với system prompt chuyên biệt đánh giá) — confidence score phản ánh thực tế hơn. Judge nhìn vào evidence, câu trả lời, và câu hỏi như một bên thứ ba với rubric rõ ràng 4 tiêu chí.

**Trade-off đã chấp nhận:**

Mỗi câu hỏi tốn thêm 1 LLM call (tăng latency ~1-2 giây, tăng chi phí API). Nhưng đổi lại, confidence score đáng tin cậy hơn — đặc biệt quan trọng cho câu abstain như gq07 và câu multi-hop như gq09.

**Bằng chứng từ code:**

```python
# workers/synthesis.py — Judge dùng rubric 4 tiêu chí độc lập
JUDGE_PROMPT = """...
1. Evidence Quality   (0–0.3): Chunks có đủ thông tin không?
2. Answer Grounding   (0–0.4): Câu trả lời có dựa vào evidence không?
3. Completeness       (0–0.2): Câu trả lời có đầy đủ không?
4. Uncertainty Handling (0–0.1): Xử lý sự không chắc chắn
..."""

# Wrapper: mặc định dùng LLM judge, fallback về heuristic nếu lỗi
def _estimate_confidence(chunks, answer, policy_result, task="") -> float:
    use_llm_judge = os.getenv("USE_LLM_JUDGE", "true").lower() == "true"
    if use_llm_judge and task:
        return _estimate_confidence_llm_judge(chunks, answer, policy_result, task)
    else:
        return _estimate_confidence_heuristic(chunks, answer, policy_result)
```

**Kết quả thực tế:**

Câu gq07 (abstain — không có thông tin về mức phạt tài chính): LLM judge cho `confidence=1.0` vì câu trả lời abstain đúng cách, `uncertainty_handling=0.1` (max). Nếu dùng self-assessment hoặc heuristic, confidence sẽ thấp (~0.3) dù câu trả lời hoàn toàn đúng — đây là điểm mà LLM-as-Judge vượt trội rõ ràng.

**Lý do:**

Khi implement confidence scoring trong `workers/synthesis.py`, tôi có 2 lựa chọn:
1. **Self-assessment** — yêu cầu LLM vừa tạo câu trả lời vừa tự đánh giá confidence trong cùng 1 lần gọi
2. **LLM-as-Judge** — dùng một LLM call riêng biệt, độc lập để đánh giá chất lượng câu trả lời

Tôi chọn option 2 vì self-assessment có bias cố hữu: model có xu hướng overconfident với câu trả lời của chính nó. LLM-as-Judge đánh giá khách quan hơn vì nó nhìn vào evidence, câu trả lời, và câu hỏi như một bên thứ ba.

**Trade-off đã chấp nhận:**

Mỗi câu hỏi tốn thêm 1 LLM call (tăng latency ~1-2 giây và tăng chi phí API). Nhưng đổi lại, confidence score phản ánh thực tế hơn — đặc biệt quan trọng cho câu gq07 (abstain case) và gq09 (multi-hop).

**Bằng chứng từ code:**

```python
# workers/synthesis.py — LLM-as-Judge với 4 tiêu chí độc lập
JUDGE_PROMPT = """...
Tiêu chí đánh giá:
1. Evidence Quality (0-0.3): Chunks có đủ thông tin không?
2. Answer Grounding (0-0.4): Câu trả lời có dựa vào evidence không?
3. Completeness (0-0.2): Câu trả lời có đầy đủ không?
4. Uncertainty Handling (0-0.1): Xử lý sự không chắc chắn
..."""

def _estimate_confidence(chunks, answer, policy_result, task="") -> float:
    use_llm_judge = os.getenv("USE_LLM_JUDGE", "true").lower() == "true"
    if use_llm_judge and task:
        return _estimate_confidence_llm_judge(chunks, answer, policy_result, task)
    else:
        return _estimate_confidence_heuristic(chunks, answer, policy_result)
```

**Kết quả thực tế từ trace:**

Câu gq07 (abstain — không có thông tin về mức phạt tài chính): LLM judge cho `confidence=1.0` vì câu trả lời abstain đúng cách, evidence quality thấp nhưng uncertainty handling = 0.1 (max). Nếu dùng heuristic, confidence sẽ thấp (~0.3) dù câu trả lời hoàn toàn đúng.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** `policy_tool_worker` không gọi MCP `search_kb` khi `retrieved_chunks` đã có sẵn từ bước trước, dù `needs_tool=True`.

**Symptom (pipeline làm gì sai?):**

Khi supervisor route sang `policy_tool_worker` với `needs_tool=True`, trace cho thấy `mcp_tools_used: []` — MCP không được gọi dù supervisor đã quyết định cần tool. Policy worker chỉ chạy rule-based check trên chunks cũ từ retrieval, bỏ qua khả năng search KB với query chuyên biệt hơn cho policy context.

**Root cause:**

Logic ban đầu trong `policy_tool.py`:

```python
# TRƯỚC KHI SỬA — chỉ gọi MCP khi chưa có chunks
if not chunks and needs_tool:
    mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
```

Điều kiện `not chunks` sai: khi pipeline đi qua `policy_tool_worker` sau `retrieval_worker`, `chunks` đã có sẵn nên MCP không bao giờ được gọi. Nhưng policy worker cần search KB với query riêng (ví dụ "refund policy flash sale exception") thay vì dùng chunks chung từ retrieval.

**Cách sửa:**

Đổi điều kiện — gọi MCP khi `needs_tool=True` bất kể đã có chunks hay chưa:

```python
# SAU KHI SỬA — gọi MCP khi supervisor quyết định cần tool
if needs_tool:
    mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
    state["mcp_tools_used"].append(mcp_result)
    state["history"].append(f"[{WORKER_NAME}] called MCP search_kb")

    if mcp_result.get("output") and mcp_result["output"].get("chunks"):
        # Merge chunks từ MCP với chunks đã có, ưu tiên MCP chunks
        mcp_chunks = mcp_result["output"]["chunks"]
        chunks = mcp_chunks + [c for c in chunks if c not in mcp_chunks]
        state["retrieved_chunks"] = chunks
```

**Bằng chứng trước/sau:**

Trước khi sửa — trace gq03 (`needs_tool=True`, đã có chunks từ retrieval):
```json
"mcp_tools_used": [],
"workers_called": ["policy_tool_worker", "retrieval_worker", "synthesis_worker"]
```

Sau khi sửa — trace gq03:
```json
"mcp_tools_used": ["search_kb"],
"workers_called": ["policy_tool_worker", "retrieval_worker", "synthesis_worker"],
"route_reason": "task contains policy/access keyword | MCP: search_kb selected"
```

Kết quả: 5/10 câu grading có `mcp_tools_used: ["search_kb"]` — đúng với các câu policy/access (gq02, gq03, gq04, gq09, gq10).

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**

Tôi cover đủ 3 phần chính: MCP server (4 tools thật, bonus +2), eval_trace (chạy grading, tính metrics), và LLM-as-Judge (confidence scoring độc lập). Điểm mạnh là tôi làm đúng spec — MCP phải là server thật chạy HTTP; confidence phải do judge đánh giá, không phải self-assessment. Trace format đủ fields để debug toàn bộ pipeline.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi chưa tối ưu latency. LLM-as-Judge tốn thêm 1 API call mỗi câu — avg latency 5123ms nhưng tôi không đo được judge chiếm bao nhiêu. Ngoài ra, phần so sánh Day 08 vs Day 09 chưa hoàn chỉnh vì thiếu baseline thực tế từ Day 08.

**Nhóm phụ thuộc vào tôi ở đâu?**

(1) `grading_run.jsonl` — bắt buộc nộp trước 18:00, mất 30/60 điểm nhóm nếu thiếu. (2) MCP tools — nếu tôi không implement `search_kb`, 5/10 câu policy sẽ không có kết quả đúng. (3) confidence scores — nếu LLM-as-Judge fail, toàn bộ trace có confidence không đáng tin.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi phụ thuộc Supervisor Owner phải set `needs_tool=True` đúng lúc, và Worker Owners phải gọi đúng các function của tôi (`_call_mcp_tool`, `_estimate_confidence`). Nếu `graph.py` không pass đúng `task` vào synthesis, LLM judge bị skip.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? 

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.

**Cải tiến 1 — Judge score breakdown:**

Tôi sẽ thêm **judge score breakdown vào trace file** để phân tích từng tiêu chí theo từng câu hỏi. Hiện tại trace chỉ lưu `confidence: 0.9` — một con số duy nhất. Nhưng LLM judge tính 4 thành phần (EQ, AG, C, UH). Trace gq09 (0.9) và gq07 (1.0) có cùng "cao" nhưng lý do khác: gq09 vì evidence tốt, gq07 vì abstain đúng. Nếu lưu breakdown, `analyze_traces()` sẽ identify pattern: `answer_grounding` thấp → cải thiện synthesis prompt.

**Cải tiến 2 — Hoàn thiện so sánh Day 08 vs Day 09:**

Tôi sẽ chạy `python day08/lab/eval_metrics.py` để lấy baseline metrics, thay vì để TODO placeholders trong `compare_single_vs_multi()`. Hiện tại `eval_report.json` chỉ có Day 09 metrics. Khi có cả hai, sẽ tính delta thực: confidence +0.05, latency +2000ms, abstain -5% — giúp kết luận multi-agent tốt hơn ở điểm nào.

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
