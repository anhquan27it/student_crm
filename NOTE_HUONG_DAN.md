# Note bàn giao — cài Website và nạp dữ liệu mẫu Student CRM

**Repository:** https://github.com/anhquan27it/student_crm

**Cập nhật:** nếu muốn đúng toàn bộ dữ liệu máy tác giả (**121 sinh viên**, cùng nhật ký và dữ liệu cũ), làm theo [RESTORE_SAME_SITE.md](docs/RESTORE_SAME_SITE.md). Các bước seed bên dưới chỉ dành cho bộ giả lập 100 sinh viên khác, không áp dụng lên site nhận bản sao đầy đủ.

Tài liệu này dành cho thành viên muốn chạy dự án trên **Ubuntu hoặc Ubuntu trong WSL2 của mình**, với Frappe/database riêng. Làm lần lượt từ trên xuống. Mọi lệnh Bash bên dưới chạy trong terminal Ubuntu, không chạy trong PowerShell.

## 1. Dữ liệu mẫu trên GitHub được lưu như thế nào?

GitHub chứa schema DocType, code backend/frontend và **code tạo dữ liệu mẫu**:

- `student_crm/demo.py`: tạo tài khoản, sinh viên, lớp, buổi học và điểm danh qua controller Frappe.
- `student_crm/demo_data/catalog.json`: danh sách môn học và thông tin mẫu để sinh dữ liệu.
- `student_crm/install.py`: khởi tạo các trường bổ sung và chỉ mục cần thiết khi cài app/migrate.

`git clone`, `git pull` hoặc `bench get-app` **chưa đưa bản ghi vào database**. Phải cài app lên đúng site và chạy lệnh seed ở bước 5.

Bộ seed dựng lại dữ liệu giả lập trên máy của bạn. Nó không phải bản sao y nguyên database của máy tác giả; dữ liệu cũ hoặc dữ liệu tự nhập bên máy tác giả không được mang theo. Không cần xin file SQL, tài khoản Ubuntu hay mật khẩu Administrator của tác giả.

## 2. Chuẩn bị và xác định đúng thư mục

Cần một bench Frappe **v16.34+ thuộc v16**, Python 3.14 và Node.js 24. Chưa có Ubuntu/Frappe: làm theo [INSTALL_UBUNTU.md](docs/INSTALL_UBUNTU.md) trước, sau đó quay lại đây.

Ví dụ bên dưới giả định:

| Thành phần | Giá trị ví dụ |
| --- | --- |
| Thư mục bench | `~/frappe-bench` |
| Site demo riêng | `studentcrm-demo.local` |
| Backend | `http://127.0.0.1:8000` |
| Website | `http://127.0.0.1:5173` |

Nếu bench của bạn là `~/frappe/frappe-bench`, thay **mọi** `~/frappe-bench` trong tài liệu bằng đường dẫn đó. Tên site có thể khác, nhưng phải dùng nhất quán trong lệnh seed, migrate và `.env`.

```bash
cd ~/frappe-bench
pwd
ls apps sites env
bench version
env/bin/python --version
node --version
```

Thư mục bench phải có `apps/`, `sites/`, `env/`. Thư mục Git của app sau khi tải là `apps/student_crm/`, không phải một bench thứ hai.

## 3. Tải app từ GitHub

Đứng trong thư mục bench:

```bash
cd ~/frappe-bench
bench get-app --branch main https://github.com/anhquan27it/student_crm.git
```

Nếu đã có `apps/student_crm`, không chạy lại `get-app`. Kiểm tra code đang có:

```bash
cd ~/frappe-bench/apps/student_crm
git remote -v
git status
```

Nếu đúng repository và không có thay đổi cần giữ, cập nhật:

```bash
git pull --ff-only
```

Nếu có thay đổi chưa commit, giữ/commit chúng trước; không dùng reset hoặc xóa thư mục để ép cập nhật. Nên dùng `bench get-app` thay vì tải ZIP vì Bench còn cài package Python cho app.

## 4. Tạo site demo và cài app

Dùng một site mới để tránh trộn dữ liệu demo với dự án khác:

```bash
cd ~/frappe-bench
bench new-site studentcrm-demo.local
```

