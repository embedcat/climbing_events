# Generated by Django 4.0.4 on 2022-10-16 20:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0057_event_yoomoney_wallet_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='yoomoney_wallet_id',
            field=models.CharField(blank=True, default='', max_length=50, null=True),
        ),
    ]