# Generated by Django 4.2.8 on 2023-12-16 17:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0043_encounter_emoji_cm'),
    ]

    operations = [
        migrations.AddField(
            model_name='emoji',
            name='discord_id_cm',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='emoji',
            name='url_cm',
            field=models.URLField(blank=True, null=True),
        ),
    ]
