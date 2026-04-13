# Báo cáo Tổng quan Dự án Lab Day 08: RAG Pipeline

---

## 1. Tổng quan dự án thiết kế

Dự án nhằm xây dựng một hệ thống Trợ lý nội bộ cho khối CS + IT Helpdesk sử dụng kiến trúc Retrieval-Augmented Generation (RAG). Hệ thống hỗ trợ trả lời chuẩn xác các câu hỏi nghiệp vụ (chính sách nghỉ phép, SLA xử lý ticket, thao tác cấp quyền...) dựa trên bộ tài liệu PDF/Markdown nội bộ thay vì hiểu biết ngẫu nhiên của LLM.

- **Pipeline cốt lõi:** Indexing (ChromaDB + OpenAI Embeddings) → Retrieval (Dense & Hybrid/BM25) → Generation (OpenAI GPT-4o-mini).
- **Kỹ thuật cốt lõi:** Hệ thống sử dụng Grounded Prompting để ép mô hình phải tuân thủ chứng cứ (Evidence-only) hoặc từ chối trả lời nếu thiếu context (Abstain).

## 2. Diễn biến các Sprint

Nhóm đã triển khai phối hợp qua 4 Sprint (mỗi Sprint 60 phút) với trọng tâm như sau:

- **Sprint 1 (Build Index):** Xây dựng cơ sở dữ liệu vector trên ChromaDB với text-embedding-3-small, đảm bảo cắt chunk nội dung đủ tối ưu (chunk_size: 450, overlap: 75), gắn metadata bao gồm source và section.
- **Sprint 2 (Baseline Retrieval):** Thiết lập nền tảng RAG cơ sở bằng Dense Retrieval và hoàn thiện hàm call LLM với Grounded Prompt. Baseline hoạt động mạnh ở các câu hỏi đánh semantic match.
- **Sprint 3 (Tuning & Hybrid Retrieval):** Để khắc phục điểm yếu khi tìm kiếm từ khóa cứng và viết tắt (ERR-403, P1 ticket), nhóm đã implement thêm Sparse Retrieval (BM25) và Hybrid Retrieval dùng công thức RRF (Reciprocal Rank Fusion).
- **Sprint 4 (Evaluation & Tuning Loop):** Chạy các vòng A/B Test so sánh điểm số với bộ 10 test questions thông qua cấu hình `eval.py`. Thay đổi một số biến số gồm trọng số Dense/Sparse (từ 0.6/0.4 lên 0.8/0.2) và tăng Top-K Search/Select nhằm đo lường trade-off giữa "Faithfulness" (an toàn) và "Completeness" (trả lời đủ thông tin). Hai thành viên phối hợp chặt chẽ để tune lại prompt dựa trên kết quả.

## 3. Kết quả đạt được

- Hệ thống hoạt động End-to-End trôi chảy, tính năng so sánh và mô đun Evaluation bằng LLM-as-a-Judge trả về các insights cụ thể theo từng test question.
- **Baseline:** Điểm Recall tương đối tốt, song câu trả lời đôi khi không an toàn và có hiện tượng ngoại suy nhẹ.
- **Variant (Hybrid):** Đã kết hợp lấy được từ vựng chuẩn xác mã lỗi thông qua BM25, chỉ số Faithfulness tăng lên mức cao hơn nhờ giảm đi rủi ro model "chế" ý. Tuy nhiên chỉ số Completeness lại hụt (ví dụ câu hỏi nhiều vế như `gq05` và `gq09`, câu trả lời bị thiếu thông tin nhắc trước hay thiếu mô tả các bước). Giải pháp tăng tham số `top_k` để bù đắp Completeness lại không đem đến hiệu quả ngoạn mục như kỳ vọng ban đầu.

## 4. Kết luận

- Pipeline Hybrid Retrieval thật sự hiệu quả với dữ liệu mang tính tài liệu chính sách/kỹ thuật nhưng nó lại đòi hỏi mức độ chỉnh chu tương đương đối với Generation Prompt. Việc lựa chọn Prompt và RAG model sẽ ảnh hưởng rất lớn đến độ dứt khoát của đầu ra.
- Nếu mô hình và prompt hướng về phía quá "an toàn", câu trả lời chắc chắn "sống bám" theo chunk hiện tại nhưng dẫn đến việc thất thoát thông tin trong chuỗi hỏi đáp có 3-4 yêu cầu song song. Nhìn chung, tối ưu RAG đòi hỏi quá trình Evaluation Loop tỉ mỉ trên từng cụm test question để tìm ra bottleneck chuẩn nhất thay vì phán đoán lý thuyết.

## 5. Hướng phát triển tiếp theo

Từ các phân tích kết quả, nhóm đề xuất hai nâng cấp hệ thống ưu tiên nếu có thêm thời gian:

1. **Sử dụng Cross-Encoder Reranker:** Gắn Reranker ngay sau bước Hybrid Retrieval thay vì lấy chay Top-K để tăng tuyệt đối Precision cho Top-3 chunk đưa vào trong prompt, đảm bảo chunk ngữ nghĩa đậm đặc nằm sát trên cùng.
2. **Kỹ thuật Cấu trúc hóa Prompt (Slot-based / Checklist-based Generation):** Ép LLM phải bóc tách mục tiêu thành checklist từng ý (chẳng hạn: "xác định khả năng cấp quyền", "đủ thời gian xử lý", "người tiếp nhận") rồi mới trả lời. Điều này sẽ trực tiếp giúp tăng chỉ số Completeness (không thiếu vế) mà vẫn giữ được chuẩn Faithfulness cao.
