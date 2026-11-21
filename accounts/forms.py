"""
Các form của app accounts.

    DangKyForm   : đăng ký tài khoản khách hàng (UC-6.1)
    DangNhapForm : đăng nhập (UC-6.2)
    TaiKhoanForm : cập nhật thông tin cá nhân (UC-6.3)
"""
import re

from django import forms

from config.form_co_ban import FormCoBan, ModelFormCoBan

from .models import User


def chuan_hoa_so_dien_thoai(so):
    """Bỏ dấu cách, dấu chấm, gạch ngang. Số hợp lệ có 9-15 chữ số (có thể có dấu + ở đầu)."""
    so = re.sub(r'[\s.()-]', '', so)
    if not re.fullmatch(r'\+?[0-9]{9,15}', so):
        raise forms.ValidationError('Số điện thoại cần có từ 9 đến 15 chữ số.')
    return so


class DangKyForm(FormCoBan):
    """UC-6.1: đăng ký tài khoản khách hàng. Email dùng làm tên đăng nhập."""

    ho_ten = forms.CharField(label='Họ tên', max_length=100)
    email = forms.EmailField(label='Email')
    so_dien_thoai = forms.CharField(label='Số điện thoại', max_length=15)
    mat_khau = forms.CharField(label='Mật khẩu', widget=forms.PasswordInput, min_length=6)
    nhap_lai = forms.CharField(label='Nhập lại mật khẩu', widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        da_dung = (
            User.objects.filter(email__iexact=email).exists()
            or User.objects.filter(username__iexact=email).exists()
        )
        if da_dung:
            raise forms.ValidationError('Email đã được sử dụng.')
        return email

    def clean_so_dien_thoai(self):
        so = chuan_hoa_so_dien_thoai(self.cleaned_data['so_dien_thoai'])
        if User.objects.filter(so_dien_thoai=so).exists():
            raise forms.ValidationError('Số điện thoại đã được sử dụng.')
        return so

    def clean(self):
        du_lieu = super().clean()
        mat_khau = du_lieu.get('mat_khau')
        nhap_lai = du_lieu.get('nhap_lai')
        if mat_khau and nhap_lai and mat_khau != nhap_lai:
            self.add_error('nhap_lai', 'Mật khẩu nhập lại không khớp.')
        return du_lieu


class DangNhapForm(FormCoBan):
    """UC-6.2: đăng nhập bằng email và mật khẩu."""

    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'autocomplete': 'username'}),
    )
    mat_khau = forms.CharField(
        label='Mật khẩu',
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )


class TaiKhoanForm(ModelFormCoBan):
    """UC-6.3: cập nhật họ tên, số điện thoại, CCCD, ảnh đại diện."""

    class Meta:
        model = User
        fields = ['ho_ten', 'so_dien_thoai', 'cccd', 'anh_dai_dien']

    def clean_so_dien_thoai(self):
        so = self.cleaned_data['so_dien_thoai']
        if not so:
            return so
        so = chuan_hoa_so_dien_thoai(so)
        if User.objects.filter(so_dien_thoai=so).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Số điện thoại đã được sử dụng.')
        return so

    def clean_cccd(self):
        cccd = self.cleaned_data['cccd'].strip()
        if cccd and not re.fullmatch(r'[0-9]{12}', cccd):
            raise forms.ValidationError('CCCD phải có đúng 12 chữ số.')
        return cccd

    def clean_anh_dai_dien(self):
        anh = self.cleaned_data.get('anh_dai_dien')
        if anh and getattr(anh, 'size', 0) > 2 * 1024 * 1024:
            raise forms.ValidationError('Ảnh đại diện tối đa 2MB.')
        return anh
