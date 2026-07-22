import datetime
from django.core.management.base import BaseCommand
from django.db.models import Q
from events.models import Event
from events import services


class Command(BaseCommand):
    help = 'Проверяет и отмечает просроченные соревнования'

    def handle(self, *args, **options):
        today = datetime.date.today()
        events = Event.objects.filter(is_expired=False).filter(
            Q(date_end__isnull=False, date_end__lt=today) |
            Q(date_end__isnull=True, date__lt=today)
        )
        services.mark_events_as_expired(events=events)
