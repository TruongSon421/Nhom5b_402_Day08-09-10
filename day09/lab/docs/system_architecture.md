# System Architecture — Lab Day 09

**Nhóm:** Nhóm 5b  
**Ngày:** 14-04-2026  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

> Mô tả ngắn hệ thống của nhóm: chọn pattern gì, gồm những thành phần nào.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**

Hệ thống sử dụng Supervisor-Worker pattern để tách biệt trách nhiệm routing logic (Supervisor) và domain expertise (Workers). Pattern này giúp:
- **Dễ debug**: Mỗi worker có thể test độc lập với input/output rõ ràng
- **Dễ mở rộng**: Thêm worker mới hoặc MCP tool không ảnh hưởng toàn hệ thống
- **Traceability**: Mỗi bước routing được ghi lại với route_reason cụ thể
- **Separation of concerns**: Supervisor không cần biết domain knowledge, workers không cần biết routing logic

---

## 2. Sơ đồ Pipeline

> Vẽ sơ đồ pipeline dưới dạng text, Mermaid diagram, hoặc ASCII art.
> Yêu cầu tối thiểu: thể hiện rõ luồng từ input → supervisor → workers → output.

**Ví dụ (ASCII art):**
```
User Request
     │
     ▼
┌──────────────┐
│  Supervisor  │  ← route_reason, risk_high, needs_tool
└──────┬───────┘
       │
   [route_decision]
       │
  ┌────┴────────────────────┐
  │                         │
  ▼                         ▼
Retrieval Worker     Policy Tool Worker
  (evidence)           (policy check + MCP)
  │                         │
  └─────────┬───────────────┘
            │
            ▼
      Synthesis Worker
        (answer + cite)
            │
            ▼
         Output
```

**Sơ đồ thực tế của nhóm:**

