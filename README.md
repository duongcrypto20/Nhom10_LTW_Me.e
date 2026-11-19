# me.e_digitalcam — Website cho thuê máy ảnh (Django)

Dự án học tập: website chức năng cho cửa hàng cho thuê máy ảnh, viết bằng Django,
giao diện có thanh điều hướng dọc bên trái.

## Cách chạy (Windows)

Cần Python 3.12 trở lên. Môi trường hiện tại sử dụng Python 3.13 và Django theo `requirements.txt`.

```powershell
git clone https://github.com/duongcrypto20/Nhom10_LTW_Me.e.git
cd Nhom10_LTW_Me.e
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe -X utf8 manage.py migrate
.\.venv\Scripts\python.exe -X utf8 manage.py taodulieu
.\.venv\Scripts\python.exe -X utf8 manage.py runserver
```

Mở http://127.0.0.1:8000/

Nếu đã có thư mục dự án, chạy các lệnh từ bước tạo `.venv` trong thư mục chứa `manage.py`.
Không cần kích hoạt môi trường ảo trong PowerShell. Database được tạo bằng các lệnh trên;
ảnh máy mẫu có sẵn trong `media/thietbi/`.

Nếu từng chạy bản cũ có thư mục `customers/` hoặc `me_e_nhom10/`, hãy sao lưu
`db.sqlite3` và `media/`, rồi clone bản này vào một thư mục mới. Bản này dùng
`accounts/` và `config/` với cấu trúc dữ liệu khác, nên cần chạy `migrate` và
`taodulieu` để tạo database mới thay vì chép database của bản cũ vào.

## Tài khoản demo (mật khẩu: 123456)

| Email | Vai trò |
|---|---|
| khach@demo.vn | Khách hàng |
| nv@demo.vn | Nhân viên |
| chu@demo.vn | Chủ cửa hàng (vào được cả /admin/) |

## Cấu trúc

| Thư mục | Nội dung | Use case |
|---|---|---|
| `config/` | Cấu hình dự án, URL gốc | |
| `accounts/` | Tài khoản, đăng ký, đăng nhập, phân quyền | UC-6.1 → 6.4 |
| `catalog/` | Thiết bị, máy vật lý, gói thuê, giá thuê, mã giảm giá | UC-2.1 → 2.3, UC-3.1 → 3.4 |
| `rentals/` | Đặt thuê, xử lý yêu cầu, giao máy, nhận trả, tiền cọc, thông báo | UC-1.1 → 1.5, UC-5.1 → 5.5 |
| `feedback/` | Gửi, xem, duyệt, thống kê, trả lời phản hồi | UC-4.1 → 4.5 |
| `templates/` | Giao diện (base.html chứa thanh điều hướng dọc) | |
| `static/` | CSS, logo, ảnh | |
| `media/` | Ảnh thiết bị và ảnh feedback tải lên | |

Mỗi app theo đúng mẫu của Django: `models.py` (dữ liệu), `forms.py` (form và kiểm tra dữ liệu),
`views.py` (xử lý), `urls.py` (đường dẫn).

## Luồng thử nhanh

1. Đăng nhập `khach@demo.vn` → Lịch máy trống → chọn máy, ngày giờ → Kiểm tra → Đặt thuê thời gian này → Xác nhận đặt đơn → Thanh toán cọc.
2. Đăng nhập `nv@demo.vn` → Lịch máy để xem máy đã được giữ (đơn chưa cọc online thì vào Yêu cầu thuê để xác nhận).
3. Vẫn là nhân viên → Quản lý tiền cọc → Thu cọc (khách nhận máy) → Hoàn cọc (khách trả máy, nếu máy hỏng thì tải ảnh).
4. Đăng nhập lại `khach@demo.vn` → mở đơn đã hoàn tất → Gửi phản hồi.
5. Đăng nhập `nv@demo.vn` → Phản hồi → Duyệt, Trả lời.
6. Đăng nhập `chu@demo.vn` → Thiết bị, Dịch vụ & giá, Tài khoản & phân quyền.

