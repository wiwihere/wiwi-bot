# Generated by Django 4.2.8 on 2023-12-15 23:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0041_alter_dpslog_core_player_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='emoji',
            name='animated',
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
    ]
