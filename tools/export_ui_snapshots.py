"""Xuất HTML để kiểm tra giao diện; mọi dữ liệu tạm được rollback."""
import os
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.db import transaction
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from catalog.models import GiaThue, GoiThue, ThietBi
from rentals import services


out = BASE / '_work' / 'ui'
out.mkdir(parents=True, exist_ok=True)


def save(client, name, route, *args, params=None):
    response = client.get(reverse(route, args=args), params or {})
    if response.status_code != 200:
        raise RuntimeError(f'{route}: HTTP {response.status_code}')
    (out / f'{name}.html').write_bytes(response.content)


with override_settings(ALLOWED_HOSTS=['testserver', '127.0.0.1', 'localhost']), transaction.atomic():
    client = Client()
    customer = User.objects.get(username='khach@demo.vn')
    staff = User.objects.get(username='nv@demo.vn')
    client.force_login(customer)
    tbs = list(ThietBi.objects.filter(ngung_cung_cap=False)[:2])
    goi = GoiThue.objects.filter(dang_cung_cap=True).first()
    start = timezone.now() + timedelta(days=365)
    tam = {'ma_gui': str(uuid4()), 'goi_thue_id': goi.pk, 'gio_nhan': start.isoformat(),
        'gio_tra': (start + timedelta(hours=2)).isoformat(),
        'cac_muc': [{'thiet_bi_id': tb.pk, 'so_luong': 1} for tb in tbs]}
    don = services.luu_yeu_cau(customer, tam)
    services.xac_nhan_lich(don.pk)
    save(client, 'don-thue', 'chi_tiet_don', don.pk)
    save(client, 'dat-coc', 'dat_coc', don.pk)
    client.force_login(staff)
    save(client, 'thu-coc', 'ql_thu_coc', don.pk)
    save(client, 'lich-may', 'ql_lich')
    save(client, 'phan-hoi', 'ql_phan_hoi')
    client.force_login(customer)
    save(client, 'may-trong', 'ds_may_anh', params={
        'gio_nhan': timezone.localtime(start).strftime('%Y-%m-%dT%H:%M'),
        'gio_tra': timezone.localtime(start + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'), 'so_luong': 1})
    save(client, 'feedback-cua-toi', 'phan_hoi_cua_toi')
    from rentals.models import DonThue
    DonThue.objects.filter(pk=don.pk).update(trang_thai=DonThue.HOAN_TAT)
    save(client, 'viet-feedback', 'gui_danh_gia', don.pk)
    custom = GoiThue.objects.filter(tuy_chinh=True, dang_cung_cap=True).first()
    if custom:
        session = client.session
        session['don_tam'] = dict(tam, ma_gui=str(uuid4()), goi_thue_id=custom.pk,
            gio_tra=(start + timedelta(hours=80)).isoformat())
        session.save()
        save(client, 'goi-tuy-chinh', 'xac_nhan_dat_thue')
    transaction.set_rollback(True)
print(f'Exported snapshots to {out}; temporary records rolled back.')
