# Tuning Log — RAG Pipeline (Day 08 Lab)

> Template: Ghi lại mỗi thay đổi và kết quả quan sát được.
> A/B Rule: Chỉ đổi MỘT biến mỗi lần.

---

## Baseline (Sprint 2)

**Ngày:** 2026-04-13  
**Config:**
```
retrieval_mode = "dense"
chunk_size = 450 tokens
overlap = 75 tokens
top_k_search = 10
top_k_select = 3
use_rerank = False
llm_model = gpt-4o-mini
```

**Scorecard Baseline:**
| Metric | Average Score |
|--------|--------------|
| Faithfulness | 4.20 /5 |
| Answer Relevance | 4.60 /5 |
| Context Recall | 5.00 /5 |
| Completeness | 3.60 /5 |

**Câu hỏi yếu nhất (điểm thấp):**
> - **gq07** (Insufficient Context) - Faithfulness = 1/5, Relevance = 1/5: Câu hỏi về phạt vi phạm SLA không có trong docs → system abstain đúng
> - **gq05** (Access Control) - Faithfulness = 2/5: Trả lời sai về contractor access, model bịa thông tin không có trong context
> - **gq08** (HR Policy) - Faithfulness = 4/5: Thiếu một số chi tiết nhỏ về quy trình nghỉ ốm

**Giả thuyết nguyên nhân (Error Tree):**
- [x] Indexing: Chunking cắt giữa điều khoản → **Không phải**, chunks đều cắt theo section heading
- [ ] Indexing: Metadata thiếu effective_date → **Không phải**, 100% chunks có effective_date
- [x] Retrieval: Dense bỏ lỡ exact keyword / alias → **Có thể**, cần test với hybrid
- [ ] Retrieval: Top-k quá ít → thiếu evidence → **Không phải**, context recall = 5.0/5
- [x] Generation: Prompt không đủ grounding → **Có thể**, gq05 bị hallucination
- [ ] Generation: Context quá dài → lost in the middle → **Không phải**, chỉ dùng 3 chunks

---

## Variant 1 (Sprint 3)

**Ngày:** 2026-04-13  
**Biến thay đổi:** Retrieval mode: dense → hybrid (Dense + BM25 RRF)  
**Lý do chọn biến này:**
> Chọn hybrid vì corpus có cả ngôn ngữ tự nhiên (policy, quy trình) lẫn keyword/mã lỗi chuyên ngành (P1, Level 3, VPN, Flash Sale).
> Dense retrieval tốt cho paraphrase nhưng có thể bỏ lỡ exact term.
> BM25 bổ sung khả năng keyword matching cho tên riêng và mã lỗi.
> Giữ nguyên tất cả tham số khác (A/B Rule: chỉ đổi 1 biến).

**Config thay đổi:**
```
retrieval_mode = "hybrid"   # Dense + BM25 với RRF (dense_weight=0.6, sparse_weight=0.4)
# Các tham số còn lại giữ nguyên như baseline
```

**Scorecard Variant 1:**
| Metric | Baseline | Variant 1 | Delta |
|--------|----------|-----------|-------|
| Faithfulness | 4.20/5 | 4.10/5 | -0.10 |
| Answer Relevance | 4.60/5 | 4.20/5 | -0.40 |
| Context Recall | 5.00/5 | 5.00/5 | 0.00 |
| Completeness | 3.60/5 | 3.20/5 | -0.40 |

**Nhận xét:**
> **Variant 1 KÉM HƠN baseline** ở hầu hết metrics:
> - **gq05** (Access Control): Baseline cho câu trả lời có hallucination nhưng vẫn relevant (2/5/5/4), Variant abstain hoàn toàn (1/1/5/1) → mất điểm relevance và completeness
> - **gq07** (Insufficient Context): Cả hai đều abstain đúng, nhưng Variant cho completeness thấp hơn (3 → 2)
> - Các câu khác: Tie hoặc tương đương
> 
> **Nguyên nhân có thể:**
> - BM25 có thể retrieve chunks ít relevant hơn cho một số query phức tạp
> - RRF fusion có thể làm giảm precision khi sparse results nhiễu
> - Hybrid không cải thiện vì context recall đã đạt 5.0/5 với dense

**Kết luận:**
> **Variant 1 KHÔNG tốt hơn baseline** (delta âm ở 3/4 metrics).
> Bằng chứng: Faithfulness -0.10, Relevance -0.40, Completeness -0.40.
> **Khuyến nghị**: Giữ lại baseline (dense) cho production.
> Nếu có thêm thời gian, nên thử: (1) Rerank với cross-encoder, (2) Query expansion, (3) Tune prompt để giảm hallucination.

---

## Variant 2 (nếu có thời gian)

**Ngày:** 2026-04-13  
**Biến thay đổi:** Điều chỉnh trọng số hybrid (dense/sparse): 0.6/0.4 → 0.8/0.2  
**Lý do chọn biến này:**
> Kết quả Variant 1 cho thấy hybrid đang thiên về sparse quá mức, làm giảm relevance và completeness.
> Nhóm thử tăng trọng số dense để ưu tiên semantic match, đồng thời vẫn giữ tín hiệu keyword từ BM25.
> Các tham số khác giữ nguyên để đảm bảo tuân thủ A/B Rule.

**Config:**
```
retrieval_mode = "hybrid"   # Dense + BM25 với RRF
dense_weight = 0.8
sparse_weight = 0.2
# top_k_search = 10, top_k_select = 3, use_rerank = False (giữ nguyên)
```

