# Переносит результаты из устаревшего Participant.accents в Participant.french_accents.
# french_accents добавлено в 0017 без переноса данных, поэтому результаты соревнований,
# введённые до марта 2023 года, остались только в старом поле.

from django.db import migrations


def convert_legacy_accents(accents: dict) -> dict:
    """{'0': '2'} -> {'0': {'top': 2, 'zone': 2}}. Нераспознанные значения пропускаются."""
    converted = {}
    for route_index, attempt in (accents or {}).items():
        try:
            top = int(attempt)
        except (TypeError, ValueError):
            continue
        # zone повторяет top — так же, как это делает form_data_to_results
        converted[str(route_index)] = {'top': top, 'zone': top}
    return converted


def backfill_french_accents(apps, schema_editor):
    Participant = apps.get_model('events', 'Participant')
    for participant in Participant.objects.iterator():
        if participant.french_accents:
            continue
        converted = convert_legacy_accents(participant.accents)
        if converted:
            participant.french_accents = converted
            participant.save(update_fields=['french_accents'])


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0032_event_registration_close_datetime_alter_route_color'),
    ]

    operations = [
        # обратная миграция — no-op: старое поле не трогаем, откатывать нечего
        migrations.RunPython(backfill_french_accents, migrations.RunPython.noop),
    ]
