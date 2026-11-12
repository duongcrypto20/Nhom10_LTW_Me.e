ME.E Nhom10 — ME.E Digitalcam

Website Django cho dịch vụ cho thuê máy ảnh ME.E Digitalcam. Hệ thống có danh mục và bảng giá, gửi yêu cầu thuê có kiểm tra lịch, tài khoản khách hàng, địa chỉ, thông báo, feedback có duyệt và khu vực quản trị nhân viên.

Chạy:
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_catalog
python manage.py createsuperuser
python manage.py runserver
```

Mở `http://127.0.0.1:8000/`. Trang quản trị nhân viên ở `http://127.0.0.1:8000/admin/`.

Nếu PowerShell chặn kích hoạt môi trường ảo, chạy lệnh cài đặt bằng `.\.venv\Scripts\python.exe` và `.\.venv\Scripts\pip.exe` thay vì đổi chính sách hệ thống.

 Chức năng

<<<<<<< 
- **Máy ảnh:** 12 mẫu Canon/Fujifilm, tìm kiếm, lọc hãng, sắp xếp theo giá và xem bảng giá theo 6 giờ, 1 ngày, 2 ngày hoặc 3 ngày.
- **Đặt thuê:** chọn thời lượng, lịch nhận, số lượng và cách nhận máy; xem lại giá; kiểm tra số máy khả dụng; gửi yêu cầu vào trạng thái chờ xác nhận. Lịch được giữ đến khi cửa hàng xác nhận hoặc từ chối yêu cầu.
- **Tài khoản:** đăng ký bằng email, đăng nhập, cập nhật hồ sơ, quản lý địa chỉ, xem thông báo và đơn thuê của mình.
- **Vận hành cửa hàng:** Django Admin quản lý máy, tồn máy, giá thuê, đơn thuê, tiền cọc, tình trạng giao/trả và lịch sử đơn.
- **Feedback:** khách hàng gửi đánh giá sau khi đơn đã hoàn tất; phản hồi và ảnh chỉ công khai sau khi nhân viên duyệt. 
- **Quy định:** giá, giờ thuê, tiền cọc, bảo quản và đền bù dựa trên tài liệu/ảnh người dùng cung cấp.

## Dữ liệu 

- Bảng giá và ảnh máy được nhập từ thư mục tài liệu trong workspace.
- Hệ thống đặt số lượng khởi tạo là **1 máy cho mỗi mẫu** vì tài liệu chưa có số lượng máy vật lý; hãy cập nhật trường “Số máy có thể cho thuê” trong trang quản trị trước khi nhận đơn thật.
- Mức cọc của từng mẫu để trống cho đến khi cửa hàng xác nhận. Website không thu tiền trực tuyến, không lưu CCCD và không yêu cầu khách tải ảnh giấy tờ.
- Địa chỉ cửa hàng, kênh liên hệ, cổng thanh toán, email gửi thư và cấu hình triển khai chưa có trong tài liệu nên chưa được tự đặt. Đơn giao theo địa chỉ chỉ dùng địa chỉ khách nhập và vẫn cần cửa hàng xác nhận.
- Ảnh feedback nguồn được giữ trong `static/images/feedback/`
=======
-Máy ảnh:12 mẫu Canon/Fujifilm, tìm kiếm, lọc hãng, sắp xếp theo giá và xem bảng giá theo 6 giờ, 1 ngày, 2 ngày hoặc 3 ngày.
- Đặt thuê:chọn thời lượng, lịch nhận, số lượng và cách nhận máy; xem lại giá; kiểm tra số máy khả dụng; gửi yêu cầu vào trạng thái chờ xác nhận. Lịch được giữ đến khi cửa hàng xác nhận hoặc từ chối yêu cầu.
- Tài khoản: đăng ký bằng email, đăng nhập, cập nhật hồ sơ, quản lý địa chỉ, xem thông báo và đơn thuê của mình.
- Vận hành cửa hàng: Django Admin quản lý máy, tồn máy, giá thuê, đơn thuê, tiền cọc, tình trạng giao/trả và lịch sử đơn
- Feedback:khách hàng gửi đánh giá sau khi đơn đã hoàn tất; phản hồi và ảnh chỉ công khai sau khi nhân viên duyệt. 
- Quy định:giá, giờ thuê, tiền cọc, bảo quản và đền bù dựa trên tài liệu/ảnh người dùng cung cấp.


>>>>>>> Stashed changes

