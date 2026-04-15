# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Nhóm 5B  
**Lớp:** 402  
**Thành viên:**

| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| Trần Thượng Trường Sơn | Sprint 1 | tranthuongtruongson@example.com |
| Bùi Lâm Tiến | Sprint 2 | builamtien@example.com |
| Trương Đăng Nghĩa | Sprint 3 | truongdangnghia@example.com |
| Nhóm làm chung | Sprint 4 (docs) | |

**Ngày nộp:** 2026-04-15  
**Repo:** https://github.com/TruongSon421/Nhom5b_402_Day08-09-10
**Độ dài:** ~800 từ

---

## 1. Pipeline tổng quan

### Nguồn raw

Chúng tôi sử dụng CSV mẫu `data/raw/policy_export_dirty.csv` với 10 records mô phỏng export từ hệ thống HR/Policy. CSV này được thiết kế có chủ đích với các failure modes:
- Duplicate records (cùng chunk_text, khác chunk_id)
- Missing `effective_date` (NULL hoặc empty)
- Invalid `doc_id` (không thuộc allowlist)
- Non-ISO date format (DD/MM/YYYY thay vì YYYY-MM-DD)
- Stale HR version (10 ngày phép vs 12 ngày phép - conflict version)
- Stale refund window (14 ngày vs 7 ngày - policy outdated)
- Encoding issues (BOM, smart quotes, excessive whitespace)

### Luồng end-to-end

```
Raw CSV (10 records) 
  → Ingest (load_raw_csv)
  → Clean (9 rules: 6 baseline + 3 new)
  → Validate (8 expectations: 6 baseline + 2 new)
  → Embed (Chroma idempotent: upsert + prune)
  → Manifest (run_id, metrics, freshness check)
```

**Kết quả:** 6 cleaned records, 4 quarantine records, 6 vectors trong Chroma collection `day10_kb`.

### Lệnh chạy một dòng

```bash
python etl_pipeline.py run --run-id sprint3-clean
```

Output:
- Log: `artifacts/logs/run_sprint3-clean.log`
- Cleaned CSV: `artifacts/cleaned/cleaned_sprint3-clean.csv`
- Quarantine CSV: `artifacts/quarantine/quarantine_sprint3-clean.csv`
- Manifest: `artifacts/manifests/manifest_sprint3-clean.json`
- Chroma: `chroma_db/day10_kb` (6 vectors)

**run_id tracking:** Dòng đầu tiên trong log: `run_id=sprint3-clean`. Cũng có thể lấy từ manifest: `jq '.run_id' artifacts/manifests/manifest_sprint3-clean.json`.

---

## 2. Cleaning & expectation

### Baseline (6 rules + 6 expectations)

**Cleaning rules:**
1. Allowlist doc_id check
2. Normalize effective_date (DD/MM/YYYY → YYYY-MM-DD)
3. Quarantine HR stale (effective_date < 2026-01-01)
4. Fix refund window (14 → 7 days)
5. Deduplicate chunk_text
6. Validate non-empty fields

**Expectations:**
1. min_one_row (halt)
2. no_empty_doc_id (halt)
3. refund_no_stale_14d_window (halt)
4. chunk_min_length_8 (warn)
5. effective_date_iso_yyyy_mm_dd (halt)
6. hr_leave_no_stale_10d_annual (halt)

### New additions (3 rules + 2 expectations)

**New cleaning rules:**
7. Strip BOM (Byte Order Mark) - remove `\ufeff`
8. Normalize Unicode (smart quotes → straight quotes, en/em dash → hyphen)
9. Quarantine excessive whitespace (>5 consecutive spaces)

**New expectations:**
7. no_html_tags (halt) - không có HTML tags trong chunk_text
8. effective_date_not_future (warn) - effective_date không được >30 ngày so với hôm nay

### Bảng metric_impact

