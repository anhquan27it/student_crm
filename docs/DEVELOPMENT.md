# Phát triển và kiểm thử

## Cấu trúc

App cài trực tiếp từ root repository bằng `bench get-app`. Package Python `student_crm/` chứa module `Student Crm`, 16 DocType, controllers, API và migrations. `install.py` tạo Custom Field và chỉ mục trên site khi install/migrate; không cần sao chép schema từ máy tác giả.

Frontend ES modules trong `frontend/public/`, Node server trong `frontend/server.mjs`. Trình duyệt gọi API cùng origin; proxy chuyển cookie và CSRF đến đúng site Frappe từ `.env`. Không tắt CSRF hoặc bật wildcard CORS. Proxy chặn `/api/resource/*` và chỉ cho các method đã allowlist.

Các nhóm API:

| Module | Chức năng |
| --- | --- |
| `student_crm.api` | `get_session_roster`, `submit_bulk_attendance`, `get_advisor_dashboard` |
| `student_crm.portal` | Login context, lớp/buổi, sinh viên, danh mục, cấu hình, cảnh báo và can thiệp |
| `student_crm.support` | Hồ sơ hỗ trợ, chuyển cố vấn, đối chiếu điểm danh, thông báo, báo cáo |
| `student_crm.experience` | Học kỳ và dashboard theo vai trò, đếm thông báo |

Các method seed, migration và service nội bộ không được whitelist. Không cấp CRUD rộng cho tài khoản Website; scope dựa trên hồ sơ Faculty Member/Student và phân công hiện tại.

## Thay đổi và cập nhật

Trong bench của mỗi người:

```bash
cd ~/frappe-bench/apps/student_crm
git switch -c ten-tinh-nang
# Sửa code, kiểm thử, commit và tạo pull request vào main.
```

Muốn cập nhật từ main, commit/cất các thay đổi của mình trước, rồi:

```bash
cd ~/frappe-bench/apps/student_crm
git switch main
git pull --ff-only
cd ../..
bench --site studentcrm.local backup
bench --site studentcrm.local migrate
```

Khởi động lại `bench start` khi thay hooks/Python và `npm start` khi thay `.env` hoặc server proxy. Không chạy lại seed để đồng bộ code.

## Kiểm tra source

```bash
cd ~/frappe-bench/apps/student_crm
npm run check --prefix frontend
npm test --prefix frontend
python3 scripts/check_package.py
```

GitHub Actions chạy các lệnh frontend và kiểm tra cấu trúc/syntax backend. Integration tests dưới đây cần một site test cài app thật; CI source không thay thế chúng.

## Backend integration tests

Từ **thư mục bench**, dùng Python trong venv của Bench:

```bash
cd ~/frappe-bench
env/bin/python apps/student_crm/scripts/run_backend_tests.py --site studentcrm.local
```

Chỉ dùng site dành cho test/demo. Runner chạy 50 tests và rollback; không commit fixture. Nó tạm bỏ giới hạn tạo User trong riêng process test để tạo fixture, không sửa cấu hình web. Các test tạo tài khoản/record giả rồi rollback; Administrator password hiện có không bị thay đổi.

## HTTP smoke test cho bộ demo portable

Giữ `bench start` chạy trước. Test tự mở Node proxy trên một cổng loopback trống và đóng sau khi xong. Trong Ubuntu, chạy từ thư mục app:

```bash
cd ~/frappe-bench/apps/student_crm
printf '%s\n' '{"site":"studentcrm.local","password":"Student@123"}' | node frontend/tests/demo-live.mjs
```

Đây là credential demo công khai; nếu dùng mật khẩu riêng, truyền JSON bằng stdin từ nơi quản lý credential, không commit hoặc dán mật khẩu thật vào mã nguồn. Test đọc dữ liệu, kiểm tra đăng nhập/phân quyền/CSRF và gửi lại đúng roster đã chốt để xác minh idempotency, không thay trạng thái điểm danh. Test này dành cho bộ seed portable 15 lớp/100 sinh viên; không áp dụng số đếm của nó cho database tùy chỉnh.

## Biên nghiệp vụ cần giữ

- Tổng 20 slot, `Absent` mới tính vắng; `Late` không phải vắng; không có `Excused`.
- `>20%` mới Barred: không đổi thành `>=20%`.
- Chỉ tính các buổi đã chốt và sinh viên đăng ký hợp lệ.
- Khi sửa điểm danh phải kiểm tra phiên bản, cập nhật thống kê và cảnh báo trong cùng transaction.
- Yêu cầu sửa phải được giảng viên phụ trách hoặc quản trị duyệt; sinh viên không tự duyệt.
- Không để API của cố vấn xem sinh viên đã chuyển sang cố vấn khác; không lộ ghi chú hỗ trợ riêng cho sinh viên.
- Không commit `.env`, mật khẩu quản trị, API key, dữ liệu thực, backup, cache hoặc session.

Giấy phép và tác giả gốc được giữ nguyên trong repository. Frontend không có dependency runtime bên ngoài để cài bằng npm.
