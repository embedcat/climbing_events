# Generated by Django 4.0.4 on 2022-10-25 09:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0005_promocode'),
    ]

    operations = [
        migrations.AddField(
            model_name='promocode',
            name='applied_num',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AddField(
            model_name='promocode',
            name='max_applied_num',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
    ]