| Rule / Expectation mới | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ |
|------------------------|-----------------|----------------------------|----------|
| **Strip BOM** | N/A (CSV mẫu không có BOM) | Nếu có BOM → cleaned_records không đổi, chunk_text sạch hơn | Code: `cleaning_rules.py:30-35` |
| **Normalize Unicode** | N/A (CSV mẫu không có smart quotes) | Nếu có → note `[cleaned: unicode_normalized]` | Code: `cleaning_rules.py:38-56` |
| **Quarantine excessive whitespace** | quarantine_records=4 | Nếu inject chunk có >5 spaces → quarantine_records=5 | Code: `cleaning_rules.py:59-63` |
| **no_html_tags (halt)** | html_tag_count=0 (PASS) | Nếu inject `<div>...</div>` → FAIL (halt) | Log: `run_sprint3-clean.log:7` |
| **effective_date_not_future (warn)** | future_date_count=0 (PASS) | Nếu inject date=2027-01-01 → future_date_count=1 (warn) | Log: `run_sprint3-clean.log:8` |

**Tác động thực tế:** Rules 7-9 không ảnh hưởng CSV mẫu hiện tại (không có BOM/smart quotes/excessive whitespace), nhưng đã được test với inject custom data. Expectations 7-8 PASS trên CSV mẫu với log evidence (`html_tag_count=0`, `future_date_count=0`).

### Expectation fail example

**Scenario:** Inject corruption với `--no-refund-fix --skip-validate`

**Log (`run_inject-bad.log` line 3):**
```
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1
WARN: expectation failed but --skip-validate → tiếp tục embed (chỉ dùng cho demo Sprint 3).
```

**Xử lý:** Trong production, pipeline halt (exit code 2), không embed. Trong lab (demo), flag `--skip-validate` bypass halt để chứng minh tác động lên retrieval.

---

## 3. Before / after ảnh hưởng retrieval

### Kịch bản inject (Sprint 3)

**Command:**
```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv
```

**Corruption mechanism:**
- Flag `--no-refund-fix` → bỏ qua cleaning rule fix "14 ngày làm việc → 7 ngày làm việc"
- Flag `--skip-validate` → bypass expectation `refund_no_stale_14d_window` FAIL
- Chunk stale "14 ngày làm việc" được embed vào Chroma → ô nhiễm vector store

### Kết quả định lượng

**File:** `artifacts/eval/after_inject_bad.csv` (before) vs `artifacts/eval/before_after_eval_clean.csv` (after)

| Question | Scenario | contains_expected | hits_forbidden | Phân tích |
|----------|----------|-------------------|----------------|-----------|
| **q_refund_window** | inject-bad | yes | **yes** ⚠️ | Top-k chứa cả "7 ngày" (đúng) và "14 ngày" (sai) |
| **q_refund_window** | sprint3-clean | yes | **no** ✓ | Chỉ có "7 ngày", prune đã xóa chunk stale |
| **q_leave_version** | inject-bad | yes | no | HR stale đã bị quarantine trước khi inject |
| **q_leave_version** | sprint3-clean | yes | no | Kết quả giống nhau (quarantine rule hoạt động) |

**Phân tích chi tiết:**

**Before (inject-bad):** `hits_forbidden=yes` chứng minh vector store bị ô nhiễm. Dù `contains_expected=yes` (vì có chunk đúng), agent vẫn có thể trả lời sai nếu LLM chọn chunk "14 ngày".

**After (sprint3-clean):** `hits_forbidden=no` chứng minh idempotent upsert + prune đã làm sạch index. Chỉ có chunk "7 ngày" trong top-k.

**Evidence:**
- Log: `embed_prune_removed=1` (xóa 1 vector cũ)
- CSV: Dòng `q_refund_window` có `hits_forbidden` khác nhau giữa 2 files
- Manifest: `no_refund_fix=true` (inject-bad) vs `false` (sprint3-clean)

---

## 4. Freshness & monitoring

### SLA chọn: 24 giờ

**Đo tại:** Boundary `publish` (thời điểm ghi manifest sau embed)

**Nguồn timestamp:** `latest_exported_at` trong manifest (đọc từ CSV `exported_at`)

**Kết quả:**
```
freshness_check=FAIL {"latest_exported_at": "2026-04-10T08:00:00", "age_hours": 114.111, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
```

### Ý nghĩa PASS/WARN/FAIL

