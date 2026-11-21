"""
Form cơ sở dùng chung cho cả dự án: thông báo lỗi tiếng Việt rõ ràng, có tên ô bị lỗi.

Thông báo mặc định của Django khá chung chung ("Trường này là bắt buộc.").
Hai lớp FormCoBan và ModelFormCoBan tự thay bằng thông báo có tên ô, ví dụ:
    "Vui lòng nhập Họ tên."
    "Email không đúng định dạng, ví dụ: ten@gmail.com."
    "Số lượng phải từ 1 trở lên."

Cách dùng: kế thừa FormCoBan thay cho forms.Form, ModelFormCoBan thay cho forms.ModelForm.
"""
from django import forms


def thong_bao_loi(field, nhan):
    """Tạo bộ thông báo lỗi cho một ô nhập dựa vào loại ô và nhãn của ô."""
    nhan = str(nhan or 'ô này')
    loi = {}

    # ----- Bỏ trống ô bắt buộc -----
    if isinstance(field, (forms.ChoiceField, forms.ModelChoiceField)):
        loi['required'] = f'Vui lòng chọn {nhan}.'
    elif isinstance(field, forms.FileField):
        loi['required'] = f'Vui lòng tải lên {nhan}.'
    elif isinstance(field, forms.BooleanField):
        loi['required'] = 'Vui lòng đánh dấu xác nhận trước khi tiếp tục.'
    else:
        loi['required'] = f'Vui lòng nhập {nhan}.'

    # ----- Sai định dạng theo từng loại ô -----
    if isinstance(field, forms.EmailField):
        loi['invalid'] = f'{nhan} không đúng định dạng, ví dụ: ten@gmail.com.'
    elif isinstance(field, forms.DateTimeField):
        loi['invalid'] = f'{nhan} không hợp lệ. Vui lòng chọn đủ ngày và giờ.'
    elif isinstance(field, forms.DateField):
        loi['invalid'] = f'{nhan} không hợp lệ. Vui lòng chọn ngày theo dạng ngày/tháng/năm.'
    elif isinstance(field, forms.TimeField):
        loi['invalid'] = f'{nhan} không hợp lệ. Vui lòng chọn giờ:phút.'
    elif isinstance(field, forms.IntegerField):
        loi['invalid'] = f'{nhan} phải là số nguyên, không có dấu chấm hay chữ.'
    elif isinstance(field, forms.URLField):
        loi['invalid'] = f'{nhan} phải là đường dẫn đầy đủ, ví dụ: https://youtube.com/...'
    elif isinstance(field, forms.ImageField):
        loi['invalid_image'] = f'{nhan}: file tải lên không phải ảnh hoặc ảnh bị hỏng.'

    # ----- Giới hạn giá trị và độ dài -----
    loi['min_value'] = f'{nhan} phải từ %(limit_value)s trở lên.'
    loi['max_value'] = f'{nhan} không được lớn hơn %(limit_value)s.'
    loi['min_length'] = f'{nhan} phải có ít nhất %(limit_value)d ký tự (hiện có %(show_value)d).'
    loi['max_length'] = f'{nhan} tối đa %(limit_value)d ký tự (hiện có %(show_value)d).'

    # ----- Lựa chọn không có trong danh sách -----
    loi['invalid_choice'] = f'Lựa chọn ở ô {nhan} không hợp lệ. Vui lòng chọn lại.'
    loi['invalid_pk_value'] = f'Lựa chọn ở ô {nhan} không hợp lệ. Vui lòng chọn lại.'
    return loi


def ap_dung_thong_bao_loi(form):
    """Gắn thông báo lỗi tiếng Việt cho mọi ô của form (giữ thông báo riêng nếu form đã tự đặt)."""
    for field in form.fields.values():
        thong_bao_moi = thong_bao_loi(field, field.label)
        thong_bao_moi.update(getattr(field, 'thong_bao_rieng', {}))
        field.error_messages.update(thong_bao_moi)


class FormCoBan(forms.Form):
    """forms.Form có thông báo lỗi tiếng Việt kèm tên ô."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ap_dung_thong_bao_loi(self)


class ModelFormCoBan(forms.ModelForm):
    """forms.ModelForm có thông báo lỗi tiếng Việt kèm tên ô."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ap_dung_thong_bao_loi(self)
