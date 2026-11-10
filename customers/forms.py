from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

from .models import Address, CustomerProfile

User = get_user_model()


class RegisterForm(forms.Form):
    first_name = forms.CharField(label="Họ và tên", max_length=150)
    email = forms.EmailField(label="Email", max_length=150)
    phone = forms.CharField(label="Số điện thoại", max_length=20)
    password1 = forms.CharField(
        label="Mật khẩu",
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Nhập lại mật khẩu",
        strip=False,
        widget=forms.PasswordInput,
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email này đã được sử dụng.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if not phone:
            raise ValidationError("Vui lòng nhập số điện thoại.")
        return phone

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Hai mật khẩu chưa khớp.")
        if password1:
            user = User(
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
            )
            try:
                password_validation.validate_password(password1, user)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=self.cleaned_data["first_name"].strip(),
            password=self.cleaned_data["password1"],
        )
        CustomerProfile.objects.create(
            user=user,
            phone=self.cleaned_data["phone"],
        )
        return user


class AccountForm(forms.Form):
    first_name = forms.CharField(label="Họ và tên", max_length=150)
    phone = forms.CharField(label="Số điện thoại", max_length=20)


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = (
            "label",
            "recipient",
            "phone",
            "street",
            "district",
            "city",
            "is_default",
        )
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Ví dụ: Nhà riêng"}),
            "street": forms.TextInput(attrs={"placeholder": "Số nhà, tên đường"}),
        }
