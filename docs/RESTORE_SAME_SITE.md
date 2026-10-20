# Khôi phục đúng Website và toàn bộ dữ liệu của tác giả

**Dùng hướng dẫn này nếu muốn có đúng 121 sinh viên và nội dung như máy tác giả.** Không chạy `demo.seed` cho site nhận bản sao này. Seed trong các hướng dẫn cũ chỉ tạo bộ giả lập 100 sinh viên khác.

## Bản sao bao gồm gì?

Repository có `transfer/studentcrm-20261020.crmenc`, là bản sao database, file public/private và khóa giải mã các trường mã hóa trong Frappe, được bảo vệ bằng **AES-256-GCM**. Mật khẩu kết nối database nguồn không được đưa vào gói. Khóa mở gói `.crmkey` được tác giả gửi riêng, không có trên GitHub.

| Dữ liệu trong bản chụp | Số lượng |
| --- | ---: |
| Sinh viên | **121** |
| Khoa / chương trình / học kỳ | 8 / 21 / 22 |
| Môn / giảng viên-cố vấn / lớp học phần | 16 / 10 / 43 |
| Buổi học | 613 |
| Đăng ký / điểm danh | 511 / 4.010 |
| Cảnh báo / hồ sơ hỗ trợ | 100 / 72 |
| Lịch sử cố vấn / nhật ký can thiệp | 100 / 36 |
| Yêu cầu sửa điểm danh | 0 tại thời điểm chụp |

Tên sinh viên, nội dung/ngày nhật ký, trạng thái điểm danh, lịch sử cảnh báo và các bản ghi cũ đều được lấy từ database nguồn. Bản sao giữ nguyên cả các bản ghi cũ cần đối chiếu ở Chất lượng dữ liệu, không tự sửa chúng.

Đây là **bản chụp tại thời điểm đóng gói**, không phải kết nối trực tiếp đến máy tác giả. Những thay đổi nhập trong Frappe sau thời điểm này chỉ sang máy khác khi tác giả tạo và chia sẻ bản sao mới.

## 1. Nhận code và khóa riêng

Chuẩn bị Ubuntu/WSL với **Frappe 16.34.0** theo [hướng dẫn cài đặt](INSTALL_UBUNTU.md). Công cụ restore yêu cầu đúng phiên bản này cho bản sao hiện tại, không dùng `--force` để vượt kiểm tra phiên bản.

Trong thư mục bench của bạn:

```bash
cd ~/frappe-bench
bench get-app --branch main https://github.com/anhquan27it/student_crm.git
```

Nếu đã có đúng app, giữ/commit thay đổi của mình trước rồi cập nhật:

```bash
cd ~/frappe-bench/apps/student_crm
git pull --ff-only
cd ../..
```

Nhận file `studentcrm-20261020.crmkey` **trực tiếp từ tác giả qua kênh riêng**. Đặt nó ngoài repository, ví dụ:

```text
~/studentcrm-20261020.crmkey
```

Nếu file ở Windows Downloads, chép vào Ubuntu bằng đường dẫn của chính bạn, ví dụ:

```bash
cp /mnt/c/Users/TEN_WINDOWS_CUA_BAN/Downloads/studentcrm-20261020.crmkey ~/studentcrm-20261020.crmkey
chmod 600 ~/studentcrm-20261020.crmkey
```

Không gửi nội dung khóa vào issue, pull request, log hoặc commit. Người có cả file mã hóa và khóa sẽ đọc được toàn bộ bản sao; chỉ chia sẻ cho thành viên được phép nhận dữ liệu.

## 2. Tạo site MỚI, không cài app/seed vào site đó

```bash
cd ~/frappe-bench
bench new-site studentcrm-copy.local
```

Đây phải là site mới chỉ có Frappe với Administrator/Guest. **Không chạy setup.sh, install-app hoặc demo.seed lên site này trước restore.** Database backup đã chứa app và các DocType; chỉ cần code app hiện diện trong `apps/student_crm`.

Nếu bạn đã seed một site từ lần cài trước, giữ site đó và tạo site mới tên khác. Công cụ chủ động từ chối ghi đè site đã dùng.

## 3. Giải mã và khôi phục

Từ thư mục bench:

```bash
cd ~/frappe-bench
env/bin/python apps/student_crm/scripts/restore_copy.py \
  --site studentcrm-copy.local \
  --package apps/student_crm/transfer/studentcrm-20261020.crmenc \
  --key-file ~/studentcrm-20261020.crmkey
```

Công cụ hỏi:

1. **Mật khẩu Administrator mới cho bản sao của bạn**, tối thiểu 10 ký tự, nhập lại để xác nhận. Không cần biết mật khẩu Administrator của tác giả.
2. **Mật khẩu quản trị MariaDB trên máy bạn**, dùng để restore database mới.

Nếu DB administrator của bạn có tên khác `root`, thêm:

```bash
env/bin/python apps/student_crm/scripts/restore_copy.py \
  --site studentcrm-copy.local \
  --package apps/student_crm/transfer/studentcrm-20261020.crmenc \
  --key-file ~/studentcrm-20261020.crmkey \
  --db-root-username frappe_admin
```

