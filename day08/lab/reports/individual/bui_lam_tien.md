# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Bùi Lâm Tiến

**Vai trò trong nhóm:** Retrieval Owner

**Ngày nộp:** 13/04/2026  

**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Trong lab Day 08, tôi phụ trách chính Sprint 2 và Sprint 3, tập trung vào lớp retrieval + generation trong `rag_answer.py`. Ở Sprint 2, tôi implement baseline dense retrieval (`retrieve_dense`) để query ChromaDB bằng embedding và build luồng `rag_answer()` end-to-end từ retrieve -> select -> prompt -> call LLM -> trả về `answer`, `sources`, `chunks_used`. Tôi ban đầu thiết kế grounded prompt dựa trên baseline cơ bản, sau đó đã thảo luận với teammate để phát triển nó ra dài hơn trong khi thực hiện tunning.  

Ở Sprint 3, tôi chọn hướng hybrid retrieval và implement `retrieve_sparse()` (BM25), `retrieve_hybrid()` (Dense + BM25 qua RRF), sau đó thêm hàm `compare_retrieval_strategies()` để so sánh A/B giữa baseline và variant. Phần việc của tôi kết nối trực tiếp với teammate làm indexing (đầu vào chunks/metadata) và teammate eval (scorecard đầu ra). Quá trình tunning được thực hiện kết hợp với teammate eval ở sprint 4.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Tôi cũng hiểu rõ hơn cách prompt ảnh hưởng trực tiếp đến hành vi của model. Nếu prompt quá “an toàn”, model dễ trả lời kiểu thiếu thông tin dù thật ra có thể trả lời một phần. Ngược lại, nếu prompt không ép grounding đủ chặt thì dễ bị bịa thêm. Vì vậy evaluation loop phải đọc từng case cụ thể, không chỉ nhìn điểm trung bình. Với tôi, phần học được lớn nhất là cách cân bằng giữa faithfulness và completeness trong cùng một pipeline.

Ngoài ra, việc lựa chọn mô hình LLM yếu để tổng hợp thông tin và ra kết quả cuối cùng là không nên khi mô hình có dấu hiệu chùn bước, không tự tin trong việc đưa ra những quyết định quan trọng dẫn đến kết quả bị sai lệch.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều làm tôi ngạc nhiên nhất là hybrid retrieval (dense + BM25) ở cấu hình đầu tiên không cải thiện, thậm chí kém baseline ở 3/4 metrics. Ban đầu tôi giả thuyết rằng vì corpus có nhiều keyword như P1, Level 3, mã lỗi nên thêm BM25 chắc chắn sẽ giúp. Tuy nhiên kết quả Variant 1 cho thấy relevance và completeness giảm.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** "Mật khẩu tài khoản công ty cần đổi định kỳ không? Nếu có, hệ thống sẽ nhắc nhở trước bao nhiêu ngày và đổi qua đâu?"

**Phân tích:**

Tôi phân tích **gq09**: “Mật khẩu tài khoản công ty cần đổi định kỳ không? Nếu có, hệ thống nhắc trước bao nhiêu ngày và đổi qua đâu?”. Đây là câu khá điển hình cho lỗi “đúng một phần”.  

Câu trả lời hiện tại nêu đúng 2 ý đầu: đổi mỗi 90 ngày và nhắc trước 7 ngày. Tuy nhiên hệ thống trả lời “không có thông tin về việc đổi mật khẩu qua đâu”. Vấn đề là câu hỏi có 3 yêu cầu rõ ràng, nên chỉ cần thiếu 1 yêu cầu là completeness giảm ngay, dù faithfulness vẫn tốt.  

Theo tôi, lỗi chính nằm ở retrieval + generation phối hợp chưa tốt, không phải do indexing hỏng. Retrieval đã kéo đúng source chính (`it/access-control-sop.md`, `support/helpdesk-faq.md`), nhưng chunk đưa vào prompt có thể chưa chứa đủ câu mô tả “kênh đổi mật khẩu”. Khi prompt nhận context thiếu mảnh ghép đó, model chọn trả lời an toàn.  

Variant hybrid có ưu điểm là giảm nguy cơ hallucination, nhưng với câu đa điều kiện như gq09, nó chưa cải thiện rõ về completeness. Nếu được cải thiện, tôi sẽ ưu tiên tăng chất lượng chunk selection (kết hợp rerank) để cải thiện chất lượng của các chunk được lựa chọn.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Nếu có thêm thời gian, tôi sẽ thử rerank bằng cross-encoder sau bước hybrid để chọn top chunks đúng trọng tâm hơn. Ngoài ra, tôi muốn chỉnh prompt theo hướng bắt buộc liệt kê từng yêu cầu của câu hỏi trước khi trả lời, nhằm giảm tình trạng bỏ sót ý. Lý do là từ kết quả, hệ thống hiện khá an toàn (ít hallucination) nhưng vẫn mất điểm completeness ở một số case.

---
