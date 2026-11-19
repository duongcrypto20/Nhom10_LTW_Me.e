from django import forms
import re

from .models import User


def so_dien_thoai_hop_le(value):
    value = re.sub(r'[\s.()-]', '', value)
    if not re.fullmatch(r'\+?[0-9]{9,15}', value):
        raise forms.ValidationError('Số điện thoại cần có từ 9 đến 15 chữ số.')
    return value


class DangKyForm(forms.Form):
    """Form đăng ký tài khoản khách hàng (UC-6.1)."""
    ho_ten = forms.CharField(label='Họ tên', max_length=100)
    email = forms.EmailField(label='Email')
    so_dien_thoai = forms.CharField(label='Số điện thoại', max_length=15)
    mat_khau = forms.CharField(label='Mật khẩu', widget=forms.PasswordInput, min_length=6)
    nhap_lai = forms.CharField(label='Nhập lại mật khẩu', widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError('Email đã được sử dụng.')
        return email

    def clean_so_dien_thoai(self):
        value = so_dien_thoai_hop_le(self.cleaned_data['so_dien_thoai'])
        if User.objects.filter(so_dien_thoai=value).exists():
            raise forms.ValidationError('Số điện thoại đã được sử dụng.')
        return value
    def clean(self):
        du_lieu = super().clean()
        if du_lieu.get('mat_khau') and du_lieu.get('nhap_lai'):
            if du_lieu['mat_khau'] != du_lieu['nhap_lai']:
                self.add_error('nhap_lai', 'Mật khẩu nhập lại không khớp.')
        return du_lieu


class DangNhapForm(forms.Form):
    """Form đăng nhập (UC-6.2)."""
    email = forms.EmailField(label='Email')
    mat_khau = forms.CharField(label='Mật khẩu', widget=forms.PasswordInput)


class TaiKhoanForm(forms.ModelForm):
    """Form cập nhật thông tin cá nhân (UC-6.3)."""
    class Meta:
        model = User
        fields = ['ho_ten', 'so_dien_thoai', 'cccd', 'anh_dai_dien']

    def clean_so_dien_thoai(self):
        value = self.cleaned_data['so_dien_thoai']
        if value:
            value = so_dien_thoai_hop_le(value)
            if User.objects.filter(so_dien_thoai=value).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError('Số điện thoại đã được sử dụng.')
        return value

    def clean_cccd(self):
        value = self.cleaned_data['cccd'].strip()
        if value and not re.fullmatch(r'[0-9]{12}', value):
            raise forms.ValidationError('CCCD phải có đúng 12 chữ số.')
        return value

    def clean_anh_dai_dien(self):
        value = self.cleaned_data.get('anh_dai_dien')
        if value and getattr(value, 'size', 0) > 2 * 1024 * 1024:
            raise forms.ValidationError('Ảnh đại diện tối đa 2MB.')
        return value
