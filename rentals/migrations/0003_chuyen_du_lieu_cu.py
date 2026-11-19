from django.db import migrations


def chuyen_du_lieu(apps, schema_editor):
    ThietBi = apps.get_model('catalog', 'ThietBi')
    Loai = apps.get_model('catalog', 'LoaiThietBi')
    nhan = {'mirrorless': 'Mirrorless', 'mirrorless_co_dien': 'Mirrorless cổ điển', 'compact': 'Compact'}
    for ma, ten in nhan.items():
        Loai.objects.get_or_create(ma=ma, defaults={'ten': ten})
    for tb in ThietBi.objects.all():
        loai, _ = Loai.objects.get_or_create(ma=tb.loai, defaults={'ten': nhan.get(tb.loai, tb.loai)})
        tb.danh_muc_id = loai.pk
        tb.save(update_fields=['danh_muc'])
    Don = apps.get_model('rentals', 'DonThue')
    ChiTiet = apps.get_model('rentals', 'ChiTietDonThue')
    PhanBo = apps.get_model('rentals', 'PhanBoMay')
    for don in Don.objects.all():
        dong, _ = ChiTiet.objects.get_or_create(don_id=don.pk, thiet_bi_id=don.thiet_bi_id,
            defaults={'so_luong': 1, 'don_gia': don.tien_thue, 'tien_coc_don_vi': don.tien_coc})
        if don.may_id:
            PhanBo.objects.get_or_create(chi_tiet_id=dong.pk, may_id=don.may_id)
    User = apps.get_model('accounts', 'User')
    DiaChi = apps.get_model('accounts', 'DiaChiKhachHang')
    for user in User.objects.exclude(dia_chi=''):
        DiaChi.objects.get_or_create(tai_khoan_id=user.pk, dia_chi_chi_tiet=user.dia_chi,
            defaults={'ho_ten_nhan': user.ho_ten, 'so_dien_thoai_nhan': user.so_dien_thoai, 'mac_dinh': True})


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_user_anh_dai_dien_diachikhachhang'),
        ('catalog', '0002_loaithietbi_magiamgia_dang_ap_dung_and_more'),
        ('rentals', '0002_baotri_hoan_tat_donthue_don_vi_van_chuyen_and_more'),
    ]
    operations = [migrations.RunPython(chuyen_du_lieu, migrations.RunPython.noop)]
