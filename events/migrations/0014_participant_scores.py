# Generated by Django 4.0.8 on 2022-12-15 12:14

from django.db import migrations, models
import events.models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0013_event_count_routes_num'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='scores',
            field=models.JSONField(default=events.models._get_blank_json),
        ),
    ]