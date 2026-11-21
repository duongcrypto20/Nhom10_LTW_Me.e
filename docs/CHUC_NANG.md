# Đối chiếu chức năng với BCTD1 và BCTD2

Tài liệu này ghi lại những gì website đã làm so với Báo cáo tiến độ 1 (phạm vi, phân công)
và Báo cáo tiến độ 2 (đặc tả use case, thiết kế cơ sở dữ liệu), sau khi nhóm còn 3 thành viên.

## 1. Thay đổi về phân công

| Module (BCTD1) | Phụ trách | Hiện trạng |
|---|---|---|
| 2.2.1 Quản lý đặt thuê thiết bị | Ngô Quỳnh Dương | Giữ, **nhận thêm phần tiền cọc** |
| 2.2.2 Quản lý thiết bị cho thuê | Đinh Nữ Quỳnh Trang | Giữ |
| 2.2.3 Quản lý dịch vụ cho thuê | Đinh Nữ Quỳnh Trang | Giữ |
| 2.2.4 Quản lý giao nhận, trả máy và tiền cọc | Nguyễn Lê Đông Hoàng (đã rời nhóm) | **Thu gọn**: chỉ giữ tiền cọc, gộp vào module đặt thuê |
| 2.2.5 Quản lý phản hồi khách hàng | Đậu Trần Khánh Tùng | Giữ |
| 2.2.6 Quản lý tài khoản và phân quyền | (chung) | Giữ |

## 2. Use case

| Use case (BCTD2) | Trong website | Ghi chú |
|---|---|---|
| UC-1.1 Chọn thiết bị và thời gian thuê | Trang Đặt thuê: số lượng, gói, giờ nhận, giờ trả, mã giảm giá | Có thêm gói Tùy chỉnh thời gian, tự ghép các gói rẻ nhất |
| UC-1.2 Gửi yêu cầu thuê | Trang Xác nhận đặt đơn | Giá tính lại từ database; gửi xong chuyển sang trang Đặt cọc |
| UC-1.3 Kiểm tra máy trống | Trang Kiểm tra máy trống + Lịch máy của nhân viên | Kiểm tra theo từng số sê-ri, lịch tháng Trống / Đang thuê / Bảo trì |
| UC-1.4 Xử lý và xác nhận lịch thuê | Yêu cầu thuê → Xác nhận / Yêu cầu điều chỉnh / Hủy; Đổi máy cùng dòng | |
| UC-1.5 Theo dõi trạng thái yêu cầu thuê | Trang của tôi, Đơn thuê của tôi, chi tiết đơn có thanh tiến trình 5 mốc | Mốc: Đặt đơn → Giữ máy → Đã cọc → Đang thuê → Hoàn tất |
| UC-2.1 → 2.3 Quản lý thiết bị | Thêm / sửa thiết bị, thêm máy theo số sê-ri, đổi tình trạng máy, danh sách, chi tiết | |
| UC-3.1 → 3.4 Quản lý dịch vụ | Thêm / sửa gói thuê, bảng giá theo máy và gói | |
| UC-4.1 → 4.5 Quản lý phản hồi | Gửi đánh giá (kèm ảnh), xem, duyệt / ẩn, thống kê, trả lời | |
| UC-5.1 Kiểm tra thông tin đơn thuê | **Bỏ trang riêng**, gộp vào ô tìm kiếm (mã đơn, tên, SĐT) ở Yêu cầu thuê và Quản lý tiền cọc | |
| UC-5.2 Ghi nhận giao, nhận trả | **Gộp** vào 2 thao tác tiền cọc: Thu cọc (khách nhận máy), Hoàn cọc (khách trả máy, chọn trả trực tiếp / gửi về) | Bỏ mã vận đơn, khách tự báo trả máy |
| UC-5.3 Kiểm tra tình trạng thiết bị | **Trang Sự cố máy**: nhân viên ghi nhận sự cố cho máy của đơn (mức độ nhẹ / nặng, mô tả, tối đa 5 ảnh máy hỏng), cập nhật kết quả xử lý. Lỗi nặng thì máy chuyển Bảo trì và được chọn sẵn là hư hỏng khi hoàn cọc | Bỏ biên bản kiểm tra từng máy |
| UC-5.4 Quản lý tiền cọc | **Giữ**: trang Quản lý tiền cọc (Chưa thu / Đang giữ / Đã hoàn) | Cọc lịch online 50.000đ, phụ thu trễ tự tính, khấu trừ đền bù |
| UC-5.5 Cập nhật trạng thái thiết bị, đơn thuê | **Tự động**: thu cọc → đơn và máy Đang thuê; hoàn cọc → đơn Hoàn tất, máy Sẵn sàng hoặc Bảo trì | Không còn màn hình riêng |
| UC-6.1 → 6.4 Tài khoản và phân quyền | Đăng ký, đăng nhập, thông tin cá nhân, đổi mật khẩu, phân quyền, khóa tài khoản | Chủ cửa hàng có thêm Báo cáo doanh thu |

