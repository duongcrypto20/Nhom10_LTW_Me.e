# me.e_digitalcam: Website cho thuê máy ảnh (Django)

Đồ án học phần Lập trình Web (MIS3010), Nhóm 10, lớp 50K22.2.
Website quản lý và cung cấp dịch vụ cho thuê máy ảnh cho cửa hàng me.e_digitalcam.

## Cách chạy (Windows)

Cần Python 3.12 trở lên.

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

> Nếu máy bạn đã có `db.sqlite3` của bản trước, hãy xóa (hoặc đổi tên) file đó rồi chạy lại
> `migrate` và `taodulieu`. Bản này đã gộp lại migration nên không dùng được database cũ.

## Tài khoản demo (mật khẩu: 123456)

| Email | Vai trò | Có sẵn |
|---|---|---|
| chu@demo.com | Chủ cửa hàng (vào được cả /admin/) | Báo cáo doanh thu, phân quyền |
| nv@demo.com | Nhân viên | Yêu cầu thuê, tiền cọc, sự cố máy, phản hồi |
| khach@demo.com | Khách hàng | 1 đơn hoàn tất, 1 đơn đang thuê, 1 đơn đã hủy |
| ngoc@demo.com | Khách hàng | 1 đơn trả trễ, 1 đơn đã cọc chờ nhận máy |
| phuc@demo.com | Khách hàng | 1 đơn có máy hư hỏng, 1 đơn chờ xử lý |
| trang@demo.com | Khách hàng | 1 đơn chưa cọc, 1 đơn cần điều chỉnh |

Lệnh `taodulieu` tạo 12 dòng máy (ảnh trong `media/thietbi/`), 5 gói thuê, bảng giá,
2 mã giảm giá (`MEE10`, `GIAM50K`), 9 đơn thuê ở đủ các trạng thái, 3 đánh giá và 2 sự cố máy.

## Cấu trúc thư mục

| Thư mục | Nội dung | Use case |
|---|---|---|
| `config/` | Cấu hình dự án, URL gốc | |
| `accounts/` | Tài khoản, đăng ký, đăng nhập, phân quyền | UC-6 |
| `catalog/` | Thiết bị, máy (số sê-ri), gói thuê, giá thuê, mã giảm giá, dữ liệu mẫu | UC-2, UC-3 |
| `rentals/` | Đặt thuê, xử lý yêu cầu, lịch máy, tiền cọc, thông báo, báo cáo | UC-1, tiền cọc |
| `feedback/` | Gửi, xem, duyệt, thống kê, trả lời phản hồi | UC-4 |
| `templates/` | Giao diện HTML (Django Template) | |
| `static/` | CSS, JavaScript, ảnh giao diện | |
| `media/` | Ảnh thiết bị và ảnh khách tải lên | |
| `docs/` | Đối chiếu chức năng (`CHUC_NANG.md`) và hướng dẫn đọc mã (`KIEN_TRUC.md`) | |

Mỗi app theo đúng mẫu của Django:

- `models.py`: bảng dữ liệu
- `forms.py`: form và kiểm tra dữ liệu nhập
- `views.py`: nhận request, kiểm tra quyền, trả về trang
- `urls.py`: đường dẫn
- `tests.py`: kiểm thử
- riêng `rentals/services.py`: các bước nghiệp vụ thay đổi đơn, máy và tiền cùng lúc

## Luồng sử dụng chính

1. Khách vào **Kiểm tra máy trống** → chọn máy, ngày giờ nhận / trả → **Đặt thuê**.
2. Khách chọn gói, xem lại đơn → **Xác nhận đặt đơn** → chuyển sang trang **Đặt cọc**.
3. Khách cọc lịch 50.000đ online → hệ thống giữ máy (số sê-ri) và báo cho nhân viên.
4. Khách đến nhận máy → nhân viên vào **Quản lý tiền cọc → Thu cọc**: thu tiền thuê và phần cọc còn lại.
5. Khách trả máy → nhân viên **Hoàn cọc**: hệ thống tự tính phụ thu trả trễ, khấu trừ đền bù nếu máy hỏng.
6. Khách viết **đánh giá** → nhân viên duyệt và trả lời.

Khi máy gặp sự cố, nhân viên mở chi tiết đơn → **Ghi nhận sự cố** (hoặc menu **Sự cố máy**, nhập mã đơn):
chọn máy, mức độ lỗi nhẹ / nặng, mô tả và tải ảnh máy hỏng. Lỗi nặng thì máy chuyển sang Bảo trì.

## Phân quyền

`accounts/decorators.py` có 3 decorator: `khach_hang_required`, `nhan_vien_required`,
`chu_cua_hang_required`. Chủ cửa hàng có toàn bộ quyền của nhân viên, thêm:
thêm thiết bị, gói thuê, mã giảm giá, danh mục, phân quyền tài khoản và báo cáo doanh thu.

## Quy định cửa hàng trong code

| Quy định | Vị trí trong code |
|---|---|
| Cọc 700.000đ mỗi máy, máy compact 300.000đ | `ThietBi.tien_coc`, đặt trong `taodulieu` |
| Cọc lịch 50.000đ để giữ máy, tính vào tổng cọc | `DonThue.COC_GIU_LICH`, `services.dat_coc_online` |
| Thuê 1 ngày tính 23 giờ, 1 buổi 6 giờ | Gói `1 ngày` 23 giờ, `6 giờ` 6 giờ |
| Trả trễ từ phút 15 phụ thu 50.000đ mỗi giờ | `rentals/utils.py` → `tinh_phi_tra_tre` |
| Đã cọc thì không nhận hủy lịch | `DonThue.co_the_huy` |
| Đền bù thiệt hại trừ vào cọc, vượt cọc thì thu thêm | `services.hoan_coc_khi_tra_may` |

Cổng thanh toán cọc là **mô phỏng**: khách bấm thanh toán thì hệ thống ghi nhận thành công ngay.
Muốn dùng cổng thật (VNPay, MoMo) chỉ cần gọi `services.dat_coc_online` khi cổng báo thành công.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -X utf8 manage.py check
.\.venv\Scripts\python.exe -X utf8 manage.py test --noinput
```
