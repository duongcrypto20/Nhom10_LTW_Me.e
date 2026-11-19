// me.e_digitalcam - các hành vi nhỏ dùng chung cho mọi trang.

// 1. Tô đậm mục menu của trang đang mở (dùng cho cả menu ngang và thanh dọc).
// Chọn liên kết khớp dài nhất với đường dẫn hiện tại, ví dụ /quan-ly/thiet-bi/5/ khớp "Thiết bị".
var duongDan = window.location.pathname;
var mucChon = null;
document.querySelectorAll('.sidebar nav a, .menu-ngang > a').forEach(function (a) {
  var href = a.getAttribute('href');
  var khop = (href === '/') ? (duongDan === '/') : duongDan.startsWith(href);
  if (khop && (mucChon === null || href.length > mucChon.getAttribute('href').length)) {
    mucChon = a;
  }
});
if (mucChon) {
  mucChon.classList.add('active');
  mucChon.setAttribute('aria-current', 'page');
}

// 2. Hỏi lại trước các thao tác cần xác nhận.
document.querySelectorAll('[data-confirm]').forEach(function (button) {
  button.addEventListener('click', function (event) {
    if (!window.confirm(button.dataset.confirm)) event.preventDefault();
  });
});

// 3. Nút Menu (checkbox ẩn): mở bằng bàn phím, đóng bằng Esc, cập nhật aria-expanded.
document.querySelectorAll('label[aria-controls]').forEach(function (toggle) {
  var input = document.getElementById(toggle.htmlFor);
  if (!input) return;
  function update() { toggle.setAttribute('aria-expanded', String(input.checked)); }
  input.addEventListener('change', update);
  toggle.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault(); input.checked = !input.checked; update();
    }
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && input.checked) { input.checked = false; update(); toggle.focus(); }
  });
});

// 4. Thanh điều hướng ngang: hiện viền và bóng khi trang đã cuộn xuống.
var thanhNav = document.getElementById('thanh-dieu-huong');
if (thanhNav) {
  var capNhatNav = function () { thanhNav.classList.toggle('da-cuon', window.scrollY > 8); };
  capNhatNav();
  window.addEventListener('scroll', capNhatNav, { passive: true });
}

// 5. Trang Ảnh & đánh giá: bấm vào ảnh để xem lớn, chuyển ảnh trước/sau bằng nút hoặc phím mũi tên.
var hopXem = document.getElementById('xem-anh');
var cacAnh = Array.from(document.querySelectorAll('.o-anh[data-anh]'));
if (hopXem && cacAnh.length && hopXem.showModal) {
  var viTri = 0;
  var hienAnh = function (i) {
    viTri = (i + cacAnh.length) % cacAnh.length;
    hopXem.querySelector('img').src = cacAnh[viTri].dataset.anh;
    hopXem.querySelector('.chu-anh').textContent = cacAnh[viTri].dataset.chu + ' (' + (viTri + 1) + '/' + cacAnh.length + ')';
  };
  cacAnh.forEach(function (nut, i) {
    nut.addEventListener('click', function () { hienAnh(i); hopXem.showModal(); });
  });
  hopXem.querySelector('[data-dong]').addEventListener('click', function () { hopXem.close(); });
  hopXem.querySelector('[data-truoc]').addEventListener('click', function () { hienAnh(viTri - 1); });
  hopXem.querySelector('[data-sau]').addEventListener('click', function () { hienAnh(viTri + 1); });
  hopXem.addEventListener('click', function (event) { if (event.target === hopXem) hopXem.close(); });
  hopXem.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowLeft') hienAnh(viTri - 1);
    if (event.key === 'ArrowRight') hienAnh(viTri + 1);
  });
}

// 6. Form viết đánh giá: xem trước ảnh vừa chọn, nút Hủy thì xóa form và đóng ô viết.
document.querySelectorAll('input[type=file][data-xem-truoc]').forEach(function (input) {
  var anh = document.getElementById(input.dataset.xemTruoc);
  input.addEventListener('change', function () {
    if (input.files && input.files[0]) { anh.src = URL.createObjectURL(input.files[0]); anh.hidden = false; }
    else { anh.hidden = true; }
  });
});
document.querySelectorAll('[data-dong-form]').forEach(function (nut) {
  nut.addEventListener('click', function () {
    var hop = nut.closest('details');
    var anh = hop.querySelector('.xem-truoc');
    if (anh) anh.hidden = true;
    hop.open = false;
  });
});
