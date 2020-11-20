from django.db import models

from config import settings


class Event(models.Model):
    title = models.CharField(max_length=128)
    date = models.DateField(null=True)
    poster = models.ImageField(upload_to=settings.MEDIA_POSTERS_DIR, blank=True, null=True)
    description = models.TextField(null=True)
    routes_num = models.IntegerField(null=True)
    is_published = models.BooleanField(default=False)
    is_registration_open = models.BooleanField(default=False)
    is_results_allowed = models.BooleanField(default=False)
    is_enter_result_allowed = models.BooleanField(default=False)

    SCORE_SIMPLE_SUM = 'SUM'
    SCORE_PROPORTIONAL = 'PROP'
    SCORE_TYPE = [
        (SCORE_SIMPLE_SUM, 'Сумма баллов'),
        (SCORE_PROPORTIONAL, 'От кол-ва пролазов'),
    ]
    score_type = models.CharField(max_length=4, choices=SCORE_TYPE, default=SCORE_SIMPLE_SUM)
    flash_points = models.IntegerField(default=100)
    redpoint_points = models.IntegerField(default=80)


class Participant(models.Model):
    first_name = models.CharField(max_length=32)
    last_name = models.CharField(max_length=32)
    birth_year = models.IntegerField(null=True)
    city = models.CharField(null=True, max_length=32)
    team = models.CharField(null=True, max_length=32)

    GRADE_BR = 'BR'
    GRADE_3YOUTH = '3Y'
    GRADE_2YOUTH = '2Y'
    GRADE_1YOUTH = '1Y'
    GRADE_3 = '3C'
    GRADE_2 = '2C'
    GRADE_1 = '1C'
    GRADE_KMS = 'KMS'
    GRADE_MS = 'MS'
    GRADE_MSMK = 'MSMK'
    GRADES = [
        (GRADE_BR, 'б/р'),
        (GRADE_3YOUTH, '3 ю.р.'),
        (GRADE_2YOUTH, '2 ю.р.'),
        (GRADE_1YOUTH, '1 ю.р.'),
        (GRADE_3, '3 сп.р.'),
        (GRADE_2, '2 сп.р.'),
        (GRADE_1, '1 сп.р.'),
        (GRADE_KMS, 'КМС'),
        (GRADE_MS, 'МС'),
        (GRADE_MSMK, 'МСМК'),
    ]
    grade = models.CharField(max_length=4, choices=GRADES, default=GRADE_BR)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='participant')
    pin = models.PositiveSmallIntegerField(null=True)
    score = models.FloatField(default=0)
    is_entered_result = models.BooleanField(default=False)

    def __str__(self):
        return f'<Part-t: Name={self.last_name}, PIN={self.pin}, Score={self.score}>'


class Route(models.Model):
    points = models.FloatField(default=1)
    number = models.IntegerField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='route')

    def __str__(self):
        return f'<Route: N={self.number}, Points={self.points}>'


class Accent(models.Model):
    ACCENT_NO = 'NO'
    ACCENT_FLASH = 'FL'
    ACCENT_REDPOINT = 'RP'
    ACCENT_TYPE = [
        (ACCENT_NO, '-'),
        (ACCENT_FLASH, 'FLASH'),
        (ACCENT_REDPOINT, 'REDPOINT'),
    ]
    accent = models.CharField(max_length=2, choices=ACCENT_TYPE, default=ACCENT_NO)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='accent')
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='accent')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='accent')

    def __str__(self):
        return f'<Accent: User={self.participant} Route={self.route}, Result={self.accent}>'
