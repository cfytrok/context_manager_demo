# Generated by Django 3.0.3 on 2020-10-06 16:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('admitad_manager', '0003_auto_20201005_1132'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='admitadaction',
            name='click_time',
        ),
    ]
