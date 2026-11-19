# Đối chiếu chức năng với tài liệu nhóm 10


| Use case | Chức năng trong website | Lần này |
|---|---|---|
| UC-1.1 | Chọn máy, số lượng, gói và thời gian thuê | Bỏ giỏ thuê và giao tận nơi: mỗi đơn là một dòng máy, nhận tại cửa hàng |
| UC-1.2 | Xem lại và gửi yêu cầu, tính lại giá, cọc, mã giảm giá | Ghi rõ các bước tiếp theo (xác nhận, cọc online, nhận máy) |
| UC-1.3 | Kiểm tra máy trống theo từng số sê-ri | **Bổ sung:** sau khi kiểm tra hiện lịch tháng, mỗi ngày ghi số máy Trống, Đang thuê, Bảo trì; nhân viên có trang Lịch máy xem từng sê-ri và đơn đang giữ máy |
| UC-1.4 | Nhân viên xác nhận, yêu cầu điều chỉnh, hủy | **Sửa logic:** đơn đã xác nhận mà khách chưa cọc có thể hủy để trả máy về lịch trống |
| UC-1.5 | Trang của tôi, danh sách và chi tiết đơn | Thêm mốc "Đã cọc" trên thanh tiến trình, nút đặt cọc ngay trong danh sách |
| UC-2.1 đến 2.3 | Thiết bị, số sê-ri, tình trạng, danh sách, chi tiết | Đủ 12 dòng máy, ảnh lấy từ thư mục `ẢNH MÁY ẢNH` |
| UC-3.1 đến 3.4 | Gói thuê và bảng giá | Giá đúng theo ảnh `giá máy.jpg`; mô tả gói theo quy định giờ nhận trả |
| UC-4.1 | Gửi đánh giá, ảnh cho đơn đã hoàn tất | **Bổ sung:** bước xác nhận trước khi gửi, báo cho nhân viên có phản hồi mới |
| UC-4.2 | Xem đánh giá đã duyệt, lọc theo máy | Giữ nguyên |
| UC-4.3 | Xử lý phản hồi | **Bổ sung:** trang chi tiết một phản hồi; báo "đã được xử lý" khi duyệt/ẩn lặp lại (E2) |
| UC-4.4 | Thống kê phản hồi theo điều kiện | **Bổ sung:** thống kê theo dòng máy, cạnh thống kê theo sao và gói |
| UC-4.5 | Trả lời phản hồi | Trả lời ngay trên trang chi tiết, khách thấy câu trả lời trong "Đánh giá của tôi" |
| UC-5 (mục 2.6) | Kiểm tra thông tin đơn thuê, quản lý tiền cọc, ảnh máy hỏng khi có sự cố | **Chỉ giữ 3 chức năng:** trang Kiểm tra đơn thuê (tìm theo mã đơn, tên, SĐT); trang Quản lý tiền cọc (chưa thu / đang giữ / đã hoàn; thu cọc khi khách nhận máy, hoàn cọc khi trả, tự trừ phụ thu trễ); trang Sự cố máy (tải tối đa 5 ảnh tình trạng máy hỏng). Bỏ trang giao máy/nhận trả, biên bản kiểm tra từng máy, giao dịch tiền và bảo trì |
| TO-BE bước 6 | Cọc online giữ máy, báo cọc thành công | **Bổ sung:** xác nhận đặt đơn chuyển thẳng sang trang cọc; cọc thành công thì hệ thống tự giữ máy, báo "Đặt cọc thành công" cho khách và nhân viên |
| UC-6.1 đến 6.4 | Tài khoản, đăng nhập, phân quyền | **Bỏ** sổ địa chỉ nhận máy. Chủ cửa hàng có thêm Báo cáo doanh thu |

## Quy định cửa hàng được đưa vào code

| Quy định (ảnh) | Trong code |
|---|---|
| Cọc 700.000đ, máy compact 300.000đ | `taodulieu` đặt `ThietBi.tien_coc` |
| Cọc lịch 50.000đ để giữ máy | Tính vào tổng cọc máy; nhân viên chỉ thu phần cọc còn lại khi khách nhận máy. Đơn đã cọc đủ trước đây không thu thêm |
| Thuê 1 ngày tính 23 giờ, 1 buổi 6 giờ | Gói `1 ngày` 23 giờ, `6 giờ` 6 giờ |
| Trả trễ phụ thu 50.000đ (15 phút đến 1 tiếng) | `rentals/utils.py` `tinh_phi_tra_tre`: dưới 15 phút không tính, sau đó 50.000đ mỗi giờ, làm tròn lên |
| Không nhận hủy lịch | Khách chỉ hủy được khi chưa cọc; đã cọc thì không hủy |
| Đền bù thiệt hại | Nhân viên nhập khấu trừ khi đánh dấu máy hư hỏng; vượt cọc thì thu thêm |

## Luồng đặt thuê sau khi hoàn thiện

1. Khách vào trang Kiểm tra máy trống: chọn dòng máy, ngày giờ nhận, ngày giờ trả, bấm Kiểm tra. Hệ thống hiện lịch tháng (Trống / Đang thuê) và số máy còn trống.
2. Khách chọn gói thuê rồi bấm Xác nhận đặt đơn, hệ thống chuyển thẳng sang trang thanh toán cọc.
3. Khách thanh toán cọc lịch 50.000đ, được tính vào tổng cọc máy. Hệ thống kiểm tra lại máy trống, giữ máy (phân bổ số sê-ri), ghi giao dịch và báo "Đặt cọc thành công". Nếu máy vừa hết thì không ghi nhận cọc. Đơn khách chưa cọc online vẫn có thể được nhân viên xác nhận để khách cọc tại quầy.
4. Đến giờ nhận, nhân viên kiểm tra máy, đối chiếu CCCD, thu tiền thuê và phần cọc máy còn lại rồi giao máy. Ví dụ tổng cọc 700.000đ, đã cọc lịch 50.000đ thì chỉ thu thêm 650.000đ tiền cọc.
5. Khách trả trực tiếp hoặc gửi máy về. Nhân viên kiểm tra máy, hệ thống tính phụ thu trễ, hoàn cọc.
6. Máy về trạng thái sẵn sàng (hoặc bảo trì nếu hư hỏng). Khách viết đánh giá.

## Phạm vi thanh toán

Cổng thanh toán cọc là **mô phỏng** cho đồ án: khi khách bấm "Thanh toán cọc online" hệ thống ghi nhận cọc thành công ngay.
Muốn dùng cổng thật (VNPay, MoMo) chỉ cần gọi `services.dat_coc_online` khi cổng báo thanh toán thành công.
Nếu đặt các biến `MEE_BANK_ID`, `MEE_BANK_ACCOUNT`, `MEE_BANK_HOLDER`, trang đặt cọc hiện thêm mã VietQR của cửa hàng.

## Kiểm chứng

```powershell
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py taodulieu
.venv\Scripts\python.exe manage.py test --noinput
```
