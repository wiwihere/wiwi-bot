# Generated by Django 4.2.8 on 2023-12-11 21:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0004_emoji'),
    ]

    operations = [
        migrations.CreateModel(
            name='RaidClears',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('start_time', models.DateTimeField()),
                ('discord_message_id', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='DpsLogs',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.CharField(max_length=100)),
                ('duration', models.TimeField()),
                ('start_time', models.DateTimeField()),
                ('clear_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='headers', to='gw2_logs.raidclears')),
            ],
        ),
    ]