Lệnh hỏi các mật khẩu:

| Mật khẩu | Ý nghĩa |
| --- | --- |
| Database root/admin password | Mật khẩu quản trị MariaDB trên máy bạn để tạo database |
| Administrator password | Mật khẩu **bạn tự đặt** cho tài khoản quản trị Frappe của site mới |
| `Student@123` | Mật khẩu tài khoản mẫu sau khi seed; không tự áp dụng cho hai loại trên |

Nếu site này đã tồn tại và đúng là site test dành cho Student CRM, bỏ lệnh tạo site. Không dùng `--force` hoặc `reinstall` để vượt lỗi site đã tồn tại.

Cài app và đồng bộ schema:

```bash
cd ~/frappe-bench
bash apps/student_crm/scripts/setup.sh studentcrm-demo.local
bench --site studentcrm-demo.local list-apps
```

Danh sách app cần có `frappe` và `student_crm`. Script tự install app nếu thiếu, chạy migrate và tạo `frontend/.env` khi chưa có. Không cần tạo thủ công 16 DocType trong giao diện Frappe.

Nếu cần làm thủ công thay script, chỉ chạy `install-app` khi app chưa được cài trên site:

```bash
bench --site studentcrm-demo.local install-app student_crm
bench --site studentcrm-demo.local migrate
```

## 5. Nạp dữ liệu mẫu vào database Frappe của bạn

Đây là bước thực sự tạo các bản ghi trong database:

```bash
cd ~/frappe-bench
bench --site studentcrm-demo.local execute student_crm.demo.seed
```

Đợi lệnh chạy xong và trả về `passed: true`; không đóng terminal giữa chừng. Lần đầu tạo hàng nghìn bản ghi nên có thể mất vài phút tùy máy.

Kiểm tra sau khi tạo:

```bash
bench --site studentcrm-demo.local execute student_crm.demo.verify
```

Các trường chính trong kết quả cần tương ứng:

```json
{
  "passed": true,
  "students": 100,
  "courses": 15,
  "offerings": 15,
  "sessions": 300,
  "enrollments": 500,
  "attendance": 4000
}
```

Kết quả thực tế còn có ngày neo dữ liệu và phân bố sinh viên theo cố vấn. Ngày neo là ngày seed trên máy bạn.

### Sau seed có những gì?

| DocType / dữ liệu | Kết quả |
| --- | --- |
| Department | 1 khoa mẫu |
| Program | 3 chương trình |
| Academic Term | 1 học kỳ mẫu |
| Course | 15 môn trong danh sách dự án |
| Faculty Member | 3 cố vấn và 5 giảng viên |
| Student | 100 sinh viên giả lập |
| Course Offering | 15 lớp học phần, mỗi lớp 20 slot |
| Class Session | 300 buổi, trong đó 120 buổi đã chốt |
| Student Course Enrollment | 500 đăng ký học; mỗi sinh viên 5 môn |
| Student Attendance | 4.000 bản ghi; mỗi sinh viên 40 bản ghi |
| Student Warning | Cảnh báo theo môn và hành vi, sinh tự động từ điểm danh |
| Student Support Case | Hồ sơ hỗ trợ liên quan tới cảnh báo |
| Advisor Assignment | Lịch sử phân công cố vấn |
| Intervention Log | Các lần liên hệ/can thiệp mẫu |
| CRM Settings | Cấu hình ngưỡng mặc định |
| Attendance Correction Request | Ban đầu trống; thử gửi yêu cầu qua Website ở bước 8 |
| User / Notification Log | Tài khoản đăng nhập và thông báo trong ứng dụng |

Ba cố vấn phụ trách lần lượt 34, 33, 33 sinh viên. `User` và `Notification Log` là DocType có sẵn của Frappe, không nằm trong 16 DocType riêng của app.

### Có chạy lại seed được không?

Có, khi lần seed trước đã hoàn tất: lệnh đọc manifest và kiểm tra dữ liệu, không tạo thêm 100 sinh viên hoặc reset password. Nó cũng không khôi phục các điểm danh mà bạn đã chủ động sửa trong lúc thử.

Manifest nằm tại:

```text
sites/studentcrm-demo.local/private/student_crm_demo/manifest.json
```

