# Generated by Django 4.2.8 on 2024-03-08 20:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0069_rename_instance_group_encounter_use_in_instance_group'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='encounter',
            name='use_total_clear_time',
        ),
    ]