| Status | Điều kiện | Ý nghĩa | Action |
|--------|-----------|---------|--------|
| **PASS** | age_hours ≤ 24 | Data fresh, trong SLA | Không action |
| **WARN** | N/A (chưa implement) | Gần vượt SLA (20-24h) | Alert team, chuẩn bị re-export |
| **FAIL** | age_hours > 24 | Data stale, vượt SLA | Alert upstream, yêu cầu re-export |

### Tại sao FAIL là hợp lý

CSV mẫu có `exported_at = 2026-04-10T08:00:00` (cũ 4+ ngày). FAIL phản ánh đúng thực tế data snapshot cũ. Trong production, alert sẽ kích hoạt workflow re-ingest từ upstream.

**Quyết định nhóm:** Không cập nhật timestamp giả để PASS vì che giấu vấn đề thực tế. SLA áp cho "data snapshot" (thời điểm export từ nguồn), không phải "pipeline run".

---

## 5. Liên hệ Day 09

### Tích hợp với multi-agent

**Day 09 context:** Multi-agent orchestration với retrieval worker, synthesis worker, policy tool.

**Day 10 contribution:** Pipeline này cung cấp và làm mới corpus cho retrieval worker.

**Collection:** `day10_kb` (tách với `day09_kb` để không ảnh hưởng grading Day 09)

**Data source:** Cùng 5 policy documents trong `data/docs/`:
- policy_refund_v4.txt
- sla_p1_2026.txt
- it_helpdesk_faq.txt
- hr_leave_policy.txt
- access_control_sop.txt

### Workflow tích hợp

```
Day 10 Pipeline (ETL)
  ↓ ingest → clean → validate → embed
  ↓ chroma_db/day10_kb (6 vectors)
  ↓
Day 09 Retrieval Worker
  ↓ query(question) → top-k chunks
  ↓
Day 09 Synthesis Worker
  ↓ generate answer from chunks
```

### Lợi ích

1. **Data quality gate:** Expectation suite đảm bảo không embed chunk stale/invalid → agent không trả lời sai
2. **Version control:** Manifest tracking run_id → có thể rollback nếu cần
3. **Observability:** Freshness check, quarantine log, eval metrics → phát hiện vấn đề sớm

**Ví dụ:** Nếu không có pipeline Day 10, agent Day 09 có thể trả lời "14 ngày" thay vì "7 ngày" vì vector store chứa chunk stale.

---

## 6. Rủi ro còn lại & việc chưa làm

### Đã làm (Sprint 1-4)

✓ 9 cleaning rules (6 baseline + 3 mới)  
✓ 8 expectations (6 baseline + 2 mới)  
✓ Idempotent embed (upsert + prune)  
✓ Before/after evidence (2 câu: q_refund_window, q_leave_version)  
✓ Manifest tracking với run_id  
✓ Freshness check (1 boundary: publish)  
✓ 3 docs (quality_report, pipeline_architecture, group_report)  
✓ Inject corruption demo

### Chưa làm (Distinction criteria)

- **(a) GE/pydantic validate:** Chưa dùng Great Expectations hoặc pydantic model validate schema cleaned
- **(b) Freshness 2 boundary:** Chỉ đo `publish`, chưa đo `ingest` → không phân biệt "data cũ" vs "pipeline chậm"
- **(c) Eval mở rộng:** Chỉ 4 câu keyword-based, chưa có LLM-judge hoặc bộ slice ≥5 câu
- **(d) Rule versioning động:** Cutoff date `2026-01-01` hard-code, chưa đọc từ `data_contract.yaml`

### Rủi ro

- CSV mẫu chỉ 10 dòng → chưa test scale (1000+ chunks)
- Chưa test concurrent pipeline runs (race condition)
- Freshness SLA 24h có thể quá chặt cho batch weekly
- Quarantine chưa có review workflow (approve/reject)

### Việc tiếp theo (nếu có thêm 2 giờ)

1. Implement freshness 2 boundary (ingest + publish) → Distinction (b)
2. Add LLM-judge eval với 2 câu mới (total 6) → Distinction (c)
3. Đọc cutoff date từ `data_contract.yaml` → Distinction (d)
