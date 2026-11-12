
from django import forms

from .models import Feedback


# BIỂU MẪU KHÁCH GỬI PHẢN HỒI
class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ("rating", "content", "photo")
        widgets = {
            "rating": forms.Select(
                choices=[("", "Chọn điểm đánh giá")]
                + [
                    (value, f"{value}/5 sao")
                    for value in range(5, 0, -1)
                ]
            ),
            "content": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Chia sẻ trải nghiệm thuê máy...",
                }
            ),
            "photo": forms.ClearableFileInput(
                attrs={
                    "accept": ".jpg,.jpeg,.png,.webp",
                }
            ),
        }

    def clean_content(self):
        content = self.cleaned_data["content"].strip()

        if not 10 <= len(content) <= 2000:
            raise forms.ValidationError(
                "Nội dung cần từ 10 đến 2000 ký tự."
            )

        return content

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")

        if photo and photo.size > 2 * 1024 * 1024:
            raise forms.ValidationError(
                "Ảnh không được vượt quá 2 MB."
            )

        return photo


# BIỂU MẪU NHÂN VIÊN DUYỆT VÀ TRẢ LỜI
class FeedbackModerationForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ("is_published", "shop_reply")
        widgets = {
            "shop_reply": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Nhập trả lời của cửa hàng...",
                }
            ),
        }

    def clean_shop_reply(self):
        return self.cleaned_data["shop_reply"].strip()
