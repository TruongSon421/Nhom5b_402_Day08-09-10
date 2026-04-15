"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Tuple


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


# NEW EXPECTATIONS - Sprint 2
# E7: No HTML tags in chunk_text (halt)
_HTML_TAG_PATTERN = re.compile(r'<[^>]+>')

def _check_no_html_tags(cleaned_rows: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """Check that no chunk_text contains HTML tags."""
    rows_with_html = [
        r for r in cleaned_rows
        if _HTML_TAG_PATTERN.search(r.get("chunk_text", ""))
    ]
    passed = len(rows_with_html) == 0
    detail = f"html_tag_count={len(rows_with_html)}"
    return passed, detail


# E8: effective_date not in the far future (warn)
def _check_effective_date_not_future(cleaned_rows: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """Check that effective_date is not beyond current date + 30 days."""
    today = date.today()
    future_threshold = today + timedelta(days=30)
    
    rows_in_future = []
    for r in cleaned_rows:
        eff_date_str = r.get("effective_date", "")
        if eff_date_str:
            try:
                eff_date = datetime.strptime(eff_date_str, "%Y-%m-%d").date()
                if eff_date > future_threshold:
                    rows_in_future.append(r.get("chunk_id"))
            except ValueError:
                pass
    
    passed = len(rows_in_future) == 0
    detail = f"future_date_count={len(rows_in_future)}"
    return passed, detail


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # NEW E7: No HTML tags in chunk_text (halt)
    ok7, detail7 = _check_no_html_tags(cleaned_rows)
    results.append(
        ExpectationResult(
            "no_html_tags",
            ok7,
            "halt",
            detail7,
        )
    )

    # NEW E8: effective_date not in the far future (warn)
    ok8, detail8 = _check_effective_date_not_future(cleaned_rows)
    results.append(
        ExpectationResult(
            "effective_date_not_future",
            ok8,
            "warn",
            detail8,
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
