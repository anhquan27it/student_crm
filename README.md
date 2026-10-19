# Student CRM — Điểm danh và cảnh báo sớm

Backend **Frappe v16** và Website tiếng Việt cho quản lý chuyên cần sinh viên đại học. Clone repository này để cài trên Ubuntu/WSL của bạn; không cần database, tài khoản Ubuntu hay mật khẩu Administrator từ máy tác giả.

**Hướng dẫn đầy đủ:** [Cài đặt Ubuntu / WSL](docs/INSTALL_UBUNTU.md) · [Dữ liệu và tài khoản mẫu](docs/DEMO_DATA.md) · [Kiến trúc và API](docs/DEVELOPMENT.md).

## Cài nhanh khi đã có Frappe v16

Trong terminal Ubuntu, thay `~/frappe-bench` bằng đường dẫn bench của bạn. Dùng site mới để thử nghiệm:

```bash
cd ~/frappe-bench
bench new-site studentcrm.local
bench get-app --branch main https://github.com/anhquan27it/student_crm.git
bash apps/student_crm/scripts/setup.sh studentcrm.local
bench --site studentcrm.local execute student_crm.demo.seed
```

`new-site` hỏi mật khẩu quản trị MariaDB và cho bạn tự đặt mật khẩu Administrator Frappe. Nếu site đã tồn tại, bỏ bước tạo site và bảo đảm đó là site dành cho dự án này. Nếu app đã nằm trong bench, bỏ `get-app`.

Mở hai terminal và giữ chúng chạy:

```bash
# Terminal 1
cd ~/frappe-bench
bench start
```

```bash
# Terminal 2
cd ~/frappe-bench/apps/student_crm/frontend
npm start
```

Mở **http://127.0.0.1:5173** bằng trình duyệt Ubuntu hoặc Windows khi dùng WSL2. Không cần `npm install`: frontend chỉ dùng Node.js chuẩn.

## Tài khoản mẫu

Sau khi chạy seed trên site mới, các tài khoản dưới đây có mật khẩu demo **`Student@123`**:

| Vai trò | Tài khoản |
| --- | --- |
| Cố vấn học tập | `demo.crm.faculty01@example.com` |
| Giảng viên | `demo.crm.faculty04@example.com` |
| Sinh viên | `demo.crm.student001@example.com` |
| Sinh viên ở mức 20% | `demo.crm.student010@example.com` |
| Sinh viên bị cấm thi | `demo.crm.student013@example.com` |
| Quản trị | `Administrator` — mật khẩu tự đặt khi tạo site |

Đây là mật khẩu công khai chỉ dành cho demo local. Có thể chọn mật khẩu khác bằng biến môi trường `CRM_DEMO_PASSWORD` trước lần seed đầu tiên. Seed không đổi mật khẩu Administrator và không tạo admin mẫu.

## Chức năng

- Quản trị: quản lý sinh viên, khoa/ngành, học kỳ, lớp học phần, buổi học, đăng ký học, ngưỡng cảnh báo và chất lượng dữ liệu.
- Giảng viên: xem lớp được phân công, điểm danh hàng loạt, sửa theo phiên bản và duyệt yêu cầu đối chiếu.
- Cố vấn: phát hiện sinh viên rủi ro, xử lý cảnh báo, ghi nhật ký can thiệp, quản lý hồ sơ hỗ trợ và hiệu quả theo dõi.
- Sinh viên: xem chuyên cần, cảnh báo và liên hệ cố vấn; gửi yêu cầu sửa điểm danh.
- Phân quyền tại API; cookie phiên, CSRF; thông báo trong ứng dụng; giao diện cam/trắng responsive.

## Quy tắc và dữ liệu

Mỗi lớp học phần có **20 slot**. Chỉ `Absent` tính vắng; `Late` vẫn tính có mặt. **Vắng >20% mới cấm thi:** 4/20 là Critical, 5/20 là Barred. Không có trạng thái nghỉ có phép. Cảnh báo hành vi phát hiện vắng liên tiếp qua nhiều môn trong cửa sổ thời gian.

Seed tạo **100 sinh viên, 8 giảng viên/cố vấn, 15 môn đã yêu cầu, 15 lớp học phần, 300 buổi học, 500 đăng ký và 4.000 điểm danh**, cùng cảnh báo, hồ sơ hỗ trợ, lịch sử cố vấn, nhật ký can thiệp và thông báo. Tất cả là dữ liệu giả lập. Ngày học đặt tương đối theo ngày seed; chạy lại không tạo trùng hoặc đặt lại mật khẩu.

```text
student_crm/        App Frappe: 16 DocType, controller, API, migrations, seed, tests
frontend/          Website và Node proxy cùng origin
scripts/           Setup, kiểm tra package và chạy backend tests
docs/              Hướng dẫn cho thành viên dự án
.github/workflows/ Kiểm tra source tự động khi push / pull request
```

## Kiểm tra

```bash
cd ~/frappe-bench/apps/student_crm
npm run check --prefix frontend
npm test --prefix frontend
python3 scripts/check_package.py
```

Backend và HTTP thực tế cần Frappe đang chạy; xem [DEVELOPMENT.md](docs/DEVELOPMENT.md). CI trong GitHub kiểm tra frontend và cấu trúc/syntax Python; không giả định đã chạy integration tests với database.

Bản đóng gói đã được kiểm tra cài mới, seed và migrate: [kết quả kiểm thử](docs/RELEASE_CHECKS.md).

Repo không chứa `.env`, session, database backup hoặc dữ liệu sinh viên thật. Môi trường mặc định chạy local; triển khai Internet cần cấu hình server/HTTPS và đổi thông tin đăng nhập demo trước.

Giấy phép: [MIT](license.txt).