**Scorecard Variant 2:**
| Metric | Baseline | Variant 1 | Variant 2 | Best |
|--------|----------|-----------|-----------|------|
| Faithfulness | 4.70/5 | 4.10/5 | 5.00/5 | Variant 2 |
| Answer Relevance | 4.80/5 | 4.20/5 | 4.80/5 | Baseline = Variant 2 |
| Context Recall | 5.00/5 | 5.00/5 | 5.00/5 | Tie |
| Completeness | 3.70/5 | 3.20/5 | 3.40/5 | Baseline |

**So sánh nhanh với Baseline và Variant 1:**
> **So với Baseline (Sprint 2):**
> - Faithfulness: **+0.30** (4.70 → 5.00)
> - Relevance: **0.00** (4.80 → 4.80)
> - Context Recall: **0.00** (5.00 → 5.00)
> - Completeness: **-0.30** (3.70 → 3.40)
>
> **So với Variant 1 (hybrid 0.6/0.4, không đổi trọng số):**
> - Faithfulness: **+0.90** (4.10 → 5.00)
> - Relevance: **+0.60** (4.20 → 4.80)
> - Context Recall: **0.00** (5.00 → 5.00)
> - Completeness: **+0.20** (3.20 → 3.40)
>
> Điều này cho thấy Variant 2 đã sửa được phần lớn suy giảm chất lượng của Variant 1, nhưng vẫn chưa vượt baseline ở completeness.

**Nhận xét theo câu hỏi:**
> - **gq05 (Access Control):** Variant 2 tránh hallucination (Faithful 5 thay vì 2 ở baseline), nhưng trả lời dạng abstain nên completeness chỉ 1.
> - **gq09 (IT Helpdesk):** Vẫn thiếu phần "đổi mật khẩu qua đâu", nên relevance/completeness chưa cải thiện.
> - Các câu còn lại gần như tie giữa baseline và variant 2.

**Kết luận Variant 2:**
> Variant 2 là lựa chọn **an toàn hơn Variant 1** và cải thiện rõ faithfulness.
> Tuy nhiên nếu ưu tiên trả lời đầy đủ (completeness), baseline dense vẫn nhỉnh hơn.
> **Khuyến nghị tạm thời:** giữ baseline cho production; dùng variant 2 nếu ưu tiên giảm hallucination.

---

## Variant 3 (Sprint 4 - Prompt v2 + tăng top-k)

**Ngày:** 2026-04-13  
**Biến thay đổi:** Hybrid 0.6/0.4 + tăng `top_k_search/top_k_select` (10/3 → 15/5) + prompt grounded v2  
**Lý do chọn biến này:**
> Sau khi chỉnh prompt để ép trả lời đủ từng vế câu hỏi, nhóm tăng top-k để mở rộng evidence pool,
> kỳ vọng tăng completeness mà vẫn giữ faithfulness.

**Config:**
```
retrieval_mode = "hybrid"
top_k_search = 15
top_k_select = 5
use_rerank = False
dense_weight = 0.6
sparse_weight = 0.4
prompt = grounded_prompt_v2 (multi-requirement, partial-missing handling)
```

**Scorecard Variant 3 (theo run mới):**
| Metric | Baseline (10/3, dense) | Variant 3 (15/5, hybrid) | Delta |
|--------|--------------------------|----------------------------|-------|
| Faithfulness | 4.50/5 | 4.80/5 | +0.30 |
| Answer Relevance | 4.60/5 | 4.60/5 | 0.00 |
| Context Recall | 5.00/5 | 5.00/5 | 0.00 |
| Completeness | 3.80/5 | 3.60/5 | -0.20 |

**Nhận xét theo câu hỏi:**
> - **gq03:** Variant 3 tốt hơn baseline (3/4/5/3 → 5/5/5/4), cho thấy hybrid + context rộng giúp câu refund rõ hơn.
> - **gq05:** Baseline tốt hơn (3/5/5/5 vs 4/4/5/2) do variant thiếu độ đầy đủ ở phần yêu cầu đặc biệt.
> - **gq09:** Cả hai vẫn tie ở 4/4/5/3, vấn đề "đổi mật khẩu qua đâu" chưa được giải quyết triệt để.

**Kết luận Variant 3:**
> Variant 3 là cấu hình cân bằng tốt về groundedness (faithfulness cao hơn baseline), nhưng vẫn thua baseline về completeness.
> Nếu mục tiêu ưu tiên "đúng và bám context": cân nhắc Variant 3.
> Nếu mục tiêu ưu tiên "đầy đủ câu trả lời": baseline dense vẫn là mốc tốt hơn.

---

## Tóm tắt học được

> Điền sau khi hoàn thành evaluation (Sprint 4).

1. **Lỗi phổ biến nhất trong pipeline này là gì?**
   > **Hallucination** (model bịa thông tin không có trong context) - xảy ra ở gq05 với baseline. Prompt grounding cần được cải thiện hoặc cần thêm rerank để lọc context chất lượng cao hơn.

2. **Biến nào có tác động lớn nhất tới chất lượng?**
   > **Dense/sparse weighting trong hybrid retrieval** có tác động rõ rệt ở Sprint 4. Cùng là hybrid nhưng đổi từ 0.6/0.4 sang 0.8/0.2 đã cải thiện mạnh faithfulness (4.10 → 5.00) và relevance (4.20 → 4.80). Tuy nhiên completeness vẫn thấp hơn baseline dense (3.40 vs 3.70), cho thấy vẫn cần tune generation/prompt để trả lời đầy đủ hơn.

3. **Nếu có thêm 1 giờ, nhóm sẽ thử gì tiếp theo?**
   > (1) **Rerank với cross-encoder** để tăng precision của top-3 chunks, (2) **Tune prompt** để giảm hallucination (thêm "Do not infer or assume"), (3) **Query decomposition** cho câu hỏi phức tạp (gq02, gq06), (4) **Metadata filtering** theo department để giảm noise.
