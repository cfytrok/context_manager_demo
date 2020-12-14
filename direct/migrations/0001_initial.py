# Generated by Django 3.0.3 on 2020-10-02 19:12

import direct.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import joinfield.joinfield
import simple_history.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('login', models.CharField(max_length=50, primary_key=True, serialize=False)),
                ('auth_token', models.CharField(max_length=200)),
                ('last_campaigns_changes_time', models.DateTimeField(blank=True, null=True)),
                ('last_dictionaries_changes_time', models.DateTimeField(blank=True, null=True)),
                ('sync_time', models.DateTimeField(blank=True, null=True)),
                ('disable', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='AdGroup',
            fields=[
                ('id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('state', models.CharField(blank=True, choices=[('DELETE', 'DELETE')], max_length=255)),
                ('status', models.CharField(blank=True, choices=[('ACCEPTED', 'ACCEPTED'), ('DRAFT', 'DRAFT'), ('MODERATION', 'MODERATION'), ('PREACCEPTED', 'PREACCEPTED'), ('REJECTED', 'REJECTED'), ('DELETE', 'DELETE')], max_length=255)),
                ('serving_status', models.CharField(blank=True, choices=[('ELIGIBLE', 'ELIGIBLE'), ('RARELY_SERVED', 'RARELY_SERVED')], max_length=255)),
            ],
            bases=(models.Model, direct.models.APIParserMixing),
        ),
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('status', models.CharField(blank=True, choices=[('ACCEPTED', 'ACCEPTED'), ('DRAFT', 'DRAFT'), ('MODERATION', 'MODERATION'), ('REJECTED', 'REJECTED'), ('UNKNOWN', 'UNKNOWN')], max_length=255)),
                ('state', models.CharField(blank=True, choices=[('ARCHIVED', 'ARCHIVED'), ('CONVERTED', 'CONVERTED'), ('ENDED', 'ENDED'), ('OFF', 'OFF'), ('ON', 'ON'), ('SUSPENDED', 'SUSPENDED'), ('UNKNOWN', 'UNKNOWN'), ('DELETE', 'DELETE')], max_length=255)),
                ('type', models.CharField(blank=True, choices=[('TEXT_CAMPAIGN', 'TEXT_CAMPAIGN'), ('MOBILE_APP_CAMPAIGN', 'MOBILE_APP_CAMPAIGN'), ('DYNAMIC_TEXT_CAMPAIGN', 'DYNAMIC_TEXT_CAMPAIGN'), ('SMART_CAMPAIGN', 'SMART_CAMPAIGN'), ('UNKNOWN', 'UNKNOWN')], max_length=255)),
                ('start_date', models.DateField(auto_now_add=True)),
                ('daily_budget_amount', models.IntegerField(blank=True, null=True)),
                ('daily_budget_mode', models.CharField(blank=True, choices=[('STANDARD', 'STANDARD'), ('DISTRIBUTED', 'DISTRIBUTED')], max_length=255)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='direct.Account')),
            ],
            bases=(models.Model, direct.models.APIParserMixing),
        ),
        migrations.CreateModel(
            name='Criterion',
            fields=[
                ('id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('ad_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='direct.AdGroup')),
            ],
            bases=(models.Model, direct.models.APIParserMixing),
        ),
        migrations.CreateModel(
            name='GroupNegativeKeyword',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=255)),
                ('ad_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='direct.AdGroup')),
            ],
        ),
        migrations.CreateModel(
            name='DynamicFeedAdTarget',
            fields=[
                ('criterion_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='direct.Criterion')),
                ('min_price', models.IntegerField(blank=True, null=True)),
                ('rate', models.FloatField(blank=True, null=True)),
                ('name', models.CharField(max_length=4096)),
            ],
            bases=('direct.criterion',),
        ),
        migrations.CreateModel(
            name='Keyword',
            fields=[
                ('criterion_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='direct.Criterion')),
                ('text', models.CharField(max_length=4096)),
                ('bid', models.IntegerField(blank=True, null=True)),
                ('context_bid', models.IntegerField(blank=True, null=True)),
                ('strategy_priority', models.CharField(blank=True, choices=[('LOW', 'LOW'), ('NORMAL', 'NORMAL'), ('HIGH', 'HIGH')], max_length=6)),
                ('user_param1', models.CharField(blank=True, max_length=255)),
                ('user_param2', models.CharField(blank=True, max_length=255)),
                ('state', models.CharField(blank=True, choices=[('OFF', 'OFF'), ('ON', 'ON'), ('SUSPENDED', 'SUSPENDED'), ('DELETE', 'DELETE')], max_length=255)),
                ('status', models.CharField(blank=True, choices=[('ACCEPTED', 'ACCEPTED'), ('DRAFT', 'DRAFT'), ('REJECTED', 'REJECTED'), ('UNKNOWN', 'UNKNOWN')], max_length=255)),
                ('serving_status', models.CharField(blank=True, choices=[('ELIGIBLE', 'ELIGIBLE'), ('RARELY_SERVED', 'RARELY_SERVED')], max_length=255)),
            ],
            bases=('direct.criterion',),
        ),
        migrations.CreateModel(
            name='TextCampaign',
            fields=[
                ('campaign_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='direct.Campaign')),
            ],
            bases=('direct.campaign',),
        ),
        migrations.CreateModel(
            name='TextAd',
            fields=[
                ('id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('state', models.CharField(blank=True, choices=[('OFF', 'OFF'), ('ON', 'ON'), ('SUSPENDED', 'SUSPENDED'), ('OFF_BY_MONITORING', 'OFF_BY_MONITORING'), ('ARCHIVED', 'ARCHIVED'), ('UNKNOWN', 'UNKNOWN'), ('DELETE', 'DELETE')], default='OFF', max_length=255)),
                ('status', models.CharField(choices=[('ACCEPTED', 'ACCEPTED'), ('DRAFT', 'DRAFT'), ('MODERATION', 'MODERATION'), ('PREACCEPTED', 'PREACCEPTED'), ('REJECTED', 'REJECTED'), ('UNKNOWN', 'UNKNOWN')], default='DRAFT', max_length=255)),
                ('status_clarification', models.TextField(blank=True)),
                ('title', models.CharField(max_length=40)),
                ('title2', models.CharField(blank=True, max_length=40)),
                ('text', models.CharField(max_length=128)),
                ('href', models.URLField(max_length=1024)),
                ('mobile', models.CharField(choices=[('YES', 'YES'), ('NO', 'NO')], default='NO', max_length=3)),
                ('display_domain', models.URLField(blank=True)),
                ('display_url_path', models.CharField(blank=True, max_length=20)),
                ('v_card_id', models.BigIntegerField(blank=True, null=True)),
                ('ad_image_hash', models.CharField(blank=True, max_length=40)),
                ('ad_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='direct.AdGroup')),
            ],
            bases=(models.Model, direct.models.APIParserMixing),
        ),
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('geo_region_name', models.CharField(max_length=255)),
                ('geo_region_type', models.CharField(choices=[('World', 'World'), ('Continent', 'Continent'), ('Region', 'Region'), ('Country', 'Country'), ('Administrative area', 'Administrative area'), ('District', 'District'), ('City', 'City'), ('City district', 'City district'), ('Village', 'Village')], max_length=20)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='direct.Region')),
            ],
            bases=(models.Model, direct.models.APIParserMixing),
        ),
        migrations.CreateModel(
            name='HistoricalTextAd',
            fields=[
                ('id', models.BigIntegerField(db_index=True)),
                ('state', models.CharField(blank=True, choices=[('OFF', 'OFF'), ('ON', 'ON'), ('SUSPENDED', 'SUSPENDED'), ('OFF_BY_MONITORING', 'OFF_BY_MONITORING'), ('ARCHIVED', 'ARCHIVED'), ('UNKNOWN', 'UNKNOWN'), ('DELETE', 'DELETE')], default='OFF', max_length=255)),
                ('status', models.CharField(choices=[('ACCEPTED', 'ACCEPTED'), ('DRAFT', 'DRAFT'), ('MODERATION', 'MODERATION'), ('PREACCEPTED', 'PREACCEPTED'), ('REJECTED', 'REJECTED'), ('UNKNOWN', 'UNKNOWN')], default='DRAFT', max_length=255)),
                ('status_clarification', models.TextField(blank=True)),
                ('title', models.CharField(max_length=40)),
                ('title2', models.CharField(blank=True, max_length=40)),
                ('text', models.CharField(max_length=128)),
                ('href', models.URLField(max_length=1024)),
                ('mobile', models.CharField(choices=[('YES', 'YES'), ('NO', 'NO')], default='NO', max_length=3)),
                ('display_domain', models.URLField(blank=True)),
                ('display_url_path', models.CharField(blank=True, max_length=20)),
                ('v_card_id', models.BigIntegerField(blank=True, null=True)),
                ('ad_image_hash', models.CharField(blank=True, max_length=40)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('ad_group', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='direct.AdGroup')),
                ('history_relation', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='history', to='direct.TextAd')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical text ad',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalGroupNegativeKeyword',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('text', models.CharField(max_length=255)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('ad_group', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='direct.AdGroup')),
                ('history_relation', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='history', to='direct.GroupNegativeKeyword')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical group negative keyword',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalAdGroup',
            fields=[
                ('id', models.BigIntegerField(db_index=True)),
                ('name', models.CharField(max_length=255)),
                ('state', models.CharField(blank=True, choices=[('DELETE', 'DELETE')], max_length=255)),
                ('status', models.CharField(blank=True, choices=[('ACCEPTED', 'ACCEPTED'), ('DRAFT', 'DRAFT'), ('MODERATION', 'MODERATION'), ('PREACCEPTED', 'PREACCEPTED'), ('REJECTED', 'REJECTED'), ('DELETE', 'DELETE')], max_length=255)),
                ('serving_status', models.CharField(blank=True, choices=[('ELIGIBLE', 'ELIGIBLE'), ('RARELY_SERVED', 'RARELY_SERVED')], max_length=255)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('campaign', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='direct.Campaign')),
                ('history_relation', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='history', to='direct.AdGroup')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical ad group',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='DirectStats',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('date', models.DateField()),
                ('clicks', models.IntegerField()),
                ('region_id', models.IntegerField()),
                ('device', models.CharField(choices=[('desktop', 'desktop'), ('mobile', 'mobile'), ('tablet', 'tablet')], max_length=20)),
                ('keyword', models.CharField(blank=True, max_length=255)),
                ('gender', models.CharField(choices=[('GENDER_MALE', 'GENDER_MALE'), ('GENDER_FEMALE', 'GENDER_FEMALE'), ('UNKNOWN', 'UNKNOWN')], max_length=20)),
                ('age', models.CharField(choices=[('AGE_0_17', 'AGE_0_17'), ('AGE_18_24', 'AGE_18_24'), ('AGE_25_34', 'AGE_25_34'), ('AGE_35_44', 'AGE_35_44'), ('AGE_45', 'AGE_45'), ('AGE_45_54', 'AGE_45_54'), ('AGE_55', 'AGE_55'), ('UNKNOWN', 'UNKNOWN')], max_length=20)),
                ('carrier_type', models.CharField(choices=[('CELLULAR', 'CELLULAR'), ('STATIONARY', 'STATIONARY'), ('UNKNOWN', 'UNKNOWN')], max_length=20)),
                ('mobile_platform', models.CharField(choices=[('ANDROID', 'ANDROID'), ('IOS', 'IOS'), ('OTHER', 'OTHER'), ('UNKNOWN', 'UNKNOWN')], max_length=20)),
                ('slot', models.CharField(choices=[('PREMIUMBLOCK', 'PREMIUMBLOCK'), ('OTHER', 'OTHER')], max_length=20)),
                ('ad', joinfield.joinfield.JoinField(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to='direct.TextAd')),
                ('campaign', joinfield.joinfield.JoinField(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to='direct.Campaign')),
                ('criterion', joinfield.joinfield.JoinField(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to='direct.Criterion')),
                ('group', joinfield.joinfield.JoinField(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to='direct.AdGroup')),
            ],
            bases=(models.Model, direct.models.APIParserMixing),
        ),
        migrations.AddField(
            model_name='adgroup',
            name='campaign',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='direct.Campaign'),
        ),
        migrations.AddField(
            model_name='adgroup',
            name='regions',
            field=models.ManyToManyField(to='direct.Region'),
        ),
        migrations.CreateModel(
            name='HistoricalTextCampaign',
            fields=[
                ('campaign_ptr', models.ForeignKey(auto_created=True, blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, parent_link=True, related_name='+', to='direct.Campaign')),
                ('id', models.BigIntegerField(db_index=True)),
                ('name', models.CharField(max_length=255)),
                ('status', models.CharField(blank=True, choices=[('ACCEPTED', 'ACCEPTED'), ('DRAFT', 'DRAFT'), ('MODERATION', 'MODERATION'), ('REJECTED', 'REJECTED'), ('UNKNOWN', 'UNKNOWN')], max_length=255)),
                ('state', models.CharField(blank=True, choices=[('ARCHIVED', 'ARCHIVED'), ('CONVERTED', 'CONVERTED'), ('ENDED', 'ENDED'), ('OFF', 'OFF'), ('ON', 'ON'), ('SUSPENDED', 'SUSPENDED'), ('UNKNOWN', 'UNKNOWN'), ('DELETE', 'DELETE')], max_length=255)),
                ('type', models.CharField(blank=True, choices=[('TEXT_CAMPAIGN', 'TEXT_CAMPAIGN'), ('MOBILE_APP_CAMPAIGN', 'MOBILE_APP_CAMPAIGN'), ('DYNAMIC_TEXT_CAMPAIGN', 'DYNAMIC_TEXT_CAMPAIGN'), ('SMART_CAMPAIGN', 'SMART_CAMPAIGN'), ('UNKNOWN', 'UNKNOWN')], max_length=255)),
                ('start_date', models.DateField(blank=True, editable=False)),
                ('daily_budget_amount', models.IntegerField(blank=True, null=True)),
                ('daily_budget_mode', models.CharField(blank=True, choices=[('STANDARD', 'STANDARD'), ('DISTRIBUTED', 'DISTRIBUTED')], max_length=255)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('account', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='direct.Account')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('history_relation', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='history', to='direct.TextCampaign')),
            ],
            options={
                'verbose_name': 'historical text campaign',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalKeyword',
            fields=[
                ('criterion_ptr', models.ForeignKey(auto_created=True, blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, parent_link=True, related_name='+', to='direct.Criterion')),
                ('id', models.BigIntegerField(db_index=True)),
                ('text', models.CharField(max_length=4096)),
                ('bid', models.IntegerField(blank=True, null=True)),
                ('context_bid', models.IntegerField(blank=True, null=True)),
                ('strategy_priority', models.CharField(blank=True, choices=[('LOW', 'LOW'), ('NORMAL', 'NORMAL'), ('HIGH', 'HIGH')], max_length=6)),
                ('user_param1', models.CharField(blank=True, max_length=255)),
                ('user_param2', models.CharField(blank=True, max_length=255)),
                ('state', models.CharField(blank=True, choices=[('OFF', 'OFF'), ('ON', 'ON'), ('SUSPENDED', 'SUSPENDED'), ('DELETE', 'DELETE')], max_length=255)),
                ('status', models.CharField(blank=True, choices=[('ACCEPTED', 'ACCEPTED'), ('DRAFT', 'DRAFT'), ('REJECTED', 'REJECTED'), ('UNKNOWN', 'UNKNOWN')], max_length=255)),
                ('serving_status', models.CharField(blank=True, choices=[('ELIGIBLE', 'ELIGIBLE'), ('RARELY_SERVED', 'RARELY_SERVED')], max_length=255)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('ad_group', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='direct.AdGroup')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('history_relation', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='history', to='direct.Keyword')),
            ],
            options={
                'verbose_name': 'historical keyword',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.AddConstraint(
            model_name='groupnegativekeyword',
            constraint=models.UniqueConstraint(fields=('ad_group', 'text'), name='unique_group_negative_keyword'),
        ),
    ]