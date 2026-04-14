# Routing Decisions Log — Lab Day 09

**Nhóm:** 5b-E402  
**Ngày:** 14/4/2026

> **Hướng dẫn:** Ghi lại ít nhất **3 quyết định routing** thực tế từ trace của nhóm.
> Không ghi giả định — phải từ trace thật (`artifacts/traces/`).
> 
> Mỗi entry phải có: task đầu vào → worker được chọn → route_reason → kết quả thực tế.

---

## Routing Decision #1

**Task đầu vào:**
> Ticket P1 được tạo lúc 22:47. Đúng theo SLA, ai nhận thông báo đầu tiên và qua kênh nào? Deadline escalation là mấy giờ? (gq01)

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `task contains SLA/ticket keyword | MCP: not needed`  
**MCP tools được gọi:** Không có  
**Workers called sequence:** `["retrieval_worker", "synthesis_worker"]`

**Kết quả thực tế:**
- final_answer (ngắn): On-call engineer là người nhận thông báo đầu tiên. Deadline escalation là 22:57 (sau 10 phút).
- confidence: `1.0`
- Correct routing? Yes

**Nhận xét:** 
Ở câu này, hệ thống bắt được mấy từ khóa như "SLA", "ticket" nên đẩy luôn vào `retrieval_worker` để lục tìm trong mấy file định dạng tài liệu thường. Do chỉ tra cứu thông tin tĩnh chứ không cần chạy tool động nên luồng này đi đúng và lấy được 100% confidence ngon ơ.

---

## Routing Decision #2

**Task đầu vào:**
> Khách hàng đặt đơn ngày 31/01/2026 và gửi yêu cầu hoàn tiền ngày 07/02/2026 vì lỗi nhà sản xuất... Chính sách nào áp dụng và có được hoàn tiền không? (gq02)

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/access keyword | MCP: search_kb selected`  
**MCP tools được gọi:** `["search_kb"]`  
**Workers called sequence:** `["policy_tool_worker", "synthesis_worker"]`

**Kết quả thực tế:**
- final_answer (ngắn): Không đủ thông tin do tài liệu hiện tại không chứa nội dung chính sách v3...
- confidence: `0.3`
- Correct routing? Yes

**Nhận xét:**
Quyết định này của hệ thống hoạt động khá xịn. Câu hỏi xuất hiện từ "chính sách" với "hoàn tiền", nhờ vậy supervisor nhận ra ngay và chia qua luồng policy, lôi kèm thêm tool `search_kb`. Kết quả là nó soi ra được rule ngoại lệ bắt lấn cấn về ngày tháng, biết là tài liệu (v3) bị thiếu nên thẳng tay hạ điểm tự tin (confidence) xuống mức 0.3 và báo ngay "Không đủ thông tin", cực kỳ thực tế luôn.

---

## Routing Decision #3

**Task đầu vào:**
> Sự cố P1 xảy ra lúc 2am. Đồng thời cần cấp Level 2 access tạm thời cho contractor để thực hiện emergency fix. Hãy nêu đầy đủ các bước... (gq09)

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/access keyword | MCP: search_kb selected | risk_high flagged`  
**MCP tools được gọi:** `["search_kb", "get_ticket_info"]`  
**Workers called sequence:** `["policy_tool_worker", "synthesis_worker"]`

**Kết quả thực tế:**
- final_answer (ngắn): Đưa ra 3 bước báo SLA và 2 điều kiện duyệt cấp quyền khẩn cấp.
- confidence: `0.85`
- Correct routing? Yes

**Nhận xét:**
Đây là một case thực sự khó vì nội dung hòa trộn giữa quy trình P1 chung chung với quy trình cấp đặc quyền truy cập (Access). May mà hệ thống bắt theo tag rủi ro "Access/Level 2", quất luôn cờ risk_high để găm vào policy_tool_worker. Nó xài song song tới 2 tính năng MCP mới lấy ra rành mạch được dữ kiện. Mô hình đa tác tử (multi-agent) rẽ sóng vụ này là chuẩn bài.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Task đầu vào:**
> ERR-403-AUTH là lỗi gì và cách xử lý? (q09)

**Worker được chọn:** `human_review` (chặn ngang)  
**Route reason (từ trace):** `unknown error code + risk_high → human review`  
**MCP tools được gọi:** N/A  
**Workers called sequence:** `["human_review"]`

**Kết quả thực tế:**
- final_answer (ngắn): Gửi qua màn hình HITL (Human-in-the-loop)
- confidence: `N/A`
- Correct routing? Yes

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**
Bởi lẽ đây là một mã lỗi lạ hoắc chả ai biết. Thông thường RAG gặp case này sẽ chế đại một câu trả lời linh tinh (hallucination), nhưng supervisor trong pipeline đợt này đã đánh hơi được tính chất rủi ro của mã lỗi và nổ luôn cờ HITL để vỗ vai kỹ sư con người (gọi tụi mình) vào review bằng tay. Viết thế này bảo vệ cho RAG chuẩn và an toàn hơn hẳn.

---

## Tổng kết

### Routing Distribution

*(Note: Data từ chu kỳ chạy 15 câu test chuẩn của nhóm)*

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 8 | 53% |
| policy_tool_worker | 7 | 46% |

### Routing Accuracy

> Trong số 15 câu nhóm đã chạy, bao nhiêu câu supervisor route đúng?

- Câu route đúng: 15 / 15
- Câu route sai (đã sửa bằng cách nào?): 0
- Câu trigger HITL: 1 (Câu q09 về cái mã lạ `ERR-403-AUTH`)

### Lesson Learned về Routing

> Quyết định kỹ thuật quan trọng nhất nhóm đưa ra về routing logic là gì?  

1. **Phối hợp bắt Keyword tĩnh với Đánh giá rủi ro động**: Đầu tiên xài keyword chặn sẵn ("SLA", "ticket" đi riêng, "policy", "access" đi riêng) làm tốc độ phân giải nhanh gọn lẹ. Nhưng cục lõi ngon nhất lại là chêm thêm bước evaluate mức độ risk để né mấy code unknown bằng cách tạo lối nhảy qua HITL.
2. **Kích hoạt Tool phụ trợ theo tư duy hoàn cảnh**: Router giỏi là router biết lúc nào kho dữ liệu kín của LLM hết hơi. Nếu thấy câu hỏi phải chọc sâu vào thông tin ngoài hệ thống, supervisor sẽ kéo công cụ dạng MCP vào hỗ trợ liền.

### Route Reason Quality

> Nhìn lại các `route_reason` trong trace — chúng có đủ thông tin để debug không?  
> Nếu chưa, nhóm sẽ cải tiến format route_reason thế nào?

Nhìn vào chuỗi text `task contains policy/access keyword | MCP: ...` hiện tại cũng khá rõ nghĩa và tiện xem qua terminal. Nhưng nếu để chuyên nghiệp và vững chắc hơn, tụi mình định đóng gói nó dưới dạng thuần JSON luôn (kiểu `{ "keywords_matched": [...], "risk_level": "high", "mcp_called": true }`), xong móc thẳng vào một script parse log nào đấy để lọc dữ kiện cho lẹ, khỏi split chuỗi string cực thân.
