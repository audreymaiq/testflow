# ADR-025 — Tên chuẩn môn, trường và ngành theo luồng tự phục vụ

**Trạng thái:** chấp nhận cho R1; cập nhật theo quyết định của chủ sản phẩm ngày 2026-11-05. Quy trình Admin duyệt từng tên trong phiên bản đầu của ADR này đã được thay thế.

Môn, trường và ngành được lưu bằng bản ghi chuẩn trong DB. Người dùng tra cứu trước khi dùng tên: nếu đã có bản ghi, giao diện chọn tên chuẩn đó. Khi không có kết quả đúng, người dùng chủ động bấm **Tạo tên mới**; API tạo bản ghi chuẩn ngay và trả về cùng một định danh để dùng trong hồ sơ hoặc đề. Không có hàng đợi duyệt tên của Admin. Việc xuất bản đề vẫn tuân theo quy trình duyệt riêng.

Khóa so khớp chắc chắn dùng Unicode NFC, `casefold` và bỏ khoảng trắng thừa, nhưng **giữ dấu**. `toán học`, `TOÁN HỌC` và ` toán  Học ` cùng một khóa và một bản ghi. `Mẫu` và `Máu` khác khóa. Tên thiếu dấu hoặc sai chính tả chỉ tạo gợi ý dựa trên độ tương tự; người dùng phải chọn gợi ý hoặc bấm tạo tên mới. Hệ thống không tự gộp hai tên gần giống vì có thể là hai thực thể khác nhau. Do đó luồng này giảm tải duyệt thủ công nhưng không bảo đảm loại bỏ mọi bản ghi sai chính tả. Nếu về sau cần gộp dữ liệu, đó phải là thao tác quản trị có kiểm toán riêng.

`POST /api/v1/taxonomy/names/` yêu cầu đăng nhập và giới hạn tần suất. Với khóa đã có, API trả bản ghi hiện hữu (`200`); với khóa mới, API tạo Subject/School/Major, alias duy nhất `(kind, key)` và bản ghi `TaxonomyProposal(APPROVED)` với lý do `SELF_SERVICE` để lưu nguồn gốc (`201`). Toàn bộ thao tác nằm trong transaction. Xung đột tạo đồng thời được giải quyết bằng ràng buộc duy nhất và đọc lại bản ghi thắng; dữ liệu cũ có nhiều đích cùng khóa không được đoán để tránh liên kết sai. Mã Subject được tạo ổn định từ tên và hash, không cần người dùng đặt mã. Subject có thể khai báo `has_formula` khi tạo.

`create_exam` chỉ liên kết với tên đã có trong danh mục, nên không tự sinh School/Major từ chuỗi metadata. Bản nháp TXT có thể giữ tên thô cho đến bước người dùng xác nhận. Hồ sơ `User.school` vẫn là trường văn bản để tránh phụ thuộc vòng giữa Accounts và Catalog; API `/taxonomy/profile-school/` chỉ ghi tên chuẩn đã tra cứu/tạo, còn `PATCH /auth/me/` không sửa trường này. Dữ liệu hồ sơ cũ chưa chuẩn cần được người dùng chọn lại khi lưu.

Migration `0007_self_service_taxonomy` chuyển các đề xuất PENDING cũ thành bản ghi chuẩn hoặc liên kết với bản ghi hiện hữu, giữ nguyên bản ghi kiểm toán. Trường hợp tên Subject quá dài hoặc dữ liệu cũ mơ hồ sẽ được đánh dấu `SELF_SERVICE_REENTER_REQUIRED` để người dùng nhập lại; không tự đoán đích.

Kiểm chứng: `backend/tests/test_catalog.py` bao phủ chuẩn hóa chữ hoa/khoảng trắng, tên gần giống, quyền truy cập, tạo và dùng lại tên, hồ sơ, đề và migration. `frontend/e2e/taxonomy.spec.ts` kiểm tra hai người dùng dùng chung bản ghi chuẩn qua hồ sơ và đề. Giới hạn sản phẩm: tên sai chính tả được tạo nếu người dùng cố ý chọn tạo mới sau gợi ý.
