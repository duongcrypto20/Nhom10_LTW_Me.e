from django import forms
from django.utils import timezone
from django.db.models import Q

from catalog.models import GoiThue, MaGiamGia, May

from .models import DonThue, SuCo

DINH_DANG_GIO = '%Y-%m-%dT%H:%M'


def o_chon_gio():
    """Ô chọn ngày giờ của trình duyệt (input type=datetime-local)."""
    return forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=DINH_DANG_GIO)


class DatThueForm(forms.Form):
    """UC-1.1: Chọn gói thuê và thời gian thuê cho một thiết bị."""
    field_order = ['so_luong', 'goi_thue', 'gio_nhan', 'gio_tra', 'ma_giam_gia', 'ghi_chu']

    goi_thue = forms.ModelChoiceField(label='Gói thuê', queryset=GoiThue.objects.none(),
                                      empty_label='-- Chọn gói thuê --')
    gio_nhan = forms.DateTimeField(label='Giờ nhận máy', widget=o_chon_gio(),
                                   input_formats=[DINH_DANG_GIO])
    gio_tra = forms.DateTimeField(label='Giờ trả dự kiến', widget=o_chon_gio(),
                                  input_formats=[DINH_DANG_GIO])
    ma_giam_gia = forms.CharField(label='Mã giảm giá', required=False)
    ghi_chu = forms.CharField(label='Ghi chú cho cửa hàng (tùy chọn)', required=False,
                              widget=forms.Textarea(attrs={'rows': 3}))
    so_luong = forms.IntegerField(label='Số lượng', min_value=1, max_value=20, initial=1, required=False)

    def __init__(self, *args, thiet_bi=None, voucher_da_dung='', **kwargs):
        super().__init__(*args, **kwargs)
        self.thiet_bi = thiet_bi
        self.voucher = None
        self.voucher_da_dung = voucher_da_dung
        # Chỉ hiện các gói đang cung cấp và đã có giá cho thiết bị này (UC-3.2)
        self.fields['goi_thue'].queryset = GoiThue.objects.filter(dang_cung_cap=True)
        if thiet_bi:
            self.fields['goi_thue'].queryset = self.fields['goi_thue'].queryset.filter(
                Q(cac_gia__thiet_bi=thiet_bi) | Q(tuy_chinh=True)).distinct()
        self.fields['goi_thue'].help_text = ('Chọn Tùy chỉnh thời gian để tự chọn giờ nhận/trả, tối đa 30 ngày. '
            'Giá là tổ hợp gói hiện có có chi phí thấp nhất, hiển thị ở bước kiểm tra trước khi gửi.')

    def clean_ma_giam_gia(self):
        ma = self.cleaned_data['ma_giam_gia'].strip().upper()
        if ma:
            self.voucher = MaGiamGia.objects.filter(ma=ma).first()
            if self.voucher is None or (ma != self.voucher_da_dung and not self.voucher.co_hieu_luc()):
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
            elif goi:
                # BR03: không vượt thời lượng tối đa của gói
                so_gio = (gio_tra - gio_nhan).total_seconds() / 3600
                if so_gio > goi.so_gio_toi_da:
                    self.add_error('gio_tra', f'Thời gian thuê vượt quá thời lượng của gói '
                                              f'(tối đa {goi.so_gio_toi_da} giờ).')
        return du_lieu


class XuLyYeuCauForm(forms.Form):
    """UC-1.4: Lý do khi yêu cầu khách điều chỉnh hoặc khi hủy đơn."""
    ly_do = forms.CharField(label='Lý do / gợi ý cho khách', required=False,
                            widget=forms.Textarea(attrs={'rows': 3}))


class NhieuAnhInput(forms.ClearableFileInput):
    """Ô chọn được nhiều ảnh một lúc (theo hướng dẫn tải nhiều file của Django)."""
    allow_multiple_selected = True


