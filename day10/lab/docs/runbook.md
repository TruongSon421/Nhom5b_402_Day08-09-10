# Runbook — Lab Day 10 (Incident Response)

**Nhóm:** Nhóm 5B — Lớp E402  
**Cập nhật:** 2026-04-15

---

## Incident: Freshness check FAIL (data stale)

### Symptom

**Alert:** Slack #data-quality: "Freshness check FAIL: age_hours=114, sla_hours=24"

**Observable behavior:**

- Pipeline chạy thành công (exit 0)
- Manifest có `freshness_check=FAIL`
- Agent có thể trả lời đúng nhưng data đã cũ >4 ngày

### Detection

**Automated:**

1. **Pipeline log:** `freshness_check=FAIL {"age_hours": 122.552, ...}`
2. **Manifest:** `latest_exported_at` cũ hơn 24 giờ so với `run_timestamp`

**Manual:**

```bash
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_2026-04-15T08-49Z.json
# Output: FAIL {"latest_exported_at": "2026-04-10T08:00:00", "age_hours": 122.552, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
```

### Diagnosis

| Bước | Việc làm | Kết quả mong đợi | Command |
|------|----------|------------------|---------|
| 1 | Check `latest_exported_at` trong manifest | Timestamp cũ hơn 24h | `jq '.latest_exported_at' artifacts/manifests/manifest_*.json` |
| 2 | Check raw CSV `exported_at` column | Tất cả dòng có `exported_at` cũ | `cut -d, -f5 data/raw/policy_export_dirty.csv \| sort \| uniq` |
| 3 | Check upstream export job | Job có chạy hàng ngày không? | `crontab -l \| grep policy_export` (hoặc check scheduler) |
| 4 | Check upstream DB watermark | Max(updated_at) trong source table | `psql -c "SELECT MAX(updated_at) FROM policy_chunks"` (nếu có DB) |

**Root cause scenarios:**

- **A. Upstream export job fail** → không có file mới
- **B. Upstream data không update** → source DB stale
- **C. SLA quá chặt** → 24h không phù hợp với batch weekly
- **D. Timezone mismatch** → `exported_at` dùng local time, `run_timestamp` dùng UTC

### Mitigation

**Immediate (10 phút):**

1. Check if this is expected (vd: lab data mẫu cố ý cũ):

   ```bash
   # Nếu đây là lab/staging → OK, document trong runbook
   # Nếu production → escalate
   ```

2. Nếu production: Page upstream data team để re-export

**Short-term (1 ngày):**

- Coordinate với upstream: Confirm export schedule (daily? weekly?)
- Adjust SLA nếu cần: `FRESHNESS_SLA_HOURS=168` (7 days) cho batch weekly
- Add `ingest_timestamp` vào manifest để phân biệt "data cũ" vs "pipeline chậm"

### Prevention

1. **SLA alignment:** Review freshness SLA với business owner (24h? 7 days?)
2. **Upstream SLA:** Chắc chắn upstream export job có monitoring và alert
3. **Graceful degradation:** Nếu data stale nhưng vẫn usable → WARN thay vì FAIL, log nhưng không halt
4. **Documentation:** Ghi rõ trong `data_contract.md`: "SLA áp cho data snapshot, không phải pipeline run"

---
