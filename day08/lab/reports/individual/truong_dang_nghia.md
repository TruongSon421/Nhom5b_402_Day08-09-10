# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline
**Họ và tên:** Trương Đăng Nghĩa
**Vai trò trong nhóm:** Retrieval Owner
**Ngày nộp:** 13/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này?

- Phụ trách Sprint 1  phần indexing pipeline trong `index.py`. Cụ thể là implement ba bước chính: preprocess, chunk, và embed + store. Ở bước preprocess dùng hàm `preprocess_document()` để parse metadata từ header của từng file `.txt` (Source, Department, Effective Date, Access) bằng regex, rồi tách phần header ra khỏi nội dung chính. Về phương pháp chunk data sử dụng chiến lược heading-based trước: split theo pattern `=== Section ===`, sau đó nếu section vẫn còn dài hơn `CHUNK_SIZE * 4` ký tự (~1800 chars) thì split tiếp theo paragraph với overlap 75 tokens (~300 chars). Logic overlap tôi xử lý ở `_split_by_size()` — lấy các paragraph cuối của chunk trước ghép vào đầu chunk tiếp theo để không mất thông tin ở ranh giới. Bước cuối dùng `text-embedding-3-small` embed từng chunk rồi upsert vào ChromaDB với cosine similarity. Kết quả là 29 chunks được index từ 5 tài liệu, mỗi chunk giữ đủ 5 metadata fields.

_________________
---

## 2. Điều tôi hiểu rõ hơn sau lab này

Trước đó chỉ nghĩ chunking là chia đều text theo số token, Khi làm thì mới thấy: cắt cứng theo token có thể chém ngay giữa một điều khoản, ví dụ điều kiện hoàn tiền nằm ở 3-4 câu liên tiếp nhưng bị chia ra 2 chunk — khi retrieve chỉ lấy 1 chunk thì model thiếu ngữ cảnh để trả lời đúng. Chiến lược heading-based giải quyết điều này vì nội dung cùng section thường có cùng chủ đề. 
Overlap cũng không phải cứ thêm là tốt, hiện đang set 75 tokens, đủ để giữ vài câu context nhưng không làm chunk quá dài hay trùng lặp quá nhiều. Nếu overlap quá lớn, ChromaDB sẽ return gần như cùng nội dung ở nhiều chunk khác nhau, precision giảm.

Điều quan trọng hơn là metadata — `effective_date` và `source` không chỉ để hiển thị citation mà còn là cơ sở để đánh giá freshness sau này. Lúc đầu cũng không chú ý nhiều đến field này, nhưng khi viết `inspect_metadata_coverage()` để debug thì mới thấy nếu thiếu date thì câu hỏi so sánh phiên bản (như gq01) rất dễ trả lời sai.

_________________
---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn

Cái khó nhất không phải viết code mà là kiểm tra chunk output, khi viết xong `chunk_document()` tưởng ổn, chạy `build_index()` không báo lỗi, nhưng khi gọi `list_chunks()` thì thấy một số chunk preview bắt đầu bằng dấu `===` — tức là section header bị lọt vào nội dung thay vì bị nhận diện đúng. Lý do là regex `re.split(r"(===.*?===)", text)` dùng capturing group nên header được giữ lại trong list kết quả, nhưng logic xử lý tiếp theo không nhất quán khi section đầu tiên không có heading.

Một vấn đề khác là file `policy_refund_v4.txt` có dòng tên tài liệu viết hoa toàn bộ (`CHÍNH SÁCH HOÀN TIỀN - PHIÊN BẢN 4`) nên bị lọc ra bởi điều kiện `line.isupper()` — điều này đúng với ý định nhưng lúc đầu không để ý và cứ tưởng metadata parse sai. Mất khoảng 20 phút để trace ra nguyên nhân bằng cách print từng dòng.

Ngạc nhiên là khi test xong và 29 chunks lên ChromaDB đúng hết, phần retrieval chạy context recall = 5.0/5 ngay từ baseline — không ngờ chunking theo section heading lại clean đến mức đó.

_________________
---

## 4. Phân tích một câu hỏi trong scorecard

**Câu hỏi:** gq03 — *Đơn hàng mua trong chương trình Flash Sale và đã kích hoạt sản phẩm có được hoàn tiền không?*

**Phân tích:**

Baseline trả lời đúng một phần: câu trả lời nêu đúng rằng Flash Sale + mã giảm giá đặc biệt + đã kích hoạt thì không được hoàn tiền, nhưng điểm Faithfulness chỉ 3/5 và Completeness 3/5. Lỗi nằm ở generation nhưng có nguồn gốc từ cách chunk.

Điều kiện ngoại lệ của chính sách hoàn tiền trong `policy_refund_v4.txt` nằm ở nhiều bullet points liên tiếp trong cùng một section. Khi chunk theo paragraph, có khả năng phần liệt kê các điều kiện bị chia giữa hai chunk nếu đoạn đó dài, khiến context block chỉ lấy được một phần điều kiện. Model nhìn thấy "Flash Sale + mã giảm giá" nhưng không thấy đủ các điều kiện đi kèm nên câu trả lời thiếu sót.

Bằng chứng: Variant 3 (top_k_search=15, top_k_select=5) cải thiện câu này lên 5/5/5/4 — tức là khi mở rộng context pool, cả hai chunk có nội dung liên quan đều được đưa vào prompt, generation mới đủ điều kiện để trả lời đầy đủ.

Fix đúng nhất ở tầng indexing là đảm bảo các bullet condition trong cùng một mục không bị cắt ngang. Có thể làm bằng cách tăng overlap hoặc thêm logic nhận diện list item (`-`, `*`, `•`) và không cắt trong block list.

_________________
---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì?

Thử hai cải tiến cụ thể:

1. **Không cắt chunk giữa list block** — thêm logic vào `_split_by_size()` để nhận ra khi đang ở trong một dãy bullet points và giữ nguyên cả block. Scorecard cho thấy gq03 và gq05 đều fail do thiếu một phần điều kiện trong danh sách điều khoản.

2. **Thêm `chunk_index` vào metadata** — để khi debug có thể biết chunk đó là chunk thứ mấy trong section, dễ kiểm tra xem ranh giới cắt có hợp lý không mà không cần đọc toàn bộ file gốc.

_________________

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*
*Ví dụ: `reports/individual/nguyen_van_a.md`*