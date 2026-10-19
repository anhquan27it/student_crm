# Kiểm tra bản đóng gói — 19/10/2026

Bản này đã được cài bằng `install-app` lên một site Frappe mới, chạy với một MariaDB tạm và web server riêng trong WSL. Site/database gốc không được dùng để tạo bộ seed mới.

| Kiểm tra | Kết quả |
| --- | --- |
| Fresh install đủ 16 DocType và Custom Field/chỉ mục | Đạt |
| Migrate trước khi seed | Đạt |
| Backend integration tests với rollback | 50/50 |
| Frontend unit/regression tests | 21/21 |
| HTTP trên chính site mới: vai trò, CSRF, roster, cảnh báo | 29/29 |
| Seed mới | 100 sinh viên, 15 môn/lớp, 300 buổi, 500 đăng ký, 4.000 điểm danh |
| Chạy lại seed | Audit thành công, không nhân đôi |
| Migrate sau seed | Số lượng/liên kết còn nguyên; ngưỡng 4/20 và 5/20 đúng |
| Build Python wheel | Đạt; đủ 16 schema JSON, install hook và catalog mẫu |
| Đường dẫn máy tác giả / private key / GitHub token trong tập file xuất bản | Không phát hiện |

Môi trường kiểm tra app: Frappe 16.34.0, Python 3.14.4, Node.js 24.21.0. Đây là kiểm tra cài app trên site mới trong môi trường Bench đã có sẵn, không phải kiểm thử cài lại toàn bộ Ubuntu từ đầu. Hướng dẫn cài hệ điều hành/phụ thuộc tham chiếu tài liệu chính thức được liên kết trong INSTALL_UBUNTU.md.

Sau kiểm thử, web server, database và site tạm đã được dọn. Các file `.env`, private manifest, backup, session và lịch sử triển khai chỉ dành cho máy tác giả đều được loại khỏi Git.

CI GitHub chạy kiểm tra frontend và cấu trúc/syntax backend; các integration test trong bảng này là kết quả kiểm thử thực tế trước xuất bản, không phải kết quả giả định từ CI.
