# Quality report — Lab Day 10 (nhóm)

**run_id:** sprint3-clean (clean) / inject-bad (corrupted)  
**Ngày:** 2026-04-15

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (inject-bad) | Sau (sprint3-clean) | Ghi chú |
|--------|-------------------|---------------------|---------|
| raw_records | 10 | 10 | Cùng nguồn CSV |
| cleaned_records | 6 | 6 | Số lượng giống nhau |
| quarantine_records | 4 | 4 | 4 dòng bị loại: unknown_doc_id, missing_date, stale_hr, duplicate |
| Expectation halt? | **YES** (bypassed với --skip-validate) | **NO** (all pass) | `refund_no_stale_14d_window` FAIL khi inject |

**Chi tiết expectation inject-bad:**
- `expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1`
- Pipeline vẫn chạy tiếp vì flag `--skip-validate`

**Chi tiết expectation sprint3-clean:**
- Tất cả 8 expectations PASS (6 baseline + 2 mới)

---

## 2. Before / after retrieval (bắt buộc)

> File: `artifacts/eval/after_inject_bad.csv` (trước) và `artifacts/eval/before_after_eval_clean.csv` (sau)

### Câu hỏi then chốt: refund window (`q_refund_window`)

**Trước (inject-bad):**
```csv
q_refund_window,Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn?,policy_refund_v4,Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.,yes,yes,,3
```
- `contains_expected`: **yes** (có "7 ngày" trong top-k)
- `hits_forbidden`: **yes** (vẫn còn chunk "14 ngày làm việc" trong top-k)
- **Vấn đề:** Vector store bị ô nhiễm với chunk stale

**Sau (sprint3-clean):**
```csv
q_refund_window,Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn?,policy_refund_v4,Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.,yes,no,,3
```
- `contains_expected`: **yes** (có "7 ngày")
- `hits_forbidden`: **no** ✓ (không còn "14 ngày làm việc")
- **Kết quả:** Vector store sạch, prune đã xóa chunk cũ

**Phân tích:** Đây là bằng chứng rõ ràng nhất về tác động của data quality lên retrieval. Khi inject corruption (bỏ flag `--no-refund-fix`), chunk "14 ngày làm việc" được embed → agent có thể trả lời sai. Sau khi chạy pipeline chuẩn, idempotent upsert + prune đảm bảo chỉ có chunk đúng trong index.

---

### Merit (khuyến nghị): versioning HR — `q_leave_version`

**Trước (inject-bad):**
```csv
q_leave_version,"Theo chính sách nghỉ phép hiện hành (2026), nhân viên dưới 3 năm kinh nghiệm được bao nhiêu ngày phép năm?",hr_leave_policy,Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm theo chính sách 2026.,yes,no,yes,3
```
- `contains_expected`: **yes** ("12 ngày")
- `hits_forbidden`: **no** (không có "10 ngày")
- `top1_doc_expected`: **yes** (top-1 là hr_leave_policy)

**Sau (sprint3-clean):**
```csv
q_leave_version,"Theo chính sách nghỉ phép hiện hành (2026), nhân viên dưới 3 năm kinh nghiệm được bao nhiêu ngày phép năm?",hr_leave_policy,Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm theo chính sách 2026.,yes,no,yes,3
```
- Kết quả giống nhau vì cleaning rule `stale_hr_policy_effective_date` đã quarantine bản HR cũ (effective_date < 2026-01-01) ở cả hai scenario
- Expectation `hr_leave_no_stale_10d_annual` xác nhận không còn "10 ngày phép năm" trong cleaned data

**Kết luận:** Quarantine rule hoạt động đúng, ngăn chặn version conflict trước khi embed.

---

## 3. Freshness & monitor

**Kết quả:** `freshness_check=FAIL` trên cả hai run

```
freshness_check=FAIL {"latest_exported_at": "2026-04-10T08:00:00", "age_hours": 114.111, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
```

**Giải thích SLA:**
- **SLA chọn:** 24 giờ (mặc định `FRESHNESS_SLA_HOURS=24`)
- **Đo tại:** Boundary `publish` (thời điểm ghi manifest sau embed)
- **Nguồn timestamp:** Trường `latest_exported_at` trong manifest (đọc từ CSV `exported_at`)
- **Age thực tế:** 114 giờ (≈4.75 ngày)

**Tại sao FAIL là hợp lý:**
CSV mẫu `policy_export_dirty.csv` có `exported_at = 2026-04-10T08:00:00`, cũ hơn 4+ ngày so với thời điểm chạy pipeline (2026-04-15). Đây là **data stale thật** — trong production sẽ trigger alert để yêu cầu re-export từ hệ nguồn.

