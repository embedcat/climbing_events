from django.db import migrations, models


def replace_accents(old: str) -> str:
    if old == "NO":
        return "-"
    if old == "FL":
        return "F"
    if old == "RP":
        return "RP"


def change_accents(apps, schema_editor):
    Participant = apps.get_model('events', 'Participant')
    for participant in Participant.objects.all():
        accents = participant.accents
        accents = {k: replace_accents(v) for k, v in accents.items()}
        participant.accents = accents
        participant.save()


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0052_participant_place'),
    ]

    operations = [
        migrations.RunPython(change_accents),
    ]
