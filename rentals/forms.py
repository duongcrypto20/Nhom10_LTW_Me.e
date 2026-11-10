from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from catalog.models import RentalRate
from .models import RentalOrder


class RentalRequestForm(forms.Form):
    rate = forms.ModelChoiceField(label="Thời lượng thuê", queryset=RentalRate.objects.none())
    start_at = forms.DateTimeField(
        label="Thời gian nhận máy",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "autocomplete": "off"},
            format="%Y-%m-%dT%H:%M",
        ),
    )
    quantity = forms.IntegerField(
        label="Số lượng máy",
        min_value=1,
        max_value=10,
        initial=1,
        widget=forms.NumberInput(attrs={"min": 1, "max": 10}),
    )
    delivery_method = forms.ChoiceField(
        label="Hình thức nhận máy",
        choices=RentalOrder.DeliveryMethod.choices,
        initial=RentalOrder.DeliveryMethod.PICKUP,
        widget=forms.RadioSelect,
    )
    delivery_address = forms.CharField(
        label="Địa chỉ giao nhận",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    customer_note = forms.CharField(
        label="Ghi chú",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    accept_policy = forms.BooleanField(
        label="Tôi đã đọc giá thuê và quy định đặt thuê.",
    )

    def __init__(self, *args, camera, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera = camera
        self.fields["rate"].queryset = camera.rates.filter(is_active=True)
        self.fields["rate"].label_from_instance = lambda rate: (
            f"{rate.label} · {rate.amount:,}đ"
        )

    def clean_start_at(self):
        start_at = self.cleaned_data["start_at"]
        if timezone.is_naive(start_at):
            start_at = timezone.make_aware(start_at)
        if start_at <= timezone.now():
            raise ValidationError("Thời gian nhận máy phải ở tương lai.")
        return start_at

    def clean(self):
        cleaned = super().clean()
        rate = cleaned.get("rate")
        start_at = cleaned.get("start_at")
        if rate and rate.duration_hours == 6 and start_at:
            if (start_at.hour, start_at.minute) not in {(8, 0), (15, 0)}:
                self.add_error(
                    "start_at",
                    "Gói 6 giờ nhận máy lúc 08:00 hoặc 15:00 theo quy định cửa hàng.",
                )
        if cleaned.get("delivery_method") == RentalOrder.DeliveryMethod.DELIVERY:
            if not cleaned.get("delivery_address", "").strip():
                self.add_error("delivery_address", "Vui lòng nhập địa chỉ giao nhận.")
        return cleaned

    def get_end_at(self):
        return self.cleaned_data["start_at"] + timedelta(
            hours=self.cleaned_data["rate"].duration_hours
        )
