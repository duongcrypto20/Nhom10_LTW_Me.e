# Hướng dẫn đọc mã nguồn

Dự án dùng Django, Django Template, HTML, CSS và một ít JavaScript thuần.
Không cần Node hay công cụ build frontend.

## Nên đọc theo thứ tự nào?

1. `config/settings.py`, `config/urls.py`: cấu hình và đường dẫn gốc của 4 app.
2. `models.py` của từng app: bảng dữ liệu và quan hệ giữa các bảng.
3. `forms.py`: các ô nhập và điều kiện dữ liệu hợp lệ.
4. `urls.py` rồi `views.py`: nhận GET/POST, kiểm tra quyền, gọi form / nghiệp vụ, render template.
5. `rentals/services.py`: các bước nghiệp vụ đặt thuê và tiền cọc.
6. `rentals/utils.py`: kiểm tra máy trống, phụ thu trả trễ, lịch tháng.
7. `catalog/pricing.py`: tính giá gói cố định và gói tùy chỉnh.
8. `templates/`: cách dữ liệu được hiển thị thành HTML.

Mỗi file Python mở đầu bằng một đoạn mô tả file chứa gì, và chia thành các phần
có tiêu đề (`# ====== 1. ... ======`) để dễ tìm.

## Trách nhiệm từng phần

| Phần | Công việc | Ví dụ |
|---|---|---|
| Model | Định nghĩa dữ liệu và các phép tính đơn giản | `DonThue.tien_coc_con_lai` |
| Form | Kiểm tra dữ liệu người dùng nhập | giờ trả sau giờ nhận, ảnh tối đa 5MB |
| View | Nhận request, phân quyền, chọn trang trả về | `xac_nhan_dat_thue` |
| Service | Thay đổi nhiều bảng trong một nghiệp vụ | `dat_coc_online`, `thu_coc_khi_nhan_may` |
| Template | Hiển thị dữ liệu và lỗi form | `rentals/dat_coc.html` |

## Các bảng dữ liệu

| App | Bảng | Ý nghĩa |
|---|---|---|
| accounts | `User` | Tài khoản, có thêm họ tên, SĐT, CCCD, vai trò |
| catalog | `LoaiThietBi` | Danh mục thiết bị |
| catalog | `ThietBi` | Dòng máy cho thuê, có tiền cọc |
| catalog | `May` | Từng chiếc máy, phân biệt bằng số sê-ri |
| catalog | `GoiThue`, `GiaThue` | Gói thuê và giá của từng máy theo gói |
| catalog | `MaGiamGia` | Mã giảm giá |
| rentals | `DonThue` | Đơn thuê, gồm cả thông tin tiền cọc và giờ nhận / trả thực tế |
| rentals | `ChiTietDonThue` | Từng dòng máy trong đơn, giá đã chốt |
| rentals | `PhanBoMay` | Máy (số sê-ri) được giữ cho đơn |
| rentals | `GiaoDich` | Sổ tiền: đặt cọc, thanh toán, hoàn cọc, thu thêm |
| rentals | `ThongBao` | Thông báo cho người dùng |
| rentals | `SuCo`, `AnhSuCo` | Sự cố của máy (mức độ, mô tả, xử lý) và ảnh máy hỏng |
| feedback | `DanhGia` | Đánh giá của khách cho đơn đã hoàn tất |

## Luồng đặt thuê và tiền cọc (`rentals/services.py`)

1. `kiem_tra_ban_nhap`: tính lại giá, tiền cọc, mã giảm giá từ database và kiểm tra còn máy trống.
2. `luu_yeu_cau`: lưu đơn và chi tiết đơn. Mã gửi (`ma_gui`) chống tạo trùng đơn khi khách bấm hai lần.
3. `dat_coc_online`: khách cọc lịch 50.000đ, hệ thống giữ máy (`phan_bo_may`) và báo cho nhân viên.
   Nếu khách chưa cọc online, nhân viên có thể `xac_nhan_lich` để giữ máy, khách cọc tại quầy.
4. `thu_coc_khi_nhan_may`: thu tiền thuê và phần cọc còn thiếu, đơn và máy chuyển sang Đang thuê.
5. `hoan_coc_khi_tra_may`: tính phụ thu trễ, khấu trừ đền bù, ghi hoàn cọc, máy hỏng chuyển Bảo trì.
6. `ghi_nhan_su_co`: lưu sự cố và ảnh máy hỏng; lỗi nặng thì máy chuyển Bảo trì.

Các hàm thay đổi dữ liệu đều dùng `transaction.atomic`: một bước lỗi thì toàn bộ thay đổi bị hủy.
`khoa_don` khóa đơn để hai nhân viên không xử lý cùng một đơn một lúc.

## Bố cục giao diện

- `base.html`: trang chủ, đăng nhập, đăng ký (thanh điều hướng ngang).
- `base_app.html`: trang sau khi đăng nhập, có thanh điều hướng dọc theo vai trò (`templates/sidebar/`).
- `base_chuc_nang.html`: trang máy ảnh, lịch trống, gói thuê, đánh giá, quy định;
  tự chọn một trong hai bố cục trên tùy người dùng đã đăng nhập hay chưa.
- `_form.html`, `_o_nhap.html`: hiển thị form và lỗi form dùng chung.
- Bộ lọc dùng GET; thao tác thay đổi dữ liệu dùng POST và CSRF.

## Tự kiểm tra sau khi sửa

```powershell
.\.venv\Scripts\python.exe -X utf8 manage.py check
.\.venv\Scripts\python.exe -X utf8 manage.py test --noinput
.\.venv\Scripts\python.exe -X utf8 manage.py makemigrations --check --dry-run
```

## Bảo mật và thông báo lỗi

- **Chống CSRF:** `CsrfViewMiddleware` bật trong `config/settings.py`; mọi form POST có `{% csrf_token %}`.
  Request thiếu / sai mã bị chặn và hiện trang `loi_csrf.html` (view `config/views.py`).
  Cookie dùng `SameSite=Lax`, cookie đăng nhập `HttpOnly`, chặn nhúng trang bằng `X_FRAME_OPTIONS = 'DENY'`.
- **Thao tác thay đổi dữ liệu** chỉ nhận POST (`@require_POST`), có kiểm tra quyền theo vai trò.
- **Thông báo lỗi khi nhập sai:** mọi form kế thừa `FormCoBan` / `ModelFormCoBan` (`config/form_co_ban.py`),
  thông báo có tên ô, ví dụ "Vui lòng nhập Họ tên.", "Email không đúng định dạng...".
  Đầu form có khung tóm tắt các ô bị lỗi (`templates/_tom_tat_loi.html`), lỗi từng ô hiện ngay dưới ô (`_o_nhap.html`).
- Lỗi nghiệp vụ (hết máy, sai trạng thái đơn, mã giảm giá hết lượt...) báo bằng `ValidationError` trong `services.py`.
