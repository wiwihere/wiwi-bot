# Generated by Django 4.2.8 on 2024-03-08 19:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0065_encounter_folder_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='encounter',
            name='use_total_clear_time',
            field=models.BooleanField(blank=True, null=True, verbose_name='use for total cleartime'),
        ),
    ]
