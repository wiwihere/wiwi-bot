# Generated by Django 4.2.8 on 2024-03-17 23:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0074_remove_dpslog_group_clear'),
    ]

    operations = [
        migrations.AddField(
            model_name='dpslog',
            name='phasetime_str',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
