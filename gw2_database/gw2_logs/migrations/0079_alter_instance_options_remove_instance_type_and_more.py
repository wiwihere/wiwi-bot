# Generated by Django 4.2.8 on 2024-09-08 12:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0078_encounter_ei_encounter_id'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='instance',
            options={'ordering': ['group_type', 'nr']},
        ),
        migrations.RemoveField(
            model_name='instance',
            name='type',
        ),
        migrations.AddField(
            model_name='instance',
            name='group_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='instance', to='gw2_logs.instancegroup'),
        ),
    ]