class NhieuAnhField(forms.ImageField):
    """Nhận 0 đến 5 ảnh JPG/PNG/WebP, mỗi ảnh tối đa 5MB. Trả về danh sách ảnh."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', NhieuAnhInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data:
            if self.required:
                raise forms.ValidationError('Cần tải lên ít nhất một ảnh tình trạng máy.')
            return []
        ds = data if isinstance(data, (list, tuple)) else [data]
        if len(ds) > 5:
            raise forms.ValidationError('Chỉ tải tối đa 5 ảnh mỗi lần.')
        ket_qua = []
        for anh in ds:
            anh = super().clean(anh, initial)
            if anh.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Mỗi ảnh tối đa 5MB.')
            if anh.image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise forms.ValidationError('Vui lòng chọn ảnh JPG, PNG hoặc WebP.')
            ket_qua.append(anh)
        return ket_qua


class NhanCocForm(forms.Form):
    """Quản lý tiền cọc: thu cọc tại quầy (hoặc xác nhận cọc online) khi khách nhận máy."""

    phuong_thuc = forms.ChoiceField(label='Thu tiền tại quầy bằng', choices=DonThue.HINH_THUC_THU_TAI_QUAY)
    da_xac_nhan = forms.BooleanField(label='Đã đối chiếu CCCD, thu đủ tiền thuê và phần cọc máy còn lại, khách đã nhận máy')


class HoanCocForm(forms.Form):
    """Quản lý tiền cọc: hoàn cọc khi khách trả máy. Phụ thu trả trễ hệ thống tự tính."""

    hinh_thuc_tra = forms.ChoiceField(label='Hình thức trả', choices=DonThue.HINH_THUC_TRA, widget=forms.RadioSelect)
    tra_thuc_te = forms.DateTimeField(label='Thời gian khách trả máy', widget=o_chon_gio(), input_formats=[DINH_DANG_GIO])
    may_hu_hong = forms.ModelMultipleChoiceField(label='Máy bị hư hỏng (bỏ trống nếu máy bình thường)',
        queryset=May.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)
    loai_su_co = forms.ChoiceField(label='Loại sự cố', choices=SuCo._meta.get_field('loai').choices, required=False)
    mo_ta_su_co = forms.CharField(label='Mô tả tình trạng hư hỏng', required=False, widget=forms.Textarea(attrs={'rows': 2}))
    anh_su_co = NhieuAnhField(label='Ảnh tình trạng máy hỏng (tối đa 5 ảnh)')
    khau_tru_den_bu = forms.IntegerField(label='Khấu trừ đền bù theo quy định (đồng)', min_value=0, initial=0)
    phuong_thuc_hoan = forms.ChoiceField(label='Hoàn cọc / thu thêm bằng', choices=DonThue.HINH_THUC_THU_TAI_QUAY)
    da_xu_ly_tien = forms.BooleanField(label='Đã nhận lại máy và đã hoàn cọc / thu thêm đúng số tiền ở trên')

    def __init__(self, *args, don=None, **kwargs):
        super().__init__(*args, **kwargs)
        if don is not None:
            self.fields['may_hu_hong'].queryset = May.objects.filter(cac_phan_bo__chi_tiet__don=don).select_related('thiet_bi').distinct()
        self.fields['may_hu_hong'].label_from_instance = lambda may: f'{may.thiet_bi.ten} · {may.so_seri}'

    def clean(self):
        data = super().clean()
        if data.get('may_hu_hong'):
            if not (data.get('mo_ta_su_co') or '').strip():
                self.add_error('mo_ta_su_co', 'Vui lòng mô tả tình trạng hư hỏng.')
            if not data.get('anh_su_co'):
                self.add_error('anh_su_co', 'Cần tải ảnh tình trạng máy hỏng làm bằng chứng.')
        elif data.get('anh_su_co'):
            self.add_error('may_hu_hong', 'Chọn máy bị hư hỏng tương ứng với ảnh đã tải.')
        return data


class BaoSuCoForm(forms.Form):
    """Ghi nhận sự cố của một máy trong đơn (khi đang thuê), kèm ảnh tình trạng máy."""

    may = forms.ModelChoiceField(label='Máy gặp sự cố', queryset=May.objects.none())
    loai = forms.ChoiceField(label='Loại sự cố', choices=SuCo._meta.get_field('loai').choices)
    mo_ta = forms.CharField(label='Mô tả tình trạng', widget=forms.Textarea(attrs={'rows': 3}))
    anh = NhieuAnhField(label='Ảnh tình trạng máy (tối đa 5 ảnh)', required=True)

    def __init__(self, *args, don=None, **kwargs):
        super().__init__(*args, **kwargs)
        if don is not None:
            self.fields['may'].queryset = May.objects.filter(cac_phan_bo__chi_tiet__don=don).select_related('thiet_bi').distinct()
        self.fields['may'].label_from_instance = lambda may: f'{may.thiet_bi.ten} · {may.so_seri}'


class ThemAnhSuCoForm(forms.Form):
    anh = NhieuAnhField(label='Tải thêm ảnh tình trạng máy', required=True)


class TraMayForm(forms.Form):
    hinh_thuc_tra = forms.ChoiceField(label='Hình thức trả máy', choices=DonThue.HINH_THUC_TRA)
    don_vi_van_chuyen = forms.CharField(label='Đơn vị vận chuyển', max_length=100, required=False)
    ma_van_don_tra = forms.CharField(label='Mã vận đơn', max_length=100, required=False)

    def clean(self):
        data = super().clean()
        if data.get('hinh_thuc_tra') == 'gui_ve':
            for name in ('don_vi_van_chuyen', 'ma_van_don_tra'):
                if not data.get(name):
                    self.add_error(name, 'Cần thông tin vận chuyển để cửa hàng theo dõi máy gửi về.')
        return data


class SuCoForm(forms.ModelForm):
    class Meta:
        model = SuCo
        fields = ['loai', 'trang_thai', 'cach_xu_ly']

    def clean(self):
        data = super().clean()
        if data.get('trang_thai') == 'da_xu_ly' and not data.get('cach_xu_ly'):
            self.add_error('cach_xu_ly', 'Cần ghi kết quả trước khi hoàn tất xử lý sự cố.')
        return data
