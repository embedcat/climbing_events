# Generated by Django 3.1.3 on 2021-10-13 10:36

from django.db import migrations, models
import events.models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0040_delete_accent'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='route',
            name='accents_num',
        ),
        migrations.AlterField(
            model_name='route',
            name='score_json',
            field=models.JSONField(default=events.models._get_blank_json),
        ),
    ]