```
User Request (task)
     │
     ▼
┌──────────────────────────────────────┐
│  Supervisor Node                     │
│  - Phân tích task keywords           │
│  - Quyết định route                  │
│  - Set risk_high, needs_tool flags   │
└──────┬───────────────────────────────┘
       │
   [route_decision]
       │
  ┌────┴────────────────────────────────┐
  │                                     │
  ▼                                     ▼
┌─────────────────┐         ┌──────────────────────┐
│ Retrieval Worker│         │ Policy Tool Worker   │
│ - ChromaDB query│         │ - Policy analysis    │
│ - Top-k chunks  │         │ - Exception detection│
│ - Cosine sim    │         │ - MCP tool calls     │
└────────┬────────┘         └──────────┬───────────┘
         │                             │
         │    ┌────────────────────────┘
         │    │ (if no chunks yet)
         │    ▼
         │  ┌─────────────────┐
         └─→│ Retrieval Worker│
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │ Synthesis Worker│
            │ - LLM call      │
            │ - Grounded      │
            │ - Citation      │
            │ - Confidence    │
            └────────┬────────┘
                     │
                     ▼
              Final Answer
              (answer + sources + confidence)

Note: Human Review node exists but auto-approves in lab mode
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích task keywords và quyết định route sang worker phù hợp. Không tự trả lời domain questions. |
| **Input** | task (string) - câu hỏi từ user |
| **Output** | supervisor_route, route_reason, risk_high, needs_tool |
| **Routing logic** | Priority 1: Policy keywords (hoàn tiền, refund, flash sale, cấp quyền, access) → policy_tool_worker<br>Priority 2: Retrieval keywords (P1, SLA, ticket, escalation) → retrieval_worker<br>Risk assessment: emergency, khẩn cấp, 2am, err- → set risk_high=True<br>Override: unknown error + high risk → human_review |
| **HITL condition** | risk_high=True AND task contains "err-" (unknown error code) |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Dense retrieval từ ChromaDB, trả về top-k chunks có relevance score cao nhất |
| **Embedding model** | OpenAI text-embedding-3-small (primary), fallback to random embeddings for testing |
| **Top-k** | 3 (default, configurable via state["retrieval_top_k"]) |
| **Stateless?** | Yes - không đọc/ghi state ngoài input/output được khai báo |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích policy rules, detect exceptions, gọi MCP tools khi needs_tool=True |
| **MCP tools gọi** | search_kb (nếu chưa có chunks), get_ticket_info (nếu task chứa ticket/P1/jira keywords) |
| **Exception cases xử lý** | Flash Sale exception, Digital product exception (license key/subscription), Activated product exception, Temporal scoping (policy v3 vs v4 based on order date) |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | OpenAI gpt-4o-mini (primary), Google Gemini 1.5 Flash (fallback) |
| **Temperature** | 0.1 (low temperature for grounded generation) |
| **Grounding strategy** | Context built from retrieved_chunks + policy_result exceptions. System prompt enforces "Answer only from context". JSON output format with answer + confidence. |
| **Abstain condition** | retrieved_chunks=[] → return "Không đủ thông tin trong tài liệu nội bộ", confidence < 0.4 |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | query (str), top_k (int, default=3) | chunks (array), sources (array), total_found (int) |
| get_ticket_info | ticket_id (str, e.g. "P1-LATEST") | ticket_id, priority, status, assignee, created_at, sla_deadline, escalated, notifications_sent |
| check_access_permission | access_level (int: 1/2/3), requester_role (str), is_emergency (bool) | can_grant, required_approvers, emergency_override, notes, source |
| create_ticket | priority (str: P1/P2/P3/P4), title (str), description (str) | ticket_id, url, created_at, status, note (MOCK) |

---

## 4. Shared State Schema

> Liệt kê các fields trong AgentState và ý nghĩa của từng field.

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào từ user | supervisor đọc, initial state ghi |
| supervisor_route | str | Worker được chọn (retrieval_worker/policy_tool_worker/human_review) | supervisor ghi, route_decision đọc |
| route_reason | str | Lý do cụ thể tại sao chọn route này | supervisor ghi, trace đọc |
| risk_high | bool | True nếu task có risk keywords (emergency, khẩn cấp, 2am, err-) | supervisor ghi |
| needs_tool | bool | True nếu cần gọi MCP tools | supervisor ghi, policy_tool đọc |
| hitl_triggered | bool | True nếu đã pause cho human review | human_review ghi |
| retrieved_chunks | list | Evidence chunks từ retrieval (text, source, score, metadata) | retrieval ghi, policy_tool/synthesis đọc |
| retrieved_sources | list | Unique list of source filenames | retrieval ghi, synthesis đọc |
| policy_result | dict | Kết quả kiểm tra policy (policy_applies, exceptions_found, policy_name) | policy_tool ghi, synthesis đọc |
| mcp_tools_used | list | Danh sách MCP tool calls (tool, input, output, error, timestamp) | policy_tool ghi, trace đọc |
| final_answer | str | Câu trả lời cuối có citation | synthesis ghi |
| sources | list | Sources được cite trong answer | synthesis ghi |
| confidence | float | Mức tin cậy 0.0-1.0 | synthesis ghi |
| history | list | Lịch sử các bước đã qua (log messages) | tất cả workers append |
| workers_called | list | Danh sách workers đã được gọi | tất cả workers append |
| worker_io_logs | list | Log input/output của từng worker (theo contract) | tất cả workers append |
| latency_ms | int | Thời gian xử lý (ms) | graph.run_graph() ghi |
| run_id | str | ID của run này (format: run_YYYYMMDD_HHMMSS_microsec) | initial state ghi |
| timestamp | str | ISO timestamp khi hoàn thành | graph.run_graph() ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — không rõ lỗi ở đâu trong monolith pipeline | Dễ hơn — test từng worker độc lập với input/output rõ ràng |
| Thêm capability mới | Phải sửa toàn prompt và logic | Thêm worker/MCP tool riêng, không ảnh hưởng code cũ |
| Routing visibility | Không có — black box | Có route_reason trong trace, dễ audit |
| Separation of concerns | Một agent làm tất cả (retrieve + policy + synthesis) | Supervisor giữ routing logic, workers giữ domain expertise |
| Testability | Phải test end-to-end | Mỗi worker test độc lập (unit test friendly) |
| Scalability | Khó scale — thêm logic làm prompt phình to | Dễ scale — thêm worker song song, supervisor route |
| Error handling | Lỗi ở đâu không rõ | worker_io_logs ghi rõ worker nào fail, input/output gì |
| MCP integration | Khó — phải hard-code tool calls trong prompt | Dễ — policy_tool worker gọi MCP, supervisor không cần biết |

**Nhóm điền thêm quan sát từ thực tế lab:**

Trong thực tế lab, nhận thấy rằng:
- **Trace quality**: Day 09 trace có đầy đủ routing decisions, worker I/O logs, MCP tool calls → dễ debug hơn nhiều so với Day 08 chỉ có input/output cuối
- **Exception handling**: Policy exceptions (Flash Sale, digital product) được xử lý rõ ràng trong policy_tool worker, không bị "chôn vùi" trong một prompt lớn
- **Confidence estimation**: Synthesis worker có thể tính confidence dựa vào chunk scores và exception penalties, trong khi Day 08 khó ước lượng
- **HITL integration**: Human review node có thể trigger dựa vào risk_high flag, Day 08 không có cơ chế này
- **Development velocity**: Sau khi setup xong graph structure, thêm worker mới hoặc MCP tool mới rất nhanh (< 30 phút), không cần refactor toàn hệ thống

---

## 6. Giới hạn và điểm cần cải tiến

> Nhóm mô tả những điểm hạn chế của kiến trúc hiện tại.

1. **Routing logic rule-based**: Supervisor hiện dùng keyword matching đơn giản. Với task phức tạp hoặc ambiguous, có thể route sai. Cải tiến: dùng LLM-based routing với few-shot examples.

2. **Policy analysis không dùng LLM**: Policy tool worker hiện dùng rule-based exception detection. Với policy phức tạp hơn (e.g., nested conditions, temporal logic), cần LLM để phân tích. Cải tiến: gọi LLM với policy context để extract rules.

3. **MCP server mock mode**: Hiện tại mặc định dùng mock data, không kết nối hệ thống thật (Jira, Access Control). Cải tiến: integrate với real APIs khi deploy production.

4. **Confidence estimation heuristic**: Synthesis worker tính confidence dựa vào chunk scores và exception count, chưa chính xác. Cải tiến: dùng LLM-as-Judge để đánh giá confidence dựa vào answer quality.

5. **HITL chỉ là placeholder**: Human review node hiện auto-approve, chưa có UI hoặc interrupt mechanism thật. Cải tiến: integrate với LangGraph interrupt_before hoặc external approval system.

6. **Không có retry logic**: Nếu worker fail (e.g., ChromaDB timeout, LLM API error), pipeline dừng ngay. Cải tiến: thêm retry với exponential backoff, hoặc fallback sang worker khác.

7. **Không có caching**: Mỗi query đều gọi embedding + ChromaDB + LLM mới. Với query giống nhau, lãng phí. Cải tiến: cache retrieved_chunks và final_answer theo query hash.

8. **Trace không có visualization**: Trace file là JSON, khó đọc. Cải tiến: build trace viewer UI (e.g., LangSmith, Phoenix) để visualize routing flow và worker I/O.
