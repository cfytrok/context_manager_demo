# Generated by Django 3.0.3 on 2020-06-01 11:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Doc',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ya_doc_id', models.CharField(max_length=50)),
                ('position', models.IntegerField()),
                ('url', models.URLField()),
                ('domain', models.URLField()),
                ('title', models.TextField()),
                ('headline', models.TextField()),
                ('modtime', models.CharField(max_length=14)),
                ('size', models.BigIntegerField()),
                ('charset', models.CharField(max_length=10)),
                ('passages_type', models.BooleanField()),
                ('lang', models.CharField(blank=True, max_length=3)),
                ('mime_type', models.CharField(max_length=100)),
                ('saved_copy_url', models.URLField()),
            ],
        ),
        migrations.CreateModel(
            name='YaXmlRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.CharField(max_length=255)),
                ('region_id', models.IntegerField(blank=True, null=True)),
                ('date', models.DateField(auto_now=True)),
                ('found', models.BigIntegerField(blank=True, null=True)),
                ('last_page', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'unique_together': {('query', 'region_id')},
            },
        ),
        migrations.CreateModel(
            name='Passage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('position', models.IntegerField()),
                ('doc', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ya_xml_search.Doc')),
            ],
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('position', models.IntegerField()),
                ('request', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ya_xml_search.YaXmlRequest')),
            ],
        ),
        migrations.AddField(
            model_name='doc',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ya_xml_search.Group'),
        ),
    ]
