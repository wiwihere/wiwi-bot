# Generated by Django 5.1.6 on 2025-02-08 19:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0090_encounter_use_for_icg_duration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='encounter',
            name='has_cm',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='encounter',
            name='has_lcm',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='encounter',
            name='lb',
            field=models.BooleanField(default=False, verbose_name='leaderboard'),
        ),
        migrations.AlterField(
            model_name='encounter',
            name='lb_cm',
            field=models.BooleanField(default=False, verbose_name='leaderboard cm'),
        ),
        migrations.AlterField(
            model_name='encounter',
            name='lb_lcm',
            field=models.BooleanField(default=False, verbose_name='leaderboard lcm'),
        ),
    ]