Không xóa/sửa manifest để ép seed lại. Nếu báo namespace đã có nhưng thiếu manifest, dùng một site demo mới hoặc phục hồi manifest đúng site từ backup. Đặc biệt, site đang chạy trên máy tác giả có bộ mẫu từ các lần triển khai trước; không cần và không nên ép seed portable đè lên bộ đó.

Muốn làm lại từ đầu trên máy bạn: tạo site khác, ví dụ `studentcrm-demo2.local`, cài app, seed và đổi `FRAPPE_SITE` sang site mới. Không cần xóa site cũ.

## 6. Kết nối Website với đúng site

Mở cấu hình frontend:

```bash
cd ~/frappe-bench/apps/student_crm/frontend
# Nếu chưa có .env thì tạo từ file mẫu; giữ nguyên file đã có.
if [ ! -f .env ]; then cp .env.example .env; fi
nano .env
```

Đặt đúng các giá trị sau:

```dotenv
PORT=5173
HOST=127.0.0.1
FRAPPE_URL=http://127.0.0.1:8000
FRAPPE_SITE=studentcrm-demo.local
```

Trong nano: `Ctrl+O` → Enter để lưu, `Ctrl+X` để thoát. Nếu chạy setup cho nhiều site, script giữ nguyên `.env` đã tồn tại, nên phải kiểm tra lại dòng `FRAPPE_SITE`.

Mở **hai terminal Ubuntu**:

```bash
# Terminal 1: backend Frappe và các tiến trình của bench
cd ~/frappe-bench
bench start
```

```bash
# Terminal 2: Website
cd ~/frappe-bench/apps/student_crm/frontend
npm start
```

Mở **http://127.0.0.1:5173** trên trình duyệt. Không cần `npm install`. Giữ hai terminal hoạt động; muốn dừng dùng `Ctrl+C` tại từng terminal.

Sau mỗi lần sửa `.env`, dừng rồi chạy lại `npm start`. Chỉ tải lại trình duyệt không làm Node đọc lại cấu hình.

## 7. Tài khoản đăng nhập

Mật khẩu mặc định của các tài khoản mẫu: **`Student@123`**.

| Vai trò | Email |
| --- | --- |
| Cố vấn 1 | `demo.crm.faculty01@example.com` |
| Cố vấn 2 | `demo.crm.faculty02@example.com` |
| Cố vấn 3 | `demo.crm.faculty03@example.com` |
| Giảng viên 1 | `demo.crm.faculty04@example.com` |
| Giảng viên còn lại | `demo.crm.faculty05@example.com` đến `demo.crm.faculty08@example.com` |
| Sinh viên | `demo.crm.student001@example.com` đến `demo.crm.student100@example.com` |
| Quản trị | `Administrator`, dùng mật khẩu tự đặt tại bước 4 |

Nút chọn vai trò trên màn hình đăng nhập chỉ điền email. Tự nhập password vào ô mật khẩu. Website không tự lưu mật khẩu mẫu.

Nếu đã chọn `CRM_DEMO_PASSWORD` riêng trước lần seed đầu, dùng mật khẩu riêng đó. Chạy lại seed không chuyển nó về `Student@123`. Cách chọn mật khẩu demo riêng được ghi ở [DEMO_DATA.md](docs/DEMO_DATA.md).

## 8. Các luồng nên thử sau khi cài

### A. Xem chuyên cần và ngưỡng cấm thi

Lần lượt đăng nhập các tài khoản dưới đây, mở tổng quan hoặc Hồ sơ của tôi:

| Sinh viên | Tình huống kỳ vọng ở môn đầu |
| --- | --- |
| `demo.crm.student001@example.com` | Good, chuyên cần ổn định |
| `demo.crm.student004@example.com` | Warning, vắng 2/20 |
| `demo.crm.student007@example.com` | Critical, vắng 3/20 |
| `demo.crm.student010@example.com` | Critical, vắng đúng 4/20 = 20%, chưa cấm thi |
| `demo.crm.student013@example.com` | Barred, vắng 5/20 = 25% |
| `demo.crm.student016@example.com` | Cảnh báo hành vi do vắng liên tiếp qua nhiều môn |
| `demo.crm.student019@example.com` | Đã sửa điểm danh và trở lại Good; có lịch sử hỗ trợ |
| `demo.crm.student022@example.com` | Đi muộn, không tính là vắng |

