# Generated by Django 4.2.8 on 2023-12-12 10:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0015_encounter_cm_encounter_dpsreport_boss_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dpslog',
            name='start_time',
            field=models.DateTimeField(blank=True, null=True, unique=True),
        ),
    ]
