# Generated by Django 4.2.8 on 2024-09-08 12:06

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0079_alter_instance_options_remove_instance_type_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='instance',
            options={'ordering': ['instance_group', 'nr']},
        ),
        migrations.RenameField(
            model_name='instance',
            old_name='group_type',
            new_name='instance_group',
        ),
    ]
