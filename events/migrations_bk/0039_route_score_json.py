# Generated by Django 3.1.3 on 2021-09-06 10:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0038_route_accents_num'),
    ]

    operations = [
        migrations.AddField(
            model_name='route',
            name='score_json',
            field=models.JSONField(default={}),
        ),
    ]