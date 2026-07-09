import datetime
from django.core.management.base import BaseCommand
from events.models import Event
from events import services


class Command(BaseCommand):
    help = 'Проверяет и отмечает просроченные соревнования'

    def handle(self, *args, **options):
        events = Event.objects.filter(is_expired=False, date__lt=datetime.date.today())
        services.mark_events_as_expired(events=events)
