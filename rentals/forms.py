"""
Các form của app rentals.

    DatThueForm     : khách chọn gói, giờ nhận, giờ trả (UC-1.1)
    XuLyYeuCauForm  : nhân viên nhập lý do điều chỉnh / hủy (UC-1.4)
    ThuCocForm      : nhân viên thu cọc khi khách nhận máy
    HoanCocForm     : nhân viên hoàn cọc khi khách trả máy
    GhiNhanSuCoForm : nhân viên ghi nhận sự cố máy (mức độ, mô tả, ảnh hỏng)
    XuLySuCoForm    : cập nhật kết quả xử lý sự cố
"""
from django import forms
from django.db.models import Q
from django.utils import timezone

from catalog.models import GoiThue, MaGiamGia, May

from .models import DonThue, SuCo

DINH_DANG_GIO = '%Y-%m-%dT%H:%M'


def o_chon_gio():
    """Ô chọn ngày giờ của trình duyệt (input type=datetime-local)."""
    return forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=DINH_DANG_GIO)


# ===========================================================================
# 1. KHÁCH ĐẶT THUÊ
# ===========================================================================

class DatThueForm(forms.Form):
    """UC-1.1: chọn số lượng, gói thuê và thời gian thuê cho một dòng máy."""

    field_order = ['so_luong', 'goi_thue', 'gio_nhan', 'gio_tra', 'ma_giam_gia', 'ghi_chu']

    so_luong = forms.IntegerField(
        label='Số lượng', min_value=1, max_value=20, initial=1, required=False,
    )
    goi_thue = forms.ModelChoiceField(
        label='Gói thuê', queryset=GoiThue.objects.none(), empty_label='-- Chọn gói thuê --',
    )
    gio_nhan = forms.DateTimeField(
        label='Giờ nhận máy', widget=o_chon_gio(), input_formats=[DINH_DANG_GIO],
    )
    gio_tra = forms.DateTimeField(
        label='Giờ trả dự kiến', widget=o_chon_gio(), input_formats=[DINH_DANG_GIO],
    )
    ma_giam_gia = forms.CharField(label='Mã giảm giá', required=False)
    ghi_chu = forms.CharField(
        label='Ghi chú cho cửa hàng (tùy chọn)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, thiet_bi=None, ma_da_dung='', **kwargs):
        super().__init__(*args, **kwargs)
        self.ma_da_dung = ma_da_dung

        # Chỉ hiện gói đang cung cấp và đã có giá cho máy này (gói tùy chỉnh luôn hiện)
        ds_goi = GoiThue.objects.filter(dang_cung_cap=True)
        if thiet_bi:
            ds_goi = ds_goi.filter(Q(cac_gia__thiet_bi=thiet_bi) | Q(tuy_chinh=True)).distinct()
        self.fields['goi_thue'].queryset = ds_goi
        self.fields['goi_thue'].help_text = (
            'Chọn Tùy chỉnh thời gian để tự chọn giờ nhận/trả, tối đa 30 ngày. '
            'Giá là tổ hợp các gói có chi phí thấp nhất.'
        )

    def clean_ma_giam_gia(self):
        ma = self.cleaned_data['ma_giam_gia'].strip().upper()
        if ma:
            voucher = MaGiamGia.objects.filter(ma=ma).first()
            if voucher is None or (ma != self.ma_da_dung and not voucher.co_hieu_luc()):
                raise forms.ValidationError('Mã giảm giá không hợp lệ hoặc đã hết lượt.')
        return ma

    def clean(self):
        du_lieu = super().clean()
        goi = du_lieu.get('goi_thue')
        gio_nhan = du_lieu.get('gio_nhan')
        gio_tra = du_lieu.get('gio_tra')

        if gio_nhan and gio_nhan <= timezone.now():
            self.add_error('gio_nhan', 'Giờ nhận máy phải ở tương lai.')

        if gio_nhan and gio_tra:
            # BR01: giờ trả phải sau giờ nhận
            if gio_tra <= gio_nhan:
                self.add_error('gio_tra', 'Giờ trả dự kiến phải sau giờ nhận máy.')
            # BR03: thời gian thuê không dài hơn số giờ của gói
            elif goi and (gio_tra - gio_nhan).total_seconds() > goi.so_gio_toi_da * 3600:
                self.add_error(
                    'gio_tra',
                    f'Thời gian thuê dài hơn gói {goi.ten}. Vui lòng chọn gói dài hơn hoặc gói Tùy chỉnh.',
                )
        return du_lieu


# ===========================================================================
# 2. NHÂN VIÊN XỬ LÝ ĐƠN
# ===========================================================================

class XuLyYeuCauForm(forms.Form):
    """UC-1.4: lý do khi yêu cầu khách điều chỉnh hoặc khi hủy đơn."""

    ly_do = forms.CharField(
        label='Lý do / gợi ý cho khách',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )


# ===========================================================================
# 3. TIỀN CỌC: THU KHI NHẬN MÁY, HOÀN KHI TRẢ MÁY
# ===========================================================================

class ThuCocForm(forms.Form):
    """Thu tiền thuê và phần cọc máy còn lại khi khách đến nhận máy."""

    phuong_thuc = forms.ChoiceField(
        label='Thu tiền tại quầy bằng',
        choices=DonThue.PHUONG_THUC_TAI_QUAY,
    )
    da_xac_nhan = forms.BooleanField(
        label='Đã đối chiếu CCCD, thu đủ tiền thuê và cọc máy còn lại, khách đã nhận máy',
    )


class HoanCocForm(forms.Form):
    """Hoàn cọc khi khách trả máy. Phụ thu trả trễ do hệ thống tự tính."""

    hinh_thuc_tra = forms.ChoiceField(
        label='Hình thức trả',
        choices=DonThue.HINH_THUC_TRA,
        widget=forms.RadioSelect,
    )
    tra_thuc_te = forms.DateTimeField(
        label='Thời gian khách trả máy',
        widget=o_chon_gio(),
        input_formats=[DINH_DANG_GIO],
    )
    may_hu_hong = forms.ModelMultipleChoiceField(
        label='Máy bị hư hỏng (bỏ trống nếu máy bình thường)',
        queryset=May.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    mo_ta_hu_hong = forms.CharField(
        label='Mô tả tình trạng hư hỏng',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
    )
    khau_tru_den_bu = forms.IntegerField(
        label='Khấu trừ đền bù theo quy định (đồng)', min_value=0, initial=0,
    )
    phuong_thuc = forms.ChoiceField(
        label='Hoàn cọc / thu thêm bằng',
        choices=DonThue.PHUONG_THUC_TAI_QUAY,
    )
    da_xu_ly_tien = forms.BooleanField(
        label='Đã nhận lại máy và đã hoàn cọc / thu thêm đúng số tiền ở trên',
    )

    def __init__(self, *args, don=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Chỉ cho chọn các máy thuộc đơn này
        if don is not None:
            self.fields['may_hu_hong'].queryset = (
                May.objects
                .filter(cac_phan_bo__chi_tiet__don=don)
                .select_related('thiet_bi')
                .distinct()
            )
        self.fields['may_hu_hong'].label_from_instance = lambda may: f'{may.thiet_bi.ten}, {may.so_seri}'

    def clean(self):
        du_lieu = super().clean()
        co_may_hong = bool(du_lieu.get('may_hu_hong'))

        if co_may_hong and not (du_lieu.get('mo_ta_hu_hong') or '').strip():
            self.add_error('mo_ta_hu_hong', 'Vui lòng mô tả tình trạng hư hỏng.')
        if du_lieu.get('khau_tru_den_bu') and not co_may_hong:
            self.add_error('may_hu_hong', 'Chọn máy hư hỏng trước khi khấu trừ đền bù.')
        return du_lieu


# ===========================================================================
# 4. SỰ CỐ MÁY
# ===========================================================================

SO_ANH_TOI_DA = 5
KICH_THUOC_ANH_TOI_DA = 5 * 1024 * 1024  # 5MB mỗi ảnh


class NhieuAnhInput(forms.ClearableFileInput):
    """Ô chọn file cho phép chọn nhiều ảnh một lúc."""

    allow_multiple_selected = True


class NhieuAnhField(forms.ImageField):
    """
    Trường nhận nhiều ảnh (theo hướng dẫn "upload nhiều file" của Django).

    Mỗi ảnh phải là JPG / PNG / WebP thật (Pillow đọc nội dung file), tối đa 5MB.
    Trả về danh sách ảnh.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', NhieuAnhInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # Không chọn ảnh nào
        if not data:
            if self.required:
                raise forms.ValidationError('Cần tải lên ít nhất một ảnh máy hỏng.')
            return []

        ds_anh = data if isinstance(data, (list, tuple)) else [data]
        if len(ds_anh) > SO_ANH_TOI_DA:
            raise forms.ValidationError(f'Chỉ tải tối đa {SO_ANH_TOI_DA} ảnh mỗi lần.')

        # Kiểm tra từng ảnh bằng ImageField gốc của Django
        ket_qua = []
        for anh in ds_anh:
            anh = super().clean(anh, initial)
            if anh.size > KICH_THUOC_ANH_TOI_DA:
                raise forms.ValidationError('Mỗi ảnh tối đa 5MB.')
            if anh.image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise forms.ValidationError('Vui lòng chọn ảnh JPG, PNG hoặc WebP.')
            ket_qua.append(anh)
        return ket_qua


class GhiNhanSuCoForm(forms.Form):
    """Nhân viên ghi nhận sự cố cho một máy của đơn thuê."""

    may = forms.ModelChoiceField(
        label='Máy gặp sự cố', queryset=May.objects.none(), empty_label='-- Chọn máy --',
    )
    muc_do = forms.ChoiceField(
        label='Mức độ',
        choices=SuCo.MUC_DO,
        widget=forms.RadioSelect,
        initial=SuCo.NHE,
        help_text='Lỗi nhẹ: máy vẫn dùng được. Lỗi nặng: phải sửa, máy chuyển sang Bảo trì.',
    )
    mo_ta = forms.CharField(
        label='Mô tả sự cố',
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Ví dụ: màn hình bị trầy một vết dài 2cm ở góc phải, máy vẫn chụp được',
        }),
    )
    anh = NhieuAnhField(label=f'Ảnh máy hỏng (tối đa {SO_ANH_TOI_DA} ảnh, mỗi ảnh tối đa 5MB)')

    def __init__(self, *args, don=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Chỉ cho chọn các máy đang được giữ cho đơn này
        if don is not None:
            self.fields['may'].queryset = (
                May.objects
                .filter(cac_phan_bo__chi_tiet__don=don)
                .select_related('thiet_bi')
                .distinct()
            )
        self.fields['may'].label_from_instance = lambda may: f'{may.thiet_bi.ten}, {may.so_seri}'

    def clean_mo_ta(self):
        mo_ta = self.cleaned_data['mo_ta'].strip()
        if len(mo_ta) < 10:
            raise forms.ValidationError('Vui lòng mô tả sự cố rõ hơn (ít nhất 10 ký tự).')
        return mo_ta


class XuLySuCoForm(forms.ModelForm):
    """Cập nhật trạng thái và kết quả xử lý sự cố."""

    class Meta:
        model = SuCo
        fields = ['trang_thai', 'ket_qua_xu_ly']
        widgets = {'ket_qua_xu_ly': forms.Textarea(attrs={'rows': 3})}

    def clean(self):
        du_lieu = super().clean()
        if du_lieu.get('trang_thai') == SuCo.DA_XU_LY and not du_lieu.get('ket_qua_xu_ly', '').strip():
            self.add_error('ket_qua_xu_ly', 'Cần ghi kết quả trước khi đánh dấu đã xử lý.')
        return du_lieu
