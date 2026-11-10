from django import forms

from .models import Feedback


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ("rating", "content", "photo")
        widgets = {
            "rating": forms.Select(
                choices=[(value, f"{value} / 5") for value in range(5, 0, -1)]
            ),
            "content": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Chia sẻ trải nghiệm thuê máy của bạn.",
                }
            ),
        }

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if len(content) < 10:
            raise forms.ValidationError("Nội dung cần có ít nhất 10 ký tự.")
        return content