Mỗi môn tổng 20 slot. Chỉ `Absent` tính vào tỷ lệ vắng, không có nghỉ có phép; `Late` vẫn tính có mặt. Các trường hợp trên mô tả dữ liệu ngay sau seed; sau khi bạn sửa điểm danh, trạng thái sẽ thay đổi tương ứng.

### B. Sinh viên gửi yêu cầu → giảng viên duyệt

1. Đăng nhập `demo.crm.student013@example.com`.
2. Mở **Điểm danh của tôi**; tìm một buổi **CEA201** đang Vắng mặt.
3. Bấm **Đề nghị sửa**, chọn Có mặt, nhập lý do/minh chứng thử nghiệm rồi gửi.
4. Đăng xuất, đăng nhập `demo.crm.faculty04@example.com`.
5. Mở **Sửa điểm danh** hoặc thông báo yêu cầu vừa tạo.
6. Đọc nội dung, chọn chấp thuận hoặc từ chối, nhập ghi chú xử lý và lưu.
7. Đăng nhập lại sinh viên để kiểm tra kết quả. Nếu chấp thuận từ Vắng thành Có mặt, số slot vắng và cảnh báo được tính lại.

Sinh viên không tự duyệt; giảng viên chỉ được duyệt buổi do mình phụ trách. Trong dữ liệu ban đầu, sinh viên 013 vắng 5/20 môn CEA201; sửa đúng một slot Vắng thành Có mặt sẽ còn 4/20, chuyển từ Barred về Critical.

### C. Cố vấn liên hệ và ghi nhật ký hỗ trợ

1. Đăng nhập `demo.crm.faculty01@example.com`.
2. Mở Tổng quan, Cảnh báo sớm hoặc Hồ sơ hỗ trợ.
3. Chọn một sinh viên còn rủi ro, xem chi tiết cảnh báo.
4. Nhập nội dung liên hệ, kết quả, kế hoạch và lịch theo dõi; lưu nhật ký.
5. Kiểm tra Nhật ký can thiệp, tiến độ hồ sơ và Hiệu quả hỗ trợ.

Đóng hồ sơ hỗ trợ chỉ ghi nhận kết quả xử lý; không tự xóa số buổi vắng hoặc miễn cấm thi.

### D. Giảng viên điểm danh

1. Đăng nhập `demo.crm.faculty04@example.com`.
2. Mở **Lịch học & điểm danh**, chọn lớp/buổi được phân công.
3. Thử tìm tên sinh viên hoặc lọc chưa điểm danh.
4. Đặt trạng thái Có mặt/Vắng mặt/Đi muộn cho đủ danh sách rồi lưu/chốt.
5. Khi sửa buổi đã chốt, hệ thống kiểm tra phiên bản và tính lại cảnh báo.

Seed đã chốt 8 buổi quá khứ mỗi lớp, các buổi còn lại ở tương lai. Không thể chốt buổi tương lai; để thử ngay, dùng một buổi quá khứ đã chốt và sửa có chủ ý trên **site demo**. Các lượt thử ghi dữ liệu làm thay đổi kết quả mẫu, không ảnh hưởng máy tác giả hay thành viên khác.

### E. Quản trị và phân công

Đăng nhập Administrator của site bạn → kiểm tra Sinh viên, Danh mục hệ thống và Cấu hình cảnh báo. Có thể thêm sinh viên hoặc phân công cố vấn. Tạo một hồ sơ Student mới không tự tạo tài khoản đăng nhập; cần tạo User trong Frappe và gắn vào hồ sơ khi muốn người đó đăng nhập.

## 9. Cập nhật code khi nhóm có thay đổi

Giữ/commit thay đổi riêng trước khi pull, sau đó:

```bash
cd ~/frappe-bench/apps/student_crm
git status
git pull --ff-only
cd ../..
bench --site studentcrm-demo.local backup
bench --site studentcrm-demo.local migrate
```

