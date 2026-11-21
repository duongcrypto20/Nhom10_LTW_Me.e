// Các tiện ích của trang chức năng. Trang chủ không nạp tệp này.

// Đưa bàn phím về ô cần sửa sau khi Django trả lại form có lỗi.
var oLoiDauTien = document.querySelector('[aria-invalid="true"]');
if (oLoiDauTien) {
  oLoiDauTien.focus();
}

// Báo trạng thái đang gửi, giữ nguyên tên và giá trị của nút submit để Django nhận đủ dữ liệu.
document.querySelectorAll('form[method="post"]').forEach(function (form) {
  form.addEventListener('submit', function (event) {
    if (!event.defaultPrevented && event.submitter) {
      event.submitter.setAttribute('aria-busy', 'true');
    }
  });
});

// Nút quay lại của trình duyệt có thể khôi phục cả trang và trạng thái nút cũ.
window.addEventListener('pageshow', function () {
  document.querySelectorAll('[aria-busy="true"]').forEach(function (nut) {
    nut.removeAttribute('aria-busy');
  });
});
