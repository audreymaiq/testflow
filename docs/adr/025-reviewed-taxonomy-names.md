# ADR-025 — Duyệt tên môn, trường và ngành

**Trạng thái:** chấp nhận cho R1, 2026-11-05.

Tên môn, trường và ngành trong đề phải trỏ đến một bản ghi chuẩn trong DB. Người dùng được nhập tên mới, nhưng dữ liệu đó là `TaxonomyProposal(PENDING)` cho đến khi Admin xử lý. `create_exam` không còn tự tạo School/Major từ chuỗi người dùng. Môn vẫn là FK Subject có mã ổn định.

Quy tắc tra cứu chắc chắn là Unicode NFC, bỏ khoảng trắng thừa và `casefold`, **giữ dấu**. Ví dụ `toán học` và `toán Học` cùng khóa; `Mẫu` và `Máu` khác khóa. Biến thể thiếu dấu hoặc sai chính tả chỉ nhận gợi ý tương đồng, không tự gộp. Người dùng có thể chọn gợi ý hiện hữu hoặc gửi đề xuất. Admin có thể gộp đề xuất vào bản ghi chuẩn, tạo bản ghi chuẩn mới, hoặc từ chối có lý do. Bản ghi duyệt lưu người duyệt, thời gian, đích và lý do; alias có khóa duy nhất `(kind, key)` và đúng một FK đích. Một khóa chỉ có tối đa một đề xuất PENDING. Tạo/gộp được khóa transaction; xung đột trả 409.

Danh mục có sẵn được tra cứu qua tên chuẩn ngay cả khi chưa có alias. Nếu dữ liệu cũ chứa nhiều bản ghi cùng khóa, hệ thống không đoán đích; Admin phải đối soát. Quyết định tạo tên mới kiểm tra lại khóa của dữ liệu cũ. Nghiệp vụ chỉ cho dùng tên đã duyệt trong metadata đề; bản nháp TXT có thể giữ chuỗi chưa duyệt để người dùng sửa trước lúc xác nhận. Tra cứu và gửi đề xuất yêu cầu đăng nhập, có throttle riêng. Hồ sơ cá nhân `User.school` vẫn là trường văn bản của tài khoản; ADR này áp dụng cho taxonomy của đề và bộ lọc thư viện.

Kiểm chứng: `backend/tests/test_catalog.py` bao phủ biến thể chữ hoa/khoảng trắng, cặp có dấu dễ nhầm, gợi ý lỗi gõ, đề xuất trùng, phân quyền, gộp, tạo mới, tạo đề và rollback. `frontend/e2e/taxonomy.spec.ts` đi từ đề xuất của Student qua duyệt Admin đến đề có trường chuẩn.
