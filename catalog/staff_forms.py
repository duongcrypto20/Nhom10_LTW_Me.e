
from django import forms

from .models import Camera, RentalRate


# BIỂU MẪU MÁY ẢNH
class CameraManageForm(forms.ModelForm):
    class Meta:
        model = Camera
        fields = (
            "name",
            "slug",
            "brand",
            "image",
            "description",
            "deposit_amount",
            "available_units",
            "is_active",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "image": forms.TextInput(
                attrs={
                    "placeholder": "images/products/ten-anh.jpg",
                }
            ),
        }

    def clean_image(self):
        path = self.cleaned_data["image"].strip().replace("\\", "/")

        if (
            not path.startswith("images/products/")
            or ".." in path
            or not path.lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp")
            )
        ):
            raise forms.ValidationError(
                "Ảnh phải nằm trong static/images/products/ "
                "và có định dạng JPG, PNG hoặc WebP."
            )

        return path


# BIỂU MẪU GÓI THUÊ
class RentalRateManageForm(forms.ModelForm):
    class Meta:
        model = RentalRate
        fields = (
            "camera",
            "label",
            "duration_hours",
            "amount",
            "sort_order",
            "is_active",
        )

    def clean_duration_hours(self):
        value = self.cleaned_data["duration_hours"]
        if value < 1:
            raise forms.ValidationError(
                "Thời lượng phải lớn hơn 0."
            )
        return value

    def clean_amount(self):
        value = self.cleaned_data["amount"]
        if value < 0:
            raise forms.ValidationError(
                "Giá thuê không được âm."
            )
        return value
