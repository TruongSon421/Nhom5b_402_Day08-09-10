# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Trương Đăng Nghĩa  
**Vai trò:** Sprint 3 (Inject Corruption & Eval) + Sprint 4 (Quality report, Pipeline architecture và Group report)  
**Nhóm:** Nhóm 5B — Lớp 402  
**Ngày nộp:** 2026-04-15  
**Độ dài:** ~500 từ

---

## 1. Tôi phụ trách phần nào?

Trong Sprint 3, tôi chịu trách nhiệm chạy kịch bản inject corruption để tạo bằng chứng before/after cho quality report. Cụ thể là chạy pipeline với flag `--no-refund-fix --skip-validate` để cố ý embed dữ liệu stale vào Chroma, sau đó dùng `eval_retrieval.py` để so sánh kết quả retrieval trước và sau khi fix.

Kết quả tôi tạo ra 2 file CSV:
- `artifacts/eval/after_inject_bad.csv` (run_id: inject-bad) - khi data bị ô nhiễm
- `artifacts/eval/before_after_eval_clean.csv` (run_id: sprint3-clean) - sau khi chạy pipeline chuẩn

Điểm quan trọng là câu hỏi `q_refund_window` cho thấy sự khác biệt rõ rệt: `hits_forbidden=yes` khi inject vs `hits_forbidden=no` sau khi fix.

Sang Sprint 4, tôi viết 3 file documentation:
- `docs/quality_report.md` - tổng hợp số liệu, before/after, freshness check
- `docs/pipeline_architecture.md` - sơ đồ luồng, idempotency strategy, liên hệ Day 09
- `reports/group_report.md` - báo cáo tổng thể của nhóm

Tôi làm việc với Trần Thượng Trường Sơn để lấy danh sách 9 cleaning rules và 8 expectations cho quality report, và với Bùi Lâm Tiến để hiểu rõ cách idempotent embed hoạt động (upsert + prune).

---

## 2. Một quyết định kỹ thuật

Khi làm Sprint 3, tôi phải quyết định giữa 2 cách lưu kết quả eval: dùng 2 file CSV riêng hay 1 file có cột `scenario`. README gợi ý cả 2 cách đều được.

Tôi chọn dùng 2 files riêng vì lý do đơn giản: mỗi file tương ứng với 1 run_id cụ thể, dễ trace lineage. Khi nhìn vào file name `after_inject_bad.csv`, tôi biết ngay nó từ run_id `inject-bad`, có thể tìm manifest tương ứng ở `artifacts/manifests/manifest_inject-bad.json` và log ở `artifacts/logs/run_inject-bad.log`.

Nếu dùng 1 file với cột `scenario`, tôi sẽ phải merge 2 CSV thủ công và thêm cột mới. Điều này không chỉ phức tạp hơn mà còn mất đi khả năng trace - không biết dòng nào từ run nào. Hơn nữa, `eval_retrieval.py` đã output 1 file/run sẵn rồi, không cần modify code.

Cách làm này cũng giúp reproducible: nếu cần rerun scenario nào, chỉ cần chạy lại pipeline với run_id tương ứng.

---

## 3. Một lỗi hoặc anomaly đã xử lý

Khi chạy xong inject-bad và eval, tôi thấy một điều lạ: câu hỏi `q_refund_window` có `contains_expected=yes` (nghĩa là có "7 ngày" trong kết quả) nhưng lại có `hits_forbidden=yes` (nghĩa là cũng có "14 ngày" - forbidden term).

Lúc đầu tôi nghĩ có thể eval bị lỗi, nhưng khi đọc kỹ log `run_inject-bad.log`, tôi thấy dòng:
```
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1
WARN: expectation failed but --skip-validate → tiếp tục embed
```

Ah, đúng rồi! Flag `--no-refund-fix` đã bỏ qua cleaning rule fix "14 ngày → 7 ngày", và flag `--skip-validate` đã bypass expectation halt. Kết quả là chunk stale "14 ngày làm việc" vẫn được embed vào Chroma, làm ô nhiễm vector store.

Để fix, tôi chạy lại pipeline chuẩn (không có 2 flags đó) với run_id `sprint3-clean`. Lần này expectation pass, cleaning rule hoạt động đúng, và quan trọng là log có dòng `embed_prune_removed=1` - chứng tỏ prune đã xóa vector cũ.

Chạy eval lại, `q_refund_window` giờ có `hits_forbidden=no`. Vector store đã sạch.

---

## 4. Bằng chứng trước / sau

**Câu hỏi:** `q_refund_window` — "Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền?"

**Trước (inject-bad):**
```
q_refund_window,Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn?,policy_refund_v4,Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.,yes,yes,,3
```
Chú ý: `contains_expected=yes` (có "7 ngày") nhưng `hits_forbidden=yes` (cũng có "14 ngày")

**Sau (sprint3-clean):**
```
q_refund_window,Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn?,policy_refund_v4,Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.,yes,no,,3
```
Giờ `hits_forbidden=no` - chỉ còn "7 ngày" đúng

Sự khác biệt này rất quan trọng vì nó chứng minh data quality ảnh hưởng trực tiếp đến retrieval. Nếu không có pipeline Day 10, agent có thể trả lời sai "14 ngày" thay vì "7 ngày".

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi muốn thêm LLM-judge vào eval thay vì chỉ dùng keyword matching.

Hiện tại eval chỉ check xem top-k có chứa keyword "7 ngày" hay không. Nhưng trong thực tế, agent có thể tổng hợp câu trả lời từ nhiều chunks, và có thể reasoning sai dù keyword đúng.

Ý tưởng là tạo `eval_llm_judge.py` dùng GPT-4 hoặc Claude để đánh giá answer quality (0-10 scale) và giải thích reasoning. Thêm 2 câu eval nữa để đủ 6 câu (Distinction criterion c yêu cầu ≥5 câu). Output sẽ có cột `llm_score` và `llm_reasoning`.

Khi so sánh inject-bad vs sprint3-clean, tôi kỳ vọng inject-bad sẽ có `llm_score` thấp hơn vì context bị ô nhiễm với chunk stale, dù keyword matching vẫn pass.

Cách này gần hơn với production eval và có thể phát hiện những lỗi tinh vi mà keyword matching bỏ qua.
