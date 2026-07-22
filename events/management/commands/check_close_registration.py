from django.core.management.base import BaseCommand
from django.utils import timezone
from events.models import Event


class Command(BaseCommand):
    help = 'Проверяет дату и время закрытия регистрации и отключает регистрацию при наступлении указанного времени'

    def handle(self, *args, **options):
        now = timezone.now()
        events = Event.objects.filter(
            is_registration_open=True,
            registration_close_datetime__isnull=False,
            registration_close_datetime__lte=now
        )
        count = events.update(is_registration_open=False)
        self.stdout.write(self.style.SUCCESS(f'Закрыта регистрация для {count} соревнований.'))
