# Generated by Django 4.0.8 on 2023-03-22 13:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0017_participant_french_accents_alter_event_score_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='french_score',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
