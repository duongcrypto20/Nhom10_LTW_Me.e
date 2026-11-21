"""
Các form của app feedback.

    DanhGiaForm     : nội dung đánh giá (số sao, nội dung, ảnh) - UC-4.1
    VietDanhGiaForm : form ở trang Đánh giá, có thêm ô chọn đơn đã thuê
    TraLoiForm      : nhân viên trả lời phản hồi - UC-4.5
    LocPhanHoiForm  : lọc phản hồi theo máy, gói, số sao, ngày... - UC-4.4
"""
from django import forms

from config.form_co_ban import FormCoBan, ModelFormCoBan

from catalog.models import GoiThue, ThietBi
from rentals.models import DonThue

from .models import DanhGia

KICH_THUOC_ANH_TOI_DA = 5 * 1024 * 1024  # 5MB


def don_cho_danh_gia(user):
    """BR01, BR03: đơn đã hoàn tất của chính khách và chưa có phản hồi."""
    return DonThue.objects.filter(
        khach_hang=user,
        trang_thai=DonThue.HOAN_TAT,
        danh_gia__isnull=True,
    )


class DanhGiaForm(ModelFormCoBan):
    """UC-4.1: gửi phản hồi gồm số sao, nội dung và ảnh (không bắt buộc)."""

    class Meta:
        model = DanhGia
        fields = ['so_sao', 'noi_dung', 'anh']
        widgets = {
            'noi_dung': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Chia sẻ trải nghiệm sử dụng máy và dịch vụ của cửa hàng',
            }),
            'anh': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        }
        labels = {
            'noi_dung': 'Nội dung feedback',
            'anh': 'Đăng ảnh feedback (tùy chọn)',
        }
        help_texts = {'anh': 'Chọn ảnh JPG, PNG hoặc WebP, tối đa 5MB.'}

    def clean_noi_dung(self):
        noi_dung = self.cleaned_data['noi_dung'].strip()
        if len(noi_dung) < 5:
            raise forms.ValidationError('Nội dung phản hồi quá ngắn.')
        return noi_dung

    def clean_anh(self):
        anh = self.cleaned_data.get('anh')
        if not anh:
            return anh
        if getattr(anh, 'size', 0) > KICH_THUOC_ANH_TOI_DA:
            raise forms.ValidationError('Ảnh phản hồi tối đa 5MB.')
        # Kiểm tra định dạng thật của ảnh (Pillow đọc nội dung file, không tin đuôi file)
        if hasattr(anh, 'image') and anh.image.format not in ('JPEG', 'PNG', 'WEBP'):
            raise forms.ValidationError('Vui lòng chọn ảnh JPG, PNG hoặc WebP.')
        return anh


class ChonDonField(forms.ModelChoiceField):
    """Ô chọn đơn, hiển thị mã đơn, tên máy và ngày trả."""

    def label_from_instance(self, don):
        if don.tra_thuc_te:
            return f'{don.ma}, {don.ten_thiet_bi}, trả máy {don.tra_thuc_te:%d/%m/%Y}'
        return f'{don.ma}, {don.ten_thiet_bi}'


class VietDanhGiaForm(DanhGiaForm):
    """Form ở trang Đánh giá: chọn đơn đã thuê, chọn sao, viết nội dung, tải ảnh."""

    class Meta(DanhGiaForm.Meta):
        fields = ['don', 'so_sao', 'noi_dung', 'anh']
        field_classes = {'don': ChonDonField}
        labels = dict(DanhGiaForm.Meta.labels, don='Đơn thuê đã sử dụng')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Chỉ cho chọn đơn của chính khách đang đăng nhập
        self.fields['don'].queryset = don_cho_danh_gia(user) if user else DonThue.objects.none()
        self.fields['don'].empty_label = 'Chọn đơn bạn muốn đánh giá'


class TraLoiForm(ModelFormCoBan):
    """UC-4.5: nhân viên trả lời phản hồi."""

    class Meta:
        model = DanhGia
        fields = ['tra_loi']
        widgets = {'tra_loi': forms.Textarea(attrs={'rows': 4})}

    def clean_tra_loi(self):
        tra_loi = self.cleaned_data['tra_loi'].strip()
        if not tra_loi:
            raise forms.ValidationError('Vui lòng nhập nội dung trả lời.')
        return tra_loi


class LocPhanHoiForm(FormCoBan):
    """UC-4.4: các điều kiện lọc và thống kê phản hồi."""

    thiet_bi = forms.ModelChoiceField(
        label='Thiết bị', queryset=ThietBi.objects.all(),
        required=False, empty_label='Tất cả thiết bị',
    )
    goi_thue = forms.ModelChoiceField(
        label='Gói thuê', queryset=GoiThue.objects.all(),
        required=False, empty_label='Tất cả gói thuê',
    )
    so_sao = forms.ChoiceField(
        label='Điểm đánh giá', required=False,
        choices=[('', 'Tất cả mức sao')] + DanhGia.SO_SAO,
    )
    tu_ngay = forms.DateField(
        label='Từ ngày', required=False, widget=forms.DateInput(attrs={'type': 'date'}),
    )
    den_ngay = forms.DateField(
        label='Đến ngày', required=False, widget=forms.DateInput(attrs={'type': 'date'}),
    )
    trang_thai = forms.ChoiceField(
        label='Trạng thái', required=False,
        choices=[('', 'Tất cả trạng thái')] + DanhGia.TRANG_THAI,
    )
    tra_loi = forms.ChoiceField(
        label='Trả lời', required=False,
        choices=[('', 'Tất cả'), ('co', 'Đã trả lời'), ('chua', 'Chưa trả lời')],
    )

    def clean(self):
        du_lieu = super().clean()
        tu_ngay = du_lieu.get('tu_ngay')
        den_ngay = du_lieu.get('den_ngay')
        if tu_ngay and den_ngay and tu_ngay > den_ngay:
            self.add_error('den_ngay', 'Ngày kết thúc phải từ ngày bắt đầu trở đi.')
        return du_lieu
