# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Bùi Lâm Tiến
**Vai trò:** Cleaning / Quality Owner (Sprint 2)
**Ngày nộp:** 15/04/2026
**Độ dài yêu cầu:** **400–650 từ**

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `transform/cleaning_rules.py`: Xây dựng thêm các quy tắc làm sạch dữ liệu (cleaning rules).
- `quality/expectations.py`: Thiết lập các bộ kiểm tra chất lượng và tính toàn vẹn của dữ liệu.

**Kết nối với thành viên khác:**
Tôi tiếp nhận dữ liệu đầu vào từ khâu Ingestion (thư mục raw), thực hiện các tác vụ gọt rửa, định dạng dữ liệu, và kiểm định chất lượng trước khi chuyển file sạch cho thành viên phụ trách Embed (Embed Owner) đưa vào Vector DB.

**Bằng chứng (commit / comment trong code):**
Tôi đã trực tiếp thiết kế và lập trình các rules và expectations sau:

- Hàm `_strip_bom()` và `_normalize_unicode()` nhằm xóa bỏ các ký tự rác tàng hình và chuẩn hóa tự động các dấu câu sai định dạng.
- Hàm `_check_excessive_whitespace()` nhằm phát hiện và cách ly các đoạn văn bản rác chứa quá nhiều khoảng trắng vô nghĩa.
- Hàm kiểm tra `_check_no_html_tags()` (loại `halt`) và `_check_effective_date_not_future()` (loại `warn`) để chủ động kiểm soát chất lượng từ dòng ban đầu.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Khi viết Data Expectations, tôi đã ra quyết định phân tầng mức độ Severity: khi nào dùng `halt` và khi nào dùng `warn`.

- Với quy tắc check mã HTML (`E7`), tôi đã cho `halt`. Nếu rác HTML lọt vào Vector DB, nó sẽ làm hỏng thuật toán truy xuất ngữ nghĩa, thậm chí tiềm ẩn rủi ro Prompt Injection làm sai lệch Agent. Do đó, ETL Pipeline buộc phải dừng ngay lập tức để bảo vệ an toàn CSDL.
- Trái lại, tôi gán nhãn `warn` cho lỗi ngày hiệu lực ở tương lai (`E8`). Thực tế vận hành, phòng HR thường xuyên đăng trước các chính sách lên hệ thống vài tuần để phổ biến. Vấn đề này chỉ được phép xuất log báo cáo cho Data Steward giám sát, tuyệt đối không được làm đứt gãy tiến trình ETL tự động hằng đêm.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Lúc chạy thử pipeline, tôi gặp một lỗi: tính năng lọc Deduplication gần như vô dụng. Các chunk nội dung dù đọc thấy giống hệt nhau vẫn bị hệ thống coi là khác biệt và lọt vào trong Vector DB.

Sau khi check kĩ lại, tôi đã phát hiện nguyên nhân xuất phát từ việc copy-paste văn bản từ file Word lên hệ thống cũ. Đoạn text bị ảnh hướng bởi các ký tự đặc thù của Word như khoảng trắng không ngắt (`\u00a0`) hay dấu ngoặc kép xoắn (`\u201c`). Nhìn bình thường thì y hệt nhau, nhưng khi chạy qua hàm băm SHA-256 thì giá trị byte khác nhau nên sinh ra mã hash khác nhau hoàn toàn.

Để fix triệt để, tôi viết thêm hàm `_normalize_unicode` chuyên ép các ký tự dị biệt kia quy chuẩn về dạng ASCII thông thường. Làm sạch được mớ này xong thì thuật toán lọc trùng mới hoạt động ngon lành trở lại.

---

## 4. Bằng chứng trước / sau (80–120 từ)

- **Trước khi chưa fix:** Chức năng loại bỏ `duplicate_chunk_text` không bắt được lỗi. Chunk bị rác khoảng trắng và HTML lọt sang khâu Embedding. Khi test mô hình, Vector DB toàn trả ra mớ context trùng lặp làm kết quả AI trả về rất nhiễu.
- **Sau khi fix (`run_id=sprint2`):** Thuật toán Deduplication hoạt động trở lại. File xuất log gặp các tag `[cleaned: unicode_normalized]` rất nhiều, không bị ảnh hưởng từ các ký tự đặc thù của Word. Các dòng bất thường được đưa vào quarantine với cờ `excessive_whitespace` tăng lên nhiều. Quan trọng nhất, rule E7 chạy `halt` ngắt ngay lập tức pipeline nếu có lỗi định dạng HTML, bảo vệ DB an toàn tuyệt đối.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu dự án cho thêm 2 giờ, hướng tối ưu hệ thống triệt để nhất của tôi là mềm hóa luật check mã nguồn HTML (`E7` halt). Thay vì phải dứt khoát khóa pipeline bỏ mặc khối dữ liệu lỗi, tôi sẽ áp dụng thư viện siêu việt `BeautifulSoup` vào `cleaning_rules.py` để chủ động bóc tách text DOM khỏi các node HTML tự động. Điều kiện trên cam kết cứu lại triệt để ngữ cảnh gốc (context), mang lại giá trị trọn vẹn nhất cho kho tàng Agentic RAG.
