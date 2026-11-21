"""
Các form của app catalog.

    ThietBiForm         : thêm / sửa thiết bị (UC-2.1, UC-2.2)
    MayForm             : thêm một máy vật lý theo số sê-ri
    GoiThueForm         : thêm / sửa gói thuê (UC-3.1, UC-3.3)
    MaGiamGiaForm       : thêm / sửa mã giảm giá
    LoaiThietBiForm     : thêm danh mục thiết bị
    KiemTraMayTrongForm : kiểm tra nhanh số máy trống (giờ nhận, giờ trả, số lượng)
    KiemTraLichForm     : trang Kiểm tra máy trống (chọn máy, ngày giờ nhận / trả)
"""
from datetime import datetime

from django import forms

from config.form_co_ban import FormCoBan, ModelFormCoBan
from django.core.validators import validate_slug
from django.utils import timezone

from .models import GoiThue, LoaiThietBi, MaGiamGia, May, ThietBi

DINH_DANG_GIO = '%Y-%m-%dT%H:%M'
SO_GIAY_30_NGAY = 30 * 24 * 3600


def o_chon_gio():
    """Ô chọn ngày giờ của trình duyệt (input type=datetime-local)."""
    return forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=DINH_DANG_GIO)


# ===========================================================================
# 1. THIẾT BỊ VÀ MÁY
# ===========================================================================

