# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Bùi Lâm Tiến
**Vai trò trong nhóm:** Worker Owner / Documentation Owner
**Ngày nộp:** 14/04/2026
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
>
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

- File chính: `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py` và `contracts/worker_contracts.yaml`. Bên cạnh đó tôi cũng tổng hợp báo cáo ở file `docs/routing_decisions.md`.
- Functions tôi implement: Thêm các edge cases trong `workers/policy_tool.py`.

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Vai trò Worker Owner của tôi là hạt nhân xử lý của hệ thống. Khi file `graph.py` của bạn làm chức năng Supervisor quyết định hướng giải quyết dựa trên câu hỏi, luồng xử lý sẽ đến với các Worker của tôi. Dựa trên State, mỗi Worker sẽ hoặc là tra cứu database, hoặc gọi API mcp tool, cuối cùng tập kết tại `synthesis_worker`. Tại đó tôi dùng LLM format câu trả lời với các nguồn dữ kiện (evidence) chính xác nhất, sau đó trả về output pipeline để hoàn thành luồng request.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
Các logic này đều nằm trong folder `workers/`. Việc phân tải contract (I/O) được tôi setup trong file `contracts/worker_contracts.yaml`. Tương tự, tôi đã phân tích các file traces `artifacts/traces/` (kết quả sau khi nối sprint 1,2,3 và chạy eval ở sprint 4 trước khi có thay đổi cho phần grading_questions) để hoàn thiện file `docs/routing_decisions.md`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
>
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Nâng cấp LLM tổng hợp trong `synthesis_worker` từ `gpt-4o-mini` lên `gpt-4.1`.

**Lý do:**
Ban đầu tôi thử tận dụng model `gpt-4o-mini` cho nhẹ và tiết kiệm, đồng thời sử dụng hàm `_estimate_confidence()` có sẵn để tự động cộng trừ điểm lấy từ `list chunks` của db. Nhưng khi chạy với `test_questions`, gặp mấy câu phức tạp đòi hỏi nối chuỗi kiến thức thì model lại trả lời sai nhiều. Việc dùng thuật toán kéo điểm bằng quy tắc cứng cũng không hề chính xác với thực tế độ tin cậy của câu trả lời. Cuối cùng, tôi quyết định mạnh dạn đổi sang model xịn hơn (`gpt-4.1`) để câu trả lời bám sát context tốt hơn.

**Trade-off đã chấp nhận:**
Việc gọi `gpt-4.1` mang lại một đánh đổi lớn: thời gian chờ (latency) tăng lên nhiều, đồng thời mỗi lần gọi tốn nhiều token hơn so với trước đó. Nhưng vì hệ thống RAG CSKH bắt buộc phải đưa ra câu trả lời chuẩn, nên tôi chấp nhận chạy chậm và tốn kém một chút để đổi lấy kết quả tốt hơn, tránh việc hallucination.

**Bằng chứng từ trace/code:**

```python
        # Trong file `synthesis.py`, tôi đã nâng cấu hình tham số khởi tạo chat:
        response = client.chat.completions.create(
            model="gpt-4.1",  # Thay thế cho model gpt-4o-mini
            messages=messages,
            temperature=0.1,  
            max_tokens=500,
        )
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** Avg Confidence của Model chỉ đạt tối đa 0.5

**Symptom (pipeline làm gì sai?):**

Sử dụng mô hình gpt-4o-mini khiến cho kết quả không tốt.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Mô hình yếu khi có đủ dữ liệu lại không tự tin trả lời.

**Cách sửa:**

Thay đổi mô hình từ gpt-4o-mini sang gpt-4.1.

**Bằng chứng trước/sau:**
> Dán trace/log/output trước khi sửa và sau khi sửa.

Avg Confidence tăng từ 0.5 lên 0.75.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**
Các phần trong sprint 2 phần lớn đã có sẵn, chỉ khi chạy eval mới thấy được kết quả hoạt động của các worker. Tôi cảm thấy đúng đẵn khi đã sử dụng mô hình tốt hơn để cải thiện kết quả tổng hợp câu trả lời.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Tôi chưa thực sự tối ưu được phần `policy_tool_worker` vì vẫn còn dùng rule-based để check policy. Điều này dẫn đến việc tốn thời gian debug và khó scale khi có nhiều policy.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_
Nếu tôi chưa làm xong `synthesis_worker`, mô hình sẽ đứt gãy luồng thông tin vì đây là bước chốt chặn sinh câu trả lời trước khi gửi ra đầu ra (END node của Graph). Cả luồng pipeline sẽ bị block nếu worker không chạy được.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_
Tôi phụ thuộc rất lớn vào người làm Supervisor (Sprint 1) truyền đúng `route_reason` và state hợp lệ cũng như bạn làm MCP (Sprint 3) hỗ trợ các tools tương tác qua cổng `search_kb`.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> _"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."_

Tôi sẽ thử **áp dụng luồng thực thi song song** cho các câu phân nhánh phức tạp. Cụ thể, vì trace của câu `gq09` cho thấy hệ thống tốn time trễ lớn do phải chạy tuần tự qua nhiều check (từ MCP lấy `ticket_info` sang `search_kb` rồi xuống Policy). Nếu biến `policy_tool_worker` xử lý dạng Async song song, tôi có thể tối ưu response latency vốn đang khá cao.

Ngoài ra tôi cũng sẽ cùng nhóm làm lại phần `eval.py` ở day08 để có ít nhất 2 metrics so sánh với `eval_trace` ở day09 trên test_questions.json. Đây là 1 phần mà nhóm tôi vẫn chưa thực hiện xong.

--
