# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `data/raw/policy_export_dirty.csv` | CSV export từ HR/Policy system | Duplicate records, missing dates, invalid doc_id, non-ISO dates, stale HR version (10 vs 12 days), stale refund window (14 vs 7 days) | `raw_records`, `quarantine_records` |
| `data/docs/*.txt` | Policy documents (5 files) | Document not in allowlist, encoding issues | `cleaned_records` |

**Data Owner:** 
- HR Policy: hr-team@company.com
- IT Helpdesk: it-support@company.com
- Finance/Refund: finance@company.com

**SLA:**
- Freshness: 24 hours (configurable via FRESHNESS_SLA_HOURS)
- Data quality: 0% halt expectation failures

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | Stable ID: `{doc_id}_{seq}_{hash}` |
| doc_id | string | Có | Must be in allowlist: policy_refund_v4, sla_p1_2026, it_helpdesk_faq, hr_leave_policy |
| chunk_text | string | Có | Text content, min 8 chars |
| effective_date | date | Có | ISO format: YYYY-MM-DD |
| exported_at | datetime | Có | ISO 8601 timestamp |

---

## 3. Quy tắc quarantine vs drop

> Record bị flag đi đâu? Ai approve merge lại?

---

## 4. Phiên bản & canonical

> Source of truth cho policy refund: file nào / version nào?