from django import forms
from datetime import datetime
from django.utils import timezone

from .models import GoiThue, LoaiThietBi, MaGiamGia, May, ThietBi


class ThietBiForm(forms.ModelForm):
    """Form thêm mới và cập nhật thiết bị (UC-2.1, UC-2.2)."""
    class Meta:
        model = ThietBi
        fields = ['ma', 'hang', 'ten', 'danh_muc', 'gia_tri_den_bu', 'tien_coc', 'thong_so',
                  'mo_ta', 'phu_hop', 'anh', 'huong_dan', 'video_huong_dan', 'ngung_cung_cap']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['danh_muc'].required = True

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.loai = self.cleaned_data['danh_muc'].ma
        if commit:
            obj.save()
        return obj

    def clean_anh(self):
        anh = self.cleaned_data.get('anh')
        # Ảnh mới tải lên có thuộc tính size; giới hạn 1MB theo thiết kế
        if anh and hasattr(anh, 'size') and anh.size > 1024 * 1024:
            raise forms.ValidationError('Ảnh thiết bị tối đa 1MB.')
        return anh


class MayForm(forms.ModelForm):
    """Form thêm một máy vật lý theo số sê-ri."""
    class Meta:
        model = May
        fields = ['so_seri', 'tinh_trang', 'ngay_mua']
        widgets = {'ngay_mua': forms.DateInput(attrs={'type': 'date'})}

    def clean_tinh_trang(self):
        value = self.cleaned_data['tinh_trang']
        if value == May.DANG_THUE:
            raise forms.ValidationError('Máy chỉ chuyển sang Đang thuê sau khi giao cho một đơn thuê.')
        return value


class GoiThueForm(forms.ModelForm):
    """Form thêm mới và cập nhật gói thuê (UC-3.1, UC-3.3)."""
    class Meta:
        model = GoiThue
        fields = ['ten', 'so_gio_toi_da', 'mo_ta', 'dang_cung_cap', 'tuy_chinh']

    def clean_so_gio_toi_da(self):
        so_gio = self.cleaned_data['so_gio_toi_da']
        if so_gio <= 0:
            raise forms.ValidationError('Thời lượng tối đa phải lớn hơn 0.')
        return so_gio

    def clean(self):
        data = super().clean()
        if data.get('tuy_chinh') and data.get('so_gio_toi_da', 0) > 720:
            self.add_error('so_gio_toi_da', 'Gói tùy chỉnh hỗ trợ tối đa 720 giờ (30 ngày).')
        return data


class MaGiamGiaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            from rentals.models import DonThue
            if DonThue.objects.filter(ma_giam_gia=self.instance.ma).exists():
                self.fields['ma'].disabled = True
                self.fields['ma'].help_text = 'Mã đã phát sinh đơn thuê. Bạn có thể cập nhật giá trị, số lượt và hiệu lực.'

    class Meta:
        model = MaGiamGia
        fields = ['ma', 'loai', 'gia_tri', 'so_luot', 'dang_ap_dung', 'ngay_bat_dau', 'ngay_ket_thuc']
        widgets = {name: forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')
                   for name in ('ngay_bat_dau', 'ngay_ket_thuc')}

    def clean_ma(self):
        return self.cleaned_data['ma'].strip().upper()

    def clean(self):
        du_lieu = super().clean()
        if du_lieu.get('loai') == MaGiamGia.PHAN_TRAM and du_lieu.get('gia_tri', 0) > 100:
            self.add_error('gia_tri', 'Giảm theo phần trăm không được vượt quá 100.')
        if du_lieu.get('ngay_bat_dau') and du_lieu.get('ngay_ket_thuc') and du_lieu['ngay_ket_thuc'] <= du_lieu['ngay_bat_dau']:
            self.add_error('ngay_ket_thuc', 'Ngày kết thúc phải sau ngày bắt đầu.')
        return du_lieu


class LoaiThietBiForm(forms.ModelForm):
    class Meta:
        model = LoaiThietBi
        fields = ['ma', 'ten']


class KiemTraMayTrongForm(forms.Form):
    gio_nhan = forms.DateTimeField(label='Giờ nhận máy', widget=forms.DateTimeInput(
        attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'), input_formats=['%Y-%m-%dT%H:%M'])
    gio_tra = forms.DateTimeField(label='Giờ trả dự kiến', widget=forms.DateTimeInput(
        attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'), input_formats=['%Y-%m-%dT%H:%M'])
    so_luong = forms.IntegerField(label='Số máy cần thuê', min_value=1, max_value=20, initial=1)
    chi_trong = forms.BooleanField(label='Chỉ hiện thiết bị đủ máy trống', required=False)

    def clean(self):
        data = super().clean()
        nhan, tra = data.get('gio_nhan'), data.get('gio_tra')
        if nhan and nhan <= timezone.now():
            self.add_error('gio_nhan', 'Giờ nhận máy phải ở tương lai.')
        if nhan and tra:
            if tra <= nhan:
                self.add_error('gio_tra', 'Giờ trả máy phải sau giờ nhận.')
            elif (tra - nhan).total_seconds() > 30 * 24 * 3600:
                self.add_error('gio_tra', 'Vui lòng kiểm tra khoảng thuê tối đa 30 ngày.')
        return data


class KiemTraLichForm(forms.Form):
    """Form kiểm tra máy trống: chọn dòng máy, ngày giờ nhận và ngày giờ trả."""
    thiet_bi = forms.ModelChoiceField(label='Dòng máy', queryset=ThietBi.objects.filter(ngung_cung_cap=False),
                                      empty_label='Chọn dòng máy', to_field_name='ma')
    ngay_nhan = forms.DateField(label='Ngày nhận', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    gio_nhan = forms.TimeField(label='Giờ nhận', initial='09:00', widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'))
    ngay_tra = forms.DateField(label='Ngày trả', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    gio_tra = forms.TimeField(label='Giờ trả', initial='09:00', widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hom_nay = timezone.localdate().isoformat()
        self.fields['ngay_nhan'].widget.attrs['min'] = hom_nay
        self.fields['ngay_tra'].widget.attrs['min'] = hom_nay

    def clean(self):
        data = super().clean()
        if not all(data.get(k) for k in ('ngay_nhan', 'gio_nhan', 'ngay_tra', 'gio_tra')):
            return data
        # Ghép ngày và giờ thành thời điểm nhận / trả theo giờ Việt Nam
        nhan = timezone.make_aware(datetime.combine(data['ngay_nhan'], data['gio_nhan']))
        tra = timezone.make_aware(datetime.combine(data['ngay_tra'], data['gio_tra']))
        if nhan <= timezone.now():
            self.add_error('gio_nhan', 'Thời gian nhận máy phải ở tương lai.')
        elif tra <= nhan:
            self.add_error('gio_tra', 'Thời gian trả phải sau thời gian nhận.')
        elif (tra - nhan).total_seconds() > 30 * 24 * 3600:
            self.add_error('ngay_tra', 'Chỉ kiểm tra được khoảng thuê tối đa 30 ngày.')
        data['nhan'], data['tra'] = nhan, tra
        return data
