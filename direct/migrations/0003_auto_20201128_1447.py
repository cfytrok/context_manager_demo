# Generated by Django 3.0.3 on 2020-11-28 14:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('direct', '0002_directadtemplate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='directadtemplate',
            name='href',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='directadtemplate',
            name='text',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='directadtemplate',
            name='title',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='directadtemplate',
            name='title2',
            field=models.TextField(blank=True),
        ),
    ]
