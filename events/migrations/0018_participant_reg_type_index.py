# Generated by Django 4.0.8 on 2023-03-25 20:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0017_event_reg_type_list_event_reg_type_num'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='reg_type_index',
            field=models.IntegerField(default=0),
        ),
    ]