class ThietBiForm(ModelFormCoBan):
    """Form thêm mới và cập nhật thiết bị (UC-2.1, UC-2.2)."""

    class Meta:
        model = ThietBi
        fields = [
            'ma', 'hang', 'ten', 'danh_muc', 'gia_tri_den_bu', 'tien_coc', 'thong_so',
            'mo_ta', 'phu_hop', 'anh', 'huong_dan', 'video_huong_dan', 'ngung_cung_cap',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['danh_muc'].required = True

    def clean_ma(self):
        # Mã dùng trong URL /may-anh/<ma>/ nên không được có dấu cách hoặc dấu /
        ma = self.cleaned_data['ma'].strip().lower()
        validate_slug(ma)
        return ma

    def clean_anh(self):
        anh = self.cleaned_data.get('anh')
        # Ảnh mới tải lên mới có thuộc tính size; giới hạn 1MB theo thiết kế
        if anh and hasattr(anh, 'size') and anh.size > 1024 * 1024:
            raise forms.ValidationError('Ảnh thiết bị tối đa 1MB.')
        return anh

    def save(self, commit=True):
        thiet_bi = super().save(commit=False)
        # Trường loai giữ cùng mã với danh mục để lọc nhanh ở trang danh sách
        thiet_bi.loai = self.cleaned_data['danh_muc'].ma
        if commit:
            thiet_bi.save()
        return thiet_bi


class MayForm(ModelFormCoBan):
    """Form thêm một máy vật lý theo số sê-ri."""

    class Meta:
        model = May
        fields = ['so_seri', 'tinh_trang', 'ngay_mua']
        widgets = {'ngay_mua': forms.DateInput(attrs={'type': 'date'})}

    def clean_tinh_trang(self):
        tinh_trang = self.cleaned_data['tinh_trang']
        if tinh_trang == May.DANG_THUE:
            raise forms.ValidationError('Máy chỉ chuyển sang Đang thuê khi khách nhận máy.')
        return tinh_trang


# ===========================================================================
# 2. GÓI THUÊ VÀ MÃ GIẢM GIÁ
# ===========================================================================

class GoiThueForm(ModelFormCoBan):
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
        du_lieu = super().clean()
        if du_lieu.get('tuy_chinh') and du_lieu.get('so_gio_toi_da', 0) > 720:
            self.add_error('so_gio_toi_da', 'Gói tùy chỉnh hỗ trợ tối đa 720 giờ (30 ngày).')
        return du_lieu


class MaGiamGiaForm(ModelFormCoBan):
    """Form thêm / sửa mã giảm giá. Mã đã có đơn dùng thì không cho đổi tên mã."""

    class Meta:
        model = MaGiamGia
        fields = ['ma', 'loai', 'gia_tri', 'so_luot', 'dang_ap_dung', 'ngay_bat_dau', 'ngay_ket_thuc']
        widgets = {
            'ngay_bat_dau': o_chon_gio(),
            'ngay_ket_thuc': o_chon_gio(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.da_co_don_dung():
            self.fields['ma'].disabled = True
            self.fields['ma'].help_text = (
                'Mã đã phát sinh đơn thuê. Bạn có thể cập nhật giá trị, số lượt và hiệu lực.'
            )

    def clean_ma(self):
        return self.cleaned_data['ma'].strip().upper()

    def clean(self):
        du_lieu = super().clean()
        if du_lieu.get('loai') == MaGiamGia.PHAN_TRAM and du_lieu.get('gia_tri', 0) > 100:
            self.add_error('gia_tri', 'Giảm theo phần trăm không được vượt quá 100.')

        bat_dau = du_lieu.get('ngay_bat_dau')
        ket_thuc = du_lieu.get('ngay_ket_thuc')
        if bat_dau and ket_thuc and ket_thuc <= bat_dau:
            self.add_error('ngay_ket_thuc', 'Ngày kết thúc phải sau ngày bắt đầu.')
        return du_lieu


class LoaiThietBiForm(ModelFormCoBan):
    """Form thêm danh mục thiết bị."""

    class Meta:
        model = LoaiThietBi
        fields = ['ma', 'ten']


# ===========================================================================
# 3. KIỂM TRA MÁY TRỐNG
# ===========================================================================

class KiemTraMayTrongForm(FormCoBan):
    """Kiểm tra nhanh số máy trống theo giờ nhận, giờ trả và số lượng."""

    gio_nhan = forms.DateTimeField(label='Giờ nhận máy', widget=o_chon_gio(), input_formats=[DINH_DANG_GIO])
    gio_tra = forms.DateTimeField(label='Giờ trả dự kiến', widget=o_chon_gio(), input_formats=[DINH_DANG_GIO])
    so_luong = forms.IntegerField(label='Số máy cần thuê', min_value=1, max_value=20, initial=1)

    def clean(self):
        du_lieu = super().clean()
        nhan = du_lieu.get('gio_nhan')
        tra = du_lieu.get('gio_tra')

        if nhan and nhan <= timezone.now():
            self.add_error('gio_nhan', 'Giờ nhận máy phải ở tương lai.')
        if nhan and tra:
            if tra <= nhan:
                self.add_error('gio_tra', 'Giờ trả máy phải sau giờ nhận.')
            elif (tra - nhan).total_seconds() > SO_GIAY_30_NGAY:
                self.add_error('gio_tra', 'Vui lòng kiểm tra khoảng thuê tối đa 30 ngày.')
        return du_lieu


class KiemTraLichForm(FormCoBan):
    """Trang Kiểm tra máy trống: chọn dòng máy, ngày giờ nhận và ngày giờ trả."""

    thiet_bi = forms.ModelChoiceField(
        label='Dòng máy',
        queryset=ThietBi.objects.filter(ngung_cung_cap=False),
        empty_label='Chọn dòng máy',
        to_field_name='ma',
    )
    ngay_nhan = forms.DateField(
        label='Ngày nhận',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    gio_nhan = forms.TimeField(
        label='Giờ nhận', initial='09:00',
        widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
    )
    ngay_tra = forms.DateField(
        label='Ngày trả',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    gio_tra = forms.TimeField(
        label='Giờ trả', initial='09:00',
        widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Không cho chọn ngày trong quá khứ trên lịch của trình duyệt
        hom_nay = timezone.localdate().isoformat()
        self.fields['ngay_nhan'].widget.attrs['min'] = hom_nay
        self.fields['ngay_tra'].widget.attrs['min'] = hom_nay

    def clean(self):
        du_lieu = super().clean()
        if not all(du_lieu.get(ten) for ten in ('ngay_nhan', 'gio_nhan', 'ngay_tra', 'gio_tra')):
            return du_lieu

        # Ghép ngày và giờ thành thời điểm nhận / trả theo giờ Việt Nam
        nhan = timezone.make_aware(datetime.combine(du_lieu['ngay_nhan'], du_lieu['gio_nhan']))
        tra = timezone.make_aware(datetime.combine(du_lieu['ngay_tra'], du_lieu['gio_tra']))

        if nhan <= timezone.now():
            self.add_error('gio_nhan', 'Thời gian nhận máy phải ở tương lai.')
        elif tra <= nhan:
            self.add_error('gio_tra', 'Thời gian trả phải sau thời gian nhận.')
        elif (tra - nhan).total_seconds() > SO_GIAY_30_NGAY:
            self.add_error('ngay_tra', 'Chỉ kiểm tra được khoảng thuê tối đa 30 ngày.')

        du_lieu['nhan'] = nhan
        du_lieu['tra'] = tra
        return du_lieu
