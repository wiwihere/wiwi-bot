# Generated by Django 5.1.6 on 2025-02-08 19:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0089_remove_instancecleargroup_discord_message_id_old_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='encounter',
            name='use_for_icg_duration',
            field=models.BooleanField(default=False),
        ),
    ]
