

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='camera',
            name='available_units',
            field=models.PositiveSmallIntegerField(default=1, help_text='Cập nhật theo số máy vật lý thực tế.', verbose_name='Số máy có thể cho thuê'),
        ),
    ]
