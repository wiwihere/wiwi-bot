# Generated by Django 4.2.8 on 2023-12-13 15:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0032_alter_instancecleargroup_start_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='dpslog',
            name='report_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
