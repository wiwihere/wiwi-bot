# Generated by Django 4.2.8 on 2024-09-08 12:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0080_alter_instance_options_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='encounter',
            old_name='use_in_instance_group',
            new_name='leaderboard_instance_group',
        ),
    ]
