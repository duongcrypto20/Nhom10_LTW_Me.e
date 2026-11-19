from django import forms

from .models import DanhGia
from catalog.models import GoiThue, ThietBi
from rentals.models import DonThue


class DanhGiaForm(forms.ModelForm):
    """UC-4.1: Gửi phản hồi."""
    class Meta:
        model = DanhGia
        fields = ['so_sao', 'noi_dung', 'anh']
        widgets = {'noi_dung': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Chia sẻ trải nghiệm sử dụng máy và dịch vụ giao nhận…'}),
                   'anh': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'})}
        labels = {'noi_dung': 'Nội dung feedback', 'anh': 'Đăng ảnh feedback (tùy chọn)'}
        help_texts = {'anh': 'Chọn ảnh JPG, PNG hoặc WebP, tối đa 5MB.'}

    def clean_noi_dung(self):
        noi_dung = self.cleaned_data['noi_dung'].strip()
        if len(noi_dung) < 5:
            raise forms.ValidationError('Nội dung phản hồi quá ngắn.')
        return noi_dung

    def clean_anh(self):
        anh = self.cleaned_data.get('anh')
        if anh and getattr(anh, 'size', 0) > 5 * 1024 * 1024:
            raise forms.ValidationError('Ảnh phản hồi tối đa 5MB.')
        if anh and hasattr(anh, 'image') and anh.image.format not in ('JPEG', 'PNG', 'WEBP'):
            raise forms.ValidationError('Vui lòng chọn ảnh JPG, PNG hoặc WebP.')
        return anh


def don_cho_danh_gia(user):
    """BR01, BR03: chỉ đơn đã hoàn tất của chính khách và chưa có phản hồi mới được đánh giá."""
    return DonThue.objects.filter(khach_hang=user, trang_thai=DonThue.HOAN_TAT, danh_gia__isnull=True)


class ChonDonField(forms.ModelChoiceField):
    def label_from_instance(self, don):
        return f'{don.ma} · {don.ten_thiet_bi} · trả máy {don.tra_thuc_te:%d/%m/%Y}' if don.tra_thuc_te else f'{don.ma} · {don.ten_thiet_bi}'


class VietDanhGiaForm(DanhGiaForm):
    """Form trong ô "Viết đánh giá" ở trang Đánh giá: chọn đơn đã thuê, chọn sao, viết nội dung, tải ảnh."""
    class Meta(DanhGiaForm.Meta):
        fields = ['don', 'so_sao', 'noi_dung', 'anh']
        field_classes = {'don': ChonDonField}
        labels = dict(DanhGiaForm.Meta.labels, don='Đơn thuê đã sử dụng')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['don'].queryset = don_cho_danh_gia(user) if user else DonThue.objects.none()
        self.fields['don'].empty_label = 'Chọn đơn bạn muốn đánh giá'


class TraLoiForm(forms.ModelForm):
    """UC-4.5: Trả lời phản hồi."""
    class Meta:
        model = DanhGia
        fields = ['tra_loi']
        widgets = {'tra_loi': forms.Textarea(attrs={'rows': 4})}

    def clean_tra_loi(self):
        tra_loi = self.cleaned_data['tra_loi'].strip()
        if not tra_loi:
            raise forms.ValidationError('Vui lòng nhập nội dung trả lời.')
        return tra_loi


class LocPhanHoiForm(forms.Form):
    thiet_bi = forms.ModelChoiceField(label='Thiết bị', queryset=ThietBi.objects.all(), required=False, empty_label='Tất cả thiết bị')
    goi_thue = forms.ModelChoiceField(label='Gói thuê', queryset=GoiThue.objects.all(), required=False, empty_label='Tất cả gói thuê')
    so_sao = forms.ChoiceField(label='Điểm đánh giá', choices=[('', 'Tất cả mức sao')] + DanhGia.SO_SAO, required=False)
    tu_ngay = forms.DateField(label='Từ ngày', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    den_ngay = forms.DateField(label='Đến ngày', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    trang_thai = forms.ChoiceField(label='Trạng thái', choices=[('', 'Tất cả trạng thái')] + DanhGia.TRANG_THAI, required=False)
    tra_loi = forms.ChoiceField(label='Trả lời', choices=[('', 'Tất cả'), ('co', 'Đã trả lời'), ('chua', 'Chưa trả lời')], required=False)

    def clean(self):
        data = super().clean()
        if data.get('tu_ngay') and data.get('den_ngay') and data['tu_ngay'] > data['den_ngay']:
            self.add_error('den_ngay', 'Ngày kết thúc phải từ ngày bắt đầu trở đi.')
        return data