Lệnh sẽ kiểm tra site đích, xác thực gói mã hóa, restore database/file, migrate, rồi so sánh **số lượng và hash nội dung của 15 bảng nghiệp vụ cùng CRM Settings** với nguồn. Sau đó đặt password quản trị mới, xóa phiên đăng nhập/API token sao chép và tạm dừng email/scheduler trên bản sao.

File giải mã chỉ tồn tại trong thư mục private tạm của site đích và được dọn khi lệnh kết thúc. Không đưa SQL đã giải mã vào Git.

Khi thành công, terminal in:

```text
RESTORE VERIFIED: full business data matches.
```

Nếu lỗi giữa chừng, site đích mới có thể chưa hoàn chỉnh; đọc lỗi và xử lý hoặc tạo một site mới khác. Không thử restore lại trên site đang có dữ liệu cần giữ. Database máy tác giả không bị công cụ này tác động.

## 4. Trỏ frontend về bản sao

Script đã chuẩn bị cấu hình tại `sites/studentcrm-copy.local/private/frontend.env`. Nếu bạn muốn chuyển frontend hiện tại sang site này, lưu `.env` cũ ngoài Git rồi chép cấu hình mới:

```bash
cd ~/frappe-bench
# Chỉ sao lưu .env nếu file này đã tồn tại.
if [ -f apps/student_crm/frontend/.env ]; then
  cp apps/student_crm/frontend/.env sites/studentcrm-copy.local/private/frontend.previous.env
fi
cp sites/studentcrm-copy.local/private/frontend.env apps/student_crm/frontend/.env
```

Nội dung cần có:

```dotenv
PORT=5173
HOST=127.0.0.1
FRAPPE_URL=http://127.0.0.1:8000
FRAPPE_SITE=studentcrm-copy.local
```

Sửa cổng backend/frontend nếu máy bạn dùng cổng khác. Dừng và chạy lại frontend sau khi đổi `.env`.

Terminal 1:

```bash
cd ~/frappe-bench
bench start
```

Terminal 2:

```bash
cd ~/frappe-bench/apps/student_crm/frontend
npm start
```

Mở **http://127.0.0.1:5173**, đăng xuất phiên cũ nếu có và `Ctrl+F5`.

## 5. Đăng nhập và đối chiếu

- Administrator: mật khẩu **mới bạn vừa đặt trong lệnh restore**.
- Tài khoản mẫu `demo.crm.faculty01@example.com`, `demo.crm.faculty04@example.com`, `demo.crm.student001@example.com`: dùng mật khẩu mẫu hiện tại của nguồn, `Student@123` trong bản chụp này.
- Tài khoản cũ khác không được tự đặt lại password; Administrator của bản sao có thể quản lý chúng khi cần.

Đăng nhập Administrator → Sinh viên: phải có **121**. Mở Nhật ký can thiệp: có **36** bản ghi với tên/nội dung giống bản chụp nguồn. Cố vấn vẫn chỉ thấy sinh viên được phân công; giảng viên vẫn chỉ thấy lớp mình phụ trách.

Ảnh/giao diện phải lấy từ đúng commit/code của repository và đúng site. Không chạy `demo.verify` trên bản full-copy: lệnh đó kiểm tra bộ seed 100 sinh viên, không phải bản sao toàn site 121 sinh viên.

Email và scheduler được tạm dừng có chủ ý để bản sao local không gửi email hoặc tự chạy các tác vụ nguồn. Chỉ bật lại sau khi tự rà cấu hình của máy mình. Các thao tác điểm danh/cảnh báo trực tiếp trên Website vẫn chạy qua hooks.

## 6. Lỗi thường gặp

| Lỗi | Cách xử lý |
| --- | --- |
| Không có file `.crmenc` | Chưa pull commit mới nhất hoặc đứng sai thư mục bench |
| Không có file `.crmkey` | Nhận khóa riêng từ tác giả; khóa không nằm trên GitHub |
| Giải mã thất bại | Kiểm tra khóa có đúng gói, file tải đủ và đường dẫn đúng; không sửa nội dung file |
| Target must be a NEW site | Tạo một site mới chỉ có Frappe; giữ nguyên site cũ |
| Yêu cầu Frappe 16.34.0 | Dùng bench đúng phiên bản; hướng dẫn cài đã có lệnh pin phiên bản |
| MariaDB Access denied | Nhập mật khẩu DB của chính máy bạn, dùng đúng `--db-root-username` |
| Business data differs | Không coi bản restore là hoàn tất. Gửi tên bảng lỗi để kiểm tra, không bỏ qua bước xác minh |
| Web vẫn chỉ hiện 100 sinh viên | Kiểm tra `FRAPPE_SITE=studentcrm-copy.local`, cổng backend, restart Node và đăng nhập Administrator |
| Web server bị cố định vào site khác | Có thể chạy `bench --site studentcrm-copy.local serve --port 8001`, sửa `FRAPPE_URL` sang cổng 8001 rồi restart frontend |

Tóm tắt: **pull code + nhận khóa riêng + tạo site mới + restore_copy.py + trỏ .env đúng site**. Không seed thêm vào site nhận full-copy.