Khởi động lại backend/frontend khi cần, rồi `Ctrl+F5` trên trình duyệt. **Không cần seed lại mỗi lần pull code.** Các thành viên dùng database riêng; điểm danh, User và dữ liệu nhập trong Frappe không tự đồng bộ qua GitHub.

Không đưa `.env`, `sites/`, `site_config.json`, manifest riêng, mật khẩu quản trị, session hoặc backup SQL lên Git. Repo đã có `.gitignore` cho các dữ liệu vận hành phổ biến.

## 10. Kiểm tra khi gặp lỗi

| Lỗi / dấu hiệu | Kiểm tra và xử lý |
| --- | --- |
| Tải code xong nhưng chưa có sinh viên | Chạy `install-app`/setup, sau đó seed **đúng site** |
| Đăng nhập được nhưng thấy dữ liệu khác | Kiểm tra `FRAPPE_SITE`, site đã seed, khởi động lại `npm start` |
| Backend đang cố định một site khác | Có thể chạy web riêng: từ bench chạy `bench --site studentcrm-demo.local serve --port 8001`, đổi `FRAPPE_URL=http://127.0.0.1:8001` rồi khởi động lại frontend; giữ các tiến trình bench cần thiết cho scheduler/workers |
| 502 / không kết nối backend | Kiểm tra `bench start` còn chạy, cổng web đúng với `FRAPPE_URL` |
| `bench: command not found` | Mở terminal mới hoặc nạp lại PATH của Bench/uv như hướng dẫn cài đặt |
| `No such command new-site` | Chưa đứng trong thư mục bench hoặc init bench chưa thành công |
| MariaDB Access denied | Dùng mật khẩu quản trị DB của chính máy bạn; xem hướng dẫn tài khoản DB trong INSTALL_UBUNTU.md |
| `ModuleNotFoundError: student_crm` | App chưa được cài vào môi trường Bench; kiểm tra đã dùng `bench get-app` đúng bench |
| Thiếu `support_case` / `crm_event_key` | Chạy migrate cho site, khởi động lại backend sau khi cập nhật hooks |
| Password demo không đăng nhập được | Kiểm tra seed hoàn tất, đúng site, email đủ 3 chữ số sinh viên và có dùng password tùy chỉnh hay không |
| Seed báo namespace có sẵn / thiếu manifest | Không ép ghi đè. Dùng site demo mới hoặc phục hồi manifest đúng site |
| `verify` báo lệch số lượng sau khi tự thử | Đối chiếu dữ liệu đã thêm/xóa; không seed để ghi đè. Tạo site mới nếu cần bộ sạch |
| Sinh viên chỉ thấy dữ liệu cá nhân, cố vấn chỉ thấy 34/33 sinh viên | Đây là phân quyền đúng; Administrator mới có phạm vi toàn site |
| Cảnh báo hành vi cũ hết hiệu lực | Đúng theo cửa sổ theo dõi; ngày seed và thời gian thực ảnh hưởng cảnh báo |
| Thông báo không có email/SMS | Hiện là thông báo trong ứng dụng; gửi email/SMS thực tế cần tích hợp/cấu hình riêng |

Khi nhờ nhóm hỗ trợ, gửi tên bước, lệnh đã chạy và phần lỗi trong terminal. Che mật khẩu, API key, cookie và nội dung `site_config.json` trước khi chia sẻ.

## 11. Các dấu hiệu hoàn tất

- `list-apps` có `student_crm`.
- `demo.verify` trả `passed: true` và đúng các số lượng mẫu ngay sau seed.
- Mở được Website cổng 5173, đăng nhập được tài khoản của cả ba nhóm vai trò.
- Sinh viên thấy 5 môn/40 điểm danh; cố vấn thấy danh sách được phân công.
- Gửi và duyệt được một yêu cầu sửa điểm danh; thống kê chuyên cần cập nhật theo kết quả.

Hướng dẫn thêm: [cài Ubuntu/WSL](docs/INSTALL_UBUNTU.md), [mô tả bộ demo](docs/DEMO_DATA.md), [phát triển và kiểm thử](docs/DEVELOPMENT.md), [kết quả kiểm tra bản đóng gói](docs/RELEASE_CHECKS.md).
