# Generated by Django 4.2.8 on 2024-03-10 09:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0073_remove_instance_discord_leaderboard_message_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dpslog',
            name='group_clear',
        ),
    ]