## Bố cục giao diện

| Loại trang | Template gốc | Điều hướng |
|---|---|---|
| Trang công khai: trang chủ, máy ảnh, gói thuê, đánh giá, quy định (ảnh), đăng nhập, đăng ký | `templates/base.html` | Thanh ngang ở trên |
| Trang chức năng sau khi đăng nhập | `templates/base_app.html` | Thanh dọc bên trái, theo vai trò |

Thanh dọc của từng vai trò nằm trong `templates/sidebar/`:

- `khach_hang.html`: Tổng quan, Đơn thuê của tôi, Thông báo, Chọn máy & đặt thuê, Thông tin cá nhân…
- `nhan_vien.html`: Tổng quan, Yêu cầu thuê, Giao nhận & tiền cọc, Thiết bị, Dịch vụ & giá, Phản hồi…
- `chu_cua_hang.html`: mọi mục của nhân viên, thêm nhóm Quản trị (Tài khoản & phân quyền, trang admin Django).

Sau khi đăng nhập: khách hàng vào `/cua-toi/`, nhân viên và chủ cửa hàng vào `/quan-ly/`.
Trên thanh ngang, người đã đăng nhập thấy nút "Trang của tôi" hoặc "Khu vực quản lý" để quay lại.

## Phân quyền

- `accounts/decorators.py` có 3 decorator: `khach_hang_required`, `nhan_vien_required`,
  `chu_cua_hang_required`. Chủ cửa hàng kế thừa quyền của nhân viên.
- Thêm thiết bị, thêm gói thuê, thêm mã giảm giá, phân quyền: chỉ chủ cửa hàng.

## Chức năng chính

- Trang Kiểm tra máy trống: chọn dòng máy, ngày giờ nhận và trả, bấm Kiểm tra để xem lịch tháng với trạng thái Trống / Đang thuê từng ngày.
- Đặt thuê một dòng máy (có số lượng), nhận máy tại cửa hàng, gói Tùy chỉnh thời gian tính tổ hợp gói rẻ nhất.
- Khách xác nhận đặt đơn thì chuyển ngay sang trang **cọc lịch 50.000đ** để giữ máy. Khoản này được tính vào tổng cọc máy; khi nhận máy, nhân viên thu tiền thuê và phần cọc còn lại. Ví dụ cọc máy 700.000đ thì thu trước 50.000đ, tại quầy thu thêm 650.000đ.
- Quản lý tiền cọc trên một trang; phụ thu trả trễ tự tính 50.000đ mỗi giờ (từ phút 15) theo quy định; máy hỏng được lưu kèm ảnh tình trạng.
- Lịch máy cho nhân viên (từng số sê-ri theo ngày), báo cáo doanh thu cho chủ cửa hàng.
- Đánh giá có ảnh, nhân viên duyệt/ẩn, trả lời và thống kê theo sao, gói, dòng máy.
- Trang Quy định chỉ hiện ảnh quy định gốc của cửa hàng.

Đối chiếu đầy đủ 26 use case và các quy tắc tại [docs/CHUC_NANG.md](docs/CHUC_NANG.md).

## Kiểm tra

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test --noinput
```

## Cấu hình chuyển khoản

Nếu cửa hàng có tài khoản nhận tiền, đặt các biến môi trường trước khi khởi động:

```powershell
$env:MEE_BANK_ID = 'ma-ngan-hang-cua-cua-hang'
$env:MEE_BANK_ACCOUNT = 'so-tai-khoan-cua-cua-hang'
$env:MEE_BANK_HOLDER = 'ten-chu-tai-khoan'
.venv\Scripts\python.exe manage.py runserver
```

Trang đặt cọc chỉ hiện mã VietQR khi có thông tin ngân hàng. Nút "Thanh toán cọc online" là cổng thanh toán mô phỏng cho đồ án. Giá thuê và tiền cọc trong dữ liệu mẫu lấy theo ảnh bảng giá và quy định cọc của cửa hàng.
