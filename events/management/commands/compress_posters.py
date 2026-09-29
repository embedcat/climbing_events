from django.core.management.base import BaseCommand
from events import img_tools, services


class Command(BaseCommand):
    help = 'Ужимает уже загруженные постеры до WebP; исходные файлы удаляются'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать, какие постеры будут пережаты')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        total_before = total_after = 0
        for event in services.get_uploaded_poster_events():
            try:
                if img_tools.is_poster_compressed(event.poster):
                    continue
                old_name = event.poster.name
                old_size = event.poster.size
                if dry_run:
                    self.stdout.write(f'[{event.id}] {old_name} ({old_size // 1024} KB)')
                    total_before += old_size
                    continue
                services.compress_event_poster(event)
                new_size = event.poster.size
            except Exception as e:
                self.stderr.write(f'[{event.id}] {event.poster.name}: {e!r}')
                continue
            total_before += old_size
            total_after += new_size
            self.stdout.write(f'[{event.id}] {old_name} ({old_size // 1024} KB) -> '
                              f'{event.poster.name} ({new_size // 1024} KB)')
        if dry_run:
            self.stdout.write(f'Будет пережато: {total_before // 1024} KB')
        else:
            self.stdout.write(f'Итого: {total_before // 1024} KB -> {total_after // 1024} KB')
