# Generated by Django 4.2.8 on 2024-02-25 17:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gw2_logs', '0063_emoji_png_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='DiscordMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_id', models.IntegerField(blank=True, null=True)),
            ],
        ),
        migrations.RenameField(
            model_name='instancecleargroup',
            old_name='discord_message_id',
            new_name='discord_message_id_old',
        ),
        migrations.AlterField(
            model_name='encounter',
            name='lb',
            field=models.BooleanField(blank=True, null=True, verbose_name='leaderboard'),
        ),
        migrations.AlterField(
            model_name='encounter',
            name='lb_cm',
            field=models.BooleanField(blank=True, null=True, verbose_name='leaderboard cm'),
        ),
        migrations.AlterField(
            model_name='instancecleargroup',
            name='type',
            field=models.CharField(choices=[('raid', 'Raid'), ('fractal', 'Fractal'), ('strike', 'Strike'), ('golem', 'Golem')], default='raid', max_length=10),
        ),
        migrations.AddField(
            model_name='instancecleargroup',
            name='discord_message',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='instance_clear_group', to='gw2_logs.discordmessage'),
        ),
    ]
