# Cài Student CRM trên Ubuntu / WSL2

Repo là một app Frappe hoàn chỉnh kèm Website riêng. Không cần chép `site_config.json`, database hoặc mật khẩu của máy khác. Thực hiện lệnh Linux trong terminal **Ubuntu**, không chạy trong PowerShell.

## 1. Chuẩn bị

Nếu máy đã có bench Frappe v16, sang bước 3. Không chạy lại phần cài dịch vụ lên máy đang có database sử dụng thực tế.

Môi trường mục tiêu: Ubuntu 24.04+, Frappe v16, Python 3.14, Node.js 24, Yarn 1.x, Redis 6+ và MariaDB 11.8. Tham khảo [hướng dẫn Frappe chính thức](https://docs.frappe.io/framework/user/en/installation). App được kiểm tra với Frappe 16.34.0.

Windows chưa có WSL: mở PowerShell với quyền Administrator:

```powershell
wsl --install -d Ubuntu-24.04
```

Khởi động lại nếu được yêu cầu, mở Ubuntu và tạo username/password Linux. Nên đặt bench trong `~/frappe-bench`, tránh `/mnt/c` hoặc OneDrive để giảm lỗi quyền và hiệu năng.

Trong Ubuntu mới:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates build-essential pkg-config redis-server libmariadb-dev
```

Cài MariaDB 11.8 theo [repository chính thức MariaDB](https://mariadb.com/docs/server/server-management/install-and-upgrade-mariadb/mariadb-package-repository-setup-and-usage). Trên Ubuntu mới, chưa có MariaDB/MySQL:

```bash
curl -fsSL https://r.mariadb.com/downloads/mariadb_repo_setup -o /tmp/mariadb_repo_setup
sudo bash /tmp/mariadb_repo_setup --mariadb-server-version=mariadb-11.8 --skip-maxscale
sudo apt update
sudo apt install -y mariadb-server mariadb-client
sudo service mariadb start
sudo mariadb-secure-installation
```

Ghi nhớ mật khẩu quản trị MariaDB vừa đặt. Nó khác với mật khẩu Administrator của Website. Nếu dùng Unix socket và chưa có tài khoản có thể tạo database, xem mục xử lý lỗi bên dưới.

Cài Node/Yarn và Python/Bench:

```bash
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh -o /tmp/install-nvm.sh
bash /tmp/install-nvm.sh
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm install 24
nvm alias default 24
npm install -g yarn@1.22.22

curl -LsSf https://astral.sh/uv/install.sh -o /tmp/install-uv.sh
sh /tmp/install-uv.sh
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.14
uv tool install frappe-bench

node --version
yarn --version
bench --version
mariadb --version
```

Các script tải từ nvm/uv/MariaDB là bộ cài của nhà cung cấp. Tính năng xuất PDF không thuộc Website hiện tại; cài thêm wkhtmltopdf nếu muốn dùng chức năng in PDF của Frappe v16.

## 2. Tạo bench Frappe

Trên máy mới:

```bash
cd ~
bench init --frappe-branch v16.34.0 --python "$(uv python find 3.14)" frappe-bench
cd ~/frappe-bench
```

Nếu đã có bench, đi vào bench của bạn và kiểm tra:

```bash
bench version
env/bin/python --version
node --version
```

Repo này yêu cầu Frappe **16.34+ thuộc v16**. Chưa hỗ trợ cài trực tiếp lên v15 hoặc v17. Có thể tạo bench v16 riêng để giữ nguyên các dự án khác.

## 3. Cài app lên site

```bash
cd ~/frappe-bench
bench new-site studentcrm.local
bench get-app --branch main https://github.com/anhquan27it/student_crm.git
bash apps/student_crm/scripts/setup.sh studentcrm.local
```

- Nếu site đã tồn tại, bỏ `new-site`; nên dùng site mới dành riêng cho demo.
- Nếu `apps/student_crm` đã tồn tại, bỏ `get-app` và kiểm tra đúng repository trước khi cập nhật.
- Nếu đặt site khác, thay `studentcrm.local` ở mọi lệnh bằng tên đó.
- Cài đặt tự đồng bộ 16 DocType, Custom Field, chỉ mục và cấu hình cần thiết. Không cần tạo DocType thủ công hay bật developer mode.
- Script không xóa database và không tự seed. Nó tạo `frontend/.env` đúng tên site khi chưa có file đó.

Có thể làm thủ công thay script:

```bash
bench --site studentcrm.local install-app student_crm
bench --site studentcrm.local migrate
cp apps/student_crm/frontend/.env.example apps/student_crm/frontend/.env
nano apps/student_crm/frontend/.env
```

Nội dung `.env`:

```dotenv
PORT=5173
HOST=127.0.0.1
FRAPPE_URL=http://127.0.0.1:8000
FRAPPE_SITE=studentcrm.local
```

Nếu bench chạy ở cổng khác, sửa `FRAPPE_URL`. Không thêm dấu `/` hoặc đường dẫn `/api` sau tên site.

## 4. Tạo dữ liệu mẫu

Trên site mới/demo:

```bash
bench --site studentcrm.local execute student_crm.demo.seed
bench --site studentcrm.local execute student_crm.demo.verify
```

Chờ lệnh seed kết thúc; lần đầu tạo hơn 4.000 bản ghi. Kết quả phải có `passed: true`, `students: 100`, `enrollments: 500`, `attendance: 4000`. Lệnh chạy lại chỉ kiểm tra bộ đã tạo, không nhân đôi dữ liệu và không reset password. Xem [DEMO_DATA.md](DEMO_DATA.md).

## 5. Chạy Website

Terminal Ubuntu 1:

```bash
cd ~/frappe-bench
bench start
```

Terminal Ubuntu 2:

```bash
cd ~/frappe-bench/apps/student_crm/frontend
npm start
```

Mở **http://127.0.0.1:5173**. Tài khoản sinh viên: `demo.crm.student001@example.com` / `Student@123`. Hai terminal cần tiếp tục chạy. Dừng bằng `Ctrl+C` ở từng terminal.

Muốn kiểm tra cảnh báo hành vi hết hạn tự động, bật scheduler cho site demo:

```bash
cd ~/frappe-bench
bench --site studentcrm.local enable-scheduler
```

Scheduler/workers đã có trong `bench start`. Thông báo hiện tại là thông báo trong ứng dụng; không yêu cầu cấu hình email/SMS.

Có thể chạy frontend trên Windows bằng Node 24: clone repo vào thư mục khác, tạo `frontend/.env` cùng cấu hình rồi chạy `npm start` trong `frontend`. Backend và app vẫn phải cài trong Ubuntu. Cách chạy toàn bộ trong Ubuntu ở trên dễ thiết lập hơn.

## Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| `bench: command not found` | Mở terminal mới hoặc `export PATH="$HOME/.local/bin:$PATH"` |
| `node/yarn: command not found` | `source ~/.nvm/nvm.sh`, `nvm use 24`, kiểm tra đã cài Yarn |
| MariaDB `Access denied` khi tạo site | Dùng mật khẩu DB quản trị của máy bạn; không dùng `Student@123` trừ khi chính bạn đã đặt nó cho DB |
| MariaDB root chỉ cho Unix socket | `sudo mariadb`, tạo tài khoản cài đặt riêng bằng `CREATE USER 'frappe_admin'@'localhost' IDENTIFIED BY 'MAT_KHAU_DB_TU_CHON';` rồi `GRANT ALL PRIVILEGES ON *.* TO 'frappe_admin'@'localhost' WITH GRANT OPTION;`. Dùng `bench new-site studentcrm.local --db-root-username frappe_admin`; tài khoản này phục vụ cài đặt Bench, không phải tài khoản Website |
| Không kết nối được DB sau khi mở WSL | `sudo service mariadb start` rồi chạy lại `bench start` |
| `No such command new-site` | Bạn chưa đứng trong bench hoặc bench init chưa hoàn tất |
| Website báo không kết nối backend / 502 | Giữ `bench start` chạy; kiểm tra cổng web và `FRAPPE_URL` |
| Sai site / đăng nhập không thấy dữ liệu mẫu | Kiểm tra `FRAPPE_SITE`, tên site đã seed; khởi động lại `npm start` sau khi đổi `.env` |
| Thiếu trường `support_case` / `crm_event_key` | `bench --site studentcrm.local migrate`, khởi động lại bench nếu vừa đổi Python hooks |
| Cổng 5173 bận | Đặt `PORT=5174` trong `.env`, khởi động lại frontend và mở đúng cổng |
| Seed báo namespace đã tồn tại nhưng không có manifest | Không xóa/gán lại dữ liệu để ép seed. Dùng site mới hoặc phục hồi manifest đúng site từ backup |
| Seed từ chối ngưỡng tùy chỉnh | Dùng site demo với cấu hình mặc định 10/15/20 và 3 buổi/14 ngày; không đổi quy tắc của site đang sử dụng để chạy demo |

Hướng dẫn này dành cho phát triển/demo local. Không mở cổng phát triển hoặc dùng tài khoản mẫu công khai trên Internet.
