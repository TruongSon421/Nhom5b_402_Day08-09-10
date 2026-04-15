# Báo cáo cá nhân — Sprint 1 & Sprint 4

**Họ và tên:** Trần Thương Trường Sơn  
**Vai trò:** Data contract & chuẩn hóa tài liệu kỹ thuật  
**Ngày nộp:** 15/04/2026

---

## 1. Tôi phụ trách phần nào?

Trong Sprint 1, tôi phụ trách phần chuẩn hóa đầu vào dữ liệu và thống nhất thuật ngữ giữa các thành viên để tránh hiểu sai khi triển khai pipeline. Tôi rà lại các trường dữ liệu đang dùng trong nhóm, đề xuất tên cột nhất quán, định nghĩa kiểu dữ liệu và quy tắc đặt giá trị thiếu.

Trong Sprint 4, tôi tập trung viết tài liệu `data_contract.md` để chốt lại các ràng buộc dữ liệu ở mức cam kết giữa producer và consumer. Tôi viết rõ schema, quy tắc validate, điều kiện bắt buộc cho từng field, và các trường hợp dữ liệu không hợp lệ phải đưa vào quarantine. Nhờ đó nhóm có một nguồn tham chiếu duy nhất, giảm tranh luận khi debug.

**File / module:**
- `day10/lab/data_contract.md`
- `day10/lab/reports/individual/tranthuongtruongson.md`

**Kết nối với thành viên khác:**  
Tôi làm việc với bạn phụ trách ingestion để map đúng field nguồn vào contract, và phối hợp với bạn làm expectation để bảo đảm các rule kiểm tra bám đúng định nghĩa trong contract.

---

## 2. Một quyết định kỹ thuật

Quyết định kỹ thuật tôi tập trung trong Sprint 1 là cách chuẩn hóa schema ngay từ bước ingest, cụ thể là chọn mô hình map tường minh giữa cột nguồn và cột chuẩn trong `data_contract.md` thay vì xử lý linh hoạt theo từng file raw.

Lý do là dữ liệu đầu vào có thể khác nhau về tên cột hoặc cách ghi giá trị thiếu. Nếu không chốt map từ đầu, mỗi lần chạy hoặc mỗi người xử lý sẽ dễ hiểu khác nhau, dẫn đến kết quả không ổn định. Vì vậy tôi ưu tiên thống nhất rõ: trường nào là bắt buộc, trường nào có thể để trống, và trường nào cần chuẩn hóa trước khi đi tiếp.

Quyết định này giúp phần ingest ở Sprint 1 có tiêu chuẩn kiểm tra rõ ràng hơn, giảm việc sửa đi sửa lại khi cả nhóm phối hợp. Đồng thời đây cũng là nền cho các sprint sau, vì mọi bước clean/validate đều dựa trên schema đã thống nhất từ đầu.

---

## 3. Một lỗi hoặc anomaly đã xử lý

Lỗi tôi gặp trong quá trình làm là phần định nghĩa dữ liệu ban đầu còn chung chung, nên khi đọc lại dễ hiểu khác nhau giữa các thành viên. Điều này làm việc trao đổi ở Sprint 1 chậm hơn vì phải hỏi lại nhiều lần về ý nghĩa field và điều kiện bắt buộc.

Tôi xử lý bằng cách sửa trực tiếp `data_contract.md`: viết lại phần mô tả field rõ ràng hơn, thống nhất tên gọi, và thêm ghi chú cách hiểu cho các trường dễ nhầm. Sau khi chỉnh, việc review trong nhóm thuận hơn vì mọi người dựa vào cùng một tài liệu thay vì diễn giải theo thói quen cá nhân.

Bài học tôi rút ra là với pipeline dữ liệu, lỗi "không rõ định nghĩa" tuy không phải lỗi code runtime nhưng ảnh hưởng lớn đến tốc độ triển khai và chất lượng phối hợp nhóm. Vì vậy tôi ưu tiên làm rõ contract sớm ngay từ Sprint 1 và hoàn thiện lại ở Sprint 4.

---

## 4. Bằng chứng trước / sau

**Trước khi chuẩn hóa `data_contract.md`:**
- Nhiều comment review tập trung vào việc "field này có bắt buộc không?"
- Cùng một mẫu dữ liệu nhưng kết luận pass/fail chưa đồng nhất giữa các thành viên.

**Sau khi hoàn thiện `data_contract.md` ở Sprint 4:**
- Mọi người dùng chung một định nghĩa schema và rule validate để đối chiếu.
- Quá trình kiểm tra dữ liệu nhanh hơn vì chỉ cần so theo contract, không phải trao đổi lại từ đầu.

Bằng chứng rõ nhất là các buổi review sau đó tập trung vào fix đúng lỗi dữ liệu cụ thể thay vì tranh luận định nghĩa. Điều này cho thấy tài liệu contract đã đóng vai trò single source of truth đúng mục tiêu ban đầu.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ bổ sung bảng Error Code Mapping trong `data_contract.md` để mỗi loại vi phạm có mã lỗi cố định (ví dụ `DC001`, `DC002`). Việc này giúp log dễ lọc hơn, hỗ trợ thống kê lỗi theo tuần và giúp nhóm ưu tiên xử lý các lỗi xuất hiện nhiều nhất.
