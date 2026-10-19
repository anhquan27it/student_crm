# Dữ liệu mẫu portable

Danh sách 15 môn nằm trong [`catalog.json`](../student_crm/demo_data/catalog.json): CEA201, CSI106, MAE101, PRF192, SSL101c, JPD113, MAD101, NWC204, OSG202, PRO192, CSD201, DBI202, JPD123, LAB211, MAS291. Tên môn và học kỳ khuyến nghị theo danh sách ban đầu; demo mở cả 15 môn trong một học kỳ để tiện thử.

Seed là mã Python gọi Document/controller thật, không phải bản dump database từ máy tác giả. Mọi tên, email `example.com`, kết quả điểm danh và ghi chú đều giả lập.

```bash
cd ~/frappe-bench
bench --site studentcrm.local execute student_crm.demo.seed
bench --site studentcrm.local execute student_crm.demo.verify
```

| Dữ liệu đầu vào | Số lượng |
| --- | ---: |
| Khoa / chương trình / học kỳ demo | 1 / 3 / 1 |
| Cố vấn / giảng viên | 3 / 5 |
| Sinh viên / tài khoản sinh viên | 100 / 100 |
| Môn / lớp học phần / buổi học | 15 / 15 / 300 |
| Đăng ký học / điểm danh | 500 / 4.000 |
| Buổi đã chốt | 120 — 8 buổi mỗi lớp |

Mỗi cố vấn phụ trách 34/33/33 sinh viên. Mỗi sinh viên học 5 môn, có 40 bản ghi điểm danh. Buổi tương lai còn lại để giảng viên tiếp tục thử điểm danh khi đến ngày học.

Các DocType phát sinh như Student Warning, Student Support Case, Advisor Assignment, Intervention Log và Notification Log được tạo qua hooks. CRM Settings có giá trị mặc định. Attendance Correction Request ban đầu trống có chủ ý: sinh viên gửi yêu cầu từ màn hình Điểm danh của tôi, sau đó giảng viên duyệt trong Sửa điểm danh hoặc từ Thông báo.

## Tài khoản và kịch bản

Mật khẩu demo mặc định: **`Student@123`**. Chỉ dùng local.

| Tài khoản | Vai trò / tình huống |
| --- | --- |
| `demo.crm.faculty01@example.com` ... `faculty03` | 3 cố vấn |
| `demo.crm.faculty04@example.com` ... `faculty08` | 5 giảng viên |
| `demo.crm.student001@example.com` ... `student100` | 100 sinh viên |
| `demo.crm.student001@example.com` | Good |
| `demo.crm.student004@example.com` | Warning, nghỉ 2/20 ở môn đầu |
| `demo.crm.student007@example.com` | Critical, nghỉ 3/20 |
| `demo.crm.student010@example.com` | Critical, nghỉ đúng 4/20, chưa cấm thi |
| `demo.crm.student013@example.com` | Barred, nghỉ 5/20 |
| `demo.crm.student016@example.com` | Vắng liên tiếp ở nhiều môn |
| `demo.crm.student019@example.com` | Đã đối chiếu, trở lại Good; có lịch sử hỗ trợ |
| `demo.crm.student022@example.com` | Đi muộn; không tính vắng |

Sinh viên 001 thuộc lớp CEA201 do giảng viên 04 phụ trách, cố vấn 01 theo dõi. Để thử sửa điểm danh: đăng nhập sinh viên 013 → Điểm danh của tôi → chọn một dòng Vắng → gửi lý do → đăng nhập giảng viên 04 → mở yêu cầu → đối chiếu và duyệt. Kết quả chuyên cần/cảnh báo được tính lại; đóng hồ sơ hỗ trợ riêng không tự xóa trạng thái cấm thi.

Để dùng mật khẩu demo khác ở lần đầu (không đưa vào Git):

```bash
read -rsp 'Mật khẩu cho các tài khoản demo: ' CRM_DEMO_PASSWORD
echo
export CRM_DEMO_PASSWORD
bench --site studentcrm.local execute student_crm.demo.seed
unset CRM_DEMO_PASSWORD
```

Manifest nằm trong **site riêng của bạn**, `sites/<site>/private/student_crm_demo/manifest.json`. Không sửa tay hoặc đưa vào Git. Seed hoàn tất được chạy lại an toàn: chỉ audit, không thay dữ liệu bạn đã sửa hoặc mật khẩu. `verify` kiểm tra số lượng/liên kết; sau khi tự thêm/xóa dữ liệu demo, một số số đếm có thể không còn khớp, cần đọc lỗi thay vì seed đè.

Ngày neo mặc định là ngày chạy seed. Do đó cảnh báo hành vi có dữ liệu gần thời điểm cài. Khi thời gian thực trôi qua, scheduler có thể làm cảnh báo hành vi cũ hết hiệu lực; đó là hành vi đúng. Không cố định ngày về máy tác giả và không giả định các cảnh báo luôn giữ nguyên.

Không có lệnh xóa dữ liệu hàng loạt trong app. Muốn làm lại demo sạch, tạo site mới và seed ở site đó. Luôn giữ backup khi có dữ liệu tự nhập cần bảo tồn.