## 3. Cơ sở dữ liệu so với BCTD2 (mục 3.3)

| Bảng trong BCTD2 | Trong code | Ghi chú |
|---|---|---|
| VaiTro | Trường `User.vai_tro` | Chỉ có 3 vai trò cố định nên dùng trường lựa chọn |
| TaiKhoan | `accounts.User` | Kế thừa User của Django |
| LoaiThietBi | `catalog.LoaiThietBi` | |
| ThietBi | `catalog.ThietBi` | |
| ChiTietThietBi | `catalog.May` | Mỗi máy một số sê-ri |
| GoiDichVu | `catalog.GoiThue` + `catalog.GiaThue` | Tách giá theo từng máy và gói |
| MaGiamGia | `catalog.MaGiamGia` | |
| DiaChiKhachHang | **Bỏ** | Khách nhận máy tại cửa hàng |
| DonThue | `rentals.DonThue` | Gồm luôn các trường tiền cọc và giờ nhận / trả thực tế |
| ChiTietDonThue | `rentals.ChiTietDonThue` + `rentals.PhanBoMay` | PhanBoMay ghi máy nào được giữ cho đơn |
| GiaoDich | `rentals.GiaoDich` | Đặt cọc, thanh toán, hoàn cọc, thu thêm |
| KiemTraThietBi | **Bỏ** | Tình trạng khi trả ghi vào `DonThue.tinh_trang_khi_tra` |
| SuCo | `rentals.SuCo` + `rentals.AnhSuCo` | Mức độ nhẹ / nặng, mô tả, trạng thái xử lý; nhiều ảnh máy hỏng. Tiền đền bù vẫn trừ ở `DonThue.khau_tru_den_bu` |
| LichSuBaoTri | **Bỏ** | Dùng tình trạng máy `Bảo trì` |
| ThongBaoHeThong | `rentals.ThongBao` | |
| DanhGia | `feedback.DanhGia` | |

## 4. Quy trình TO-BE (BCTD2 mục 1.3) sau khi chỉnh sửa

1. Chủ cửa hàng thiết lập thiết bị, gói thuê, bảng giá, mã giảm giá.
2. Khách xem máy, kiểm tra máy trống theo ngày giờ.
3. Khách chọn gói, xác nhận đặt đơn.
4. Hệ thống kiểm tra lại máy trống và giá.
5. Khách cọc lịch 50.000đ online → hệ thống giữ máy, báo "Đặt cọc thành công" cho khách và nhân viên.
   (Khách chưa cọc online thì nhân viên xác nhận đơn, khách cọc tại quầy.)
6. Khách đến nhận máy: nhân viên đối chiếu CCCD, thu tiền thuê và phần cọc còn lại (Thu cọc).
7. Khách trả máy trực tiếp hoặc gửi về.
8. Nhân viên kiểm tra máy, hệ thống tính phụ thu trễ, khấu trừ đền bù, hoàn cọc (Hoàn cọc).
9. Hệ thống cập nhật máy về Sẵn sàng (hoặc Bảo trì) và đơn Hoàn tất.
10. Khách gửi đánh giá, nhân viên duyệt và trả lời.
