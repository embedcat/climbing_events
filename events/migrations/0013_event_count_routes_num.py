# Generated by Django 4.0.8 on 2022-12-15 12:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0012_rename_is_premium_used_event_is_expired'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='count_routes_num',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
    ]