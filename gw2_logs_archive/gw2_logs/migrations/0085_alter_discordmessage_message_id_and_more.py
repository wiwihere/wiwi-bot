# Generated by Django 4.2.8 on 2025-02-01 20:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0084_dpslog_friend_player_count_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='discordmessage',
            name='message_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='emoji',
            name='discord_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='emoji',
            name='discord_id_cm',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='emoji',
            name='discord_id_lcm',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='instancecleargroup',
            name='discord_message_id_old',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
