# Generated by Django 4.0.8 on 2022-12-13 07:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0010_event_max_participants'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='description',
            field=models.TextField(default='Регламент', null=True),
        ),
        migrations.AlterField(
            model_name='event',
            name='gym',
            field=models.CharField(default='Скалодром', max_length=128),
        ),
        migrations.AlterField(
            model_name='event',
            name='is_count_only_entered_results',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='event',
            name='is_separate_score_by_groups',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='event',
            name='is_view_full_results',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='event',
            name='is_view_route_score',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='event',
            name='short_description',
            field=models.TextField(default='Краткое описание', max_length=200, null=True),
        ),
    ]
