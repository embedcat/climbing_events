# Generated by Django 4.0.8 on 2022-11-21 12:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0006_remove_event_flash_points_event_flash_points_pc'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='is_premium',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='event',
            name='is_premium_used',
            field=models.BooleanField(default=False),
        ),
    ]