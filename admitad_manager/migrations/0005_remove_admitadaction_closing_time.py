# Generated by Django 3.0.3 on 2020-11-19 15:45

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('admitad_manager', '0004_remove_admitadaction_click_time'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='admitadaction',
            name='closing_time',
        ),
    ]