**Quyết định nhóm:** Không cập nhật timestamp giả để PASS vì:
1. FAIL phản ánh đúng thực tế data snapshot cũ
2. SLA áp cho "thời điểm export từ nguồn", không phải "thời điểm chạy pipeline"
3. Trong production, alert sẽ kích hoạt workflow re-ingest

**Cải tiến (chưa làm):** Đo freshness tại 2 boundary (ingest + publish) để phân biệt "data cũ từ nguồn" vs "pipeline chậm" — xem mục 5.

---

## 4. Corruption inject (Sprint 3)

**Kịch bản inject:**

```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
```

**Mô tả corruption:**
- **Loại:** Stale policy content (cửa sổ hoàn tiền 14 ngày thay vì 7 ngày)
- **Cơ chế:** Flag `--no-refund-fix` bỏ qua cleaning rule fix "14 ngày làm việc → 7 ngày làm việc"
- **Bypass validation:** Flag `--skip-validate` cho phép embed dù expectation `refund_no_stale_14d_window` FAIL

**Log evidence (run_inject-bad.log):**
```
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1
WARN: expectation failed but --skip-validate → tiếp tục embed (chỉ dùng cho demo Sprint 3).
embed_prune_removed=1
embed_upsert count=6 collection=day10_kb
```

**Cách phát hiện:**
1. **Expectation suite:** `refund_no_stale_14d_window` FAIL → pipeline nên halt
2. **Eval retrieval:** Chạy `python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv`
   - Kết quả: `q_refund_window` có `hits_forbidden=yes`
   - Chứng minh: Top-k chunks chứa forbidden term "14 ngày làm việc"
3. **Manifest:** Trường `skipped_validate=true` cảnh báo pipeline đã bypass quality gate

**Tác động:**
- Agent có thể trả lời "14 ngày" thay vì "7 ngày" → sai policy
- Dù `contains_expected=yes` (vì có chunk khác đúng), context vẫn ô nhiễm
- Đây là ví dụ điển hình của "data quality issue không phát hiện được bằng mắt thường"

**Fix:**
```bash
python etl_pipeline.py run --run-id sprint3-clean
```
- Cleaning rule fix 14→7 được áp dụng
- Idempotent upsert + prune xóa vector stale
- Eval: `hits_forbidden=no` ✓

---

## 5. Hạn chế & việc chưa làm

### Đã làm (Sprint 1-3):
- ✓ 9 cleaning rules (6 baseline + 3 mới: BOM strip, Unicode normalize, excessive whitespace)
- ✓ 8 expectations (6 baseline + 2 mới: no HTML tags, effective_date not future)
- ✓ Idempotent embed (upsert by chunk_id + prune stale ids)
- ✓ Before/after evidence cho 2 câu (q_refund_window, q_leave_version)
- ✓ Manifest tracking với run_id
- ✓ Freshness check (1 boundary: publish)

### Chưa làm (cải tiến tiềm năng):
- **Freshness 2 boundary:** Chỉ đo tại `publish` (manifest timestamp). Chưa đo tại `ingest` (thời điểm đọc raw file) → không phân biệt được "data cũ từ nguồn" vs "pipeline chậm". Cần thêm `ingest_timestamp` vào manifest (Distinction criterion b).
- **Rule versioning động:** Cutoff date `2026-01-01` đang hard-code trong `cleaning_rules.py`. Nên đọc từ `contracts/data_contract.yaml` field `policy_versioning.hr_leave_min_effective_date` (Distinction criterion d).
- **Schema validation:** Chưa dùng pydantic model validate schema cleaned. Hiện chỉ có expectation check format (Distinction criterion a).
- **Eval mở rộng:** Chỉ có 4 câu keyword-based. Chưa có LLM-judge hoặc bộ slice ≥5 câu (Distinction criterion c).
- **Quarantine review workflow:** Chưa có process approve/merge lại quarantine records. Hiện chỉ ghi CSV và bỏ qua.
- **Lineage tracking:** Manifest có `run_id` nhưng chưa track upstream dependencies (file raw nào, version nào).

### Rủi ro còn lại:
- CSV mẫu chỉ 10 dòng → chưa test scale (1000+ chunks)
- Chưa test concurrent pipeline runs (race condition trên Chroma collection)
- Freshness SLA 24h có thể quá chặt cho batch weekly → cần review với business owner
