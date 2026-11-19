from django.db import migrations


def tao_goi(apps, schema_editor):
    Goi = apps.get_model('catalog', 'GoiThue')
    Goi.objects.get_or_create(ten='Tùy chỉnh thời gian', defaults={'so_gio_toi_da': 720,
        'mo_ta': 'Tự chọn giờ nhận/trả, tối đa 30 ngày. Giá là tổ hợp các gói hiện có có chi phí thấp nhất.',
        'tuy_chinh': True, 'dang_cung_cap': True})


class Migration(migrations.Migration):
    dependencies = [('catalog', '0004_goithue_tuy_chinh')]
    operations = [migrations.RunPython(tao_goi, migrations.RunPython.noop)]
