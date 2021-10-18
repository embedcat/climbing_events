from colorfield.fields import ColorField
from django.db import models
from multiselectfield import MultiSelectField

from config import settings


def _get_blank_json():
    return {}


class Event(models.Model):
    title = models.CharField(max_length=128)
    gym = models.CharField(max_length=128)
    date = models.DateField(null=True)
    poster = models.ImageField(upload_to=settings.MEDIA_POSTERS_DIR, blank=True, null=True)
    description = models.TextField(null=True)
    routes_num = models.IntegerField(null=True)
    is_published = models.BooleanField(default=False)
    is_registration_open = models.BooleanField(default=False)
    is_results_allowed = models.BooleanField(default=False)
    is_enter_result_allowed = models.BooleanField(default=False)
    is_count_only_entered_results = models.BooleanField(default=False)
    is_view_full_results = models.BooleanField(default=False)
    is_view_route_color = models.BooleanField(default=False)
    is_view_route_grade = models.BooleanField(default=False)
    is_view_route_score = models.BooleanField(default=False)
    is_separate_score_by_groups = models.BooleanField(default=False)

    SCORE_SIMPLE_SUM = 'SUM'
    SCORE_PROPORTIONAL = 'PROP'
    SCORE_TYPE = [
        (SCORE_SIMPLE_SUM, 'Сумма баллов'),
        (SCORE_PROPORTIONAL, 'От кол-ва пролазов'),
    ]
    score_type = models.CharField(max_length=4, choices=SCORE_TYPE, default=SCORE_SIMPLE_SUM)
    flash_points = models.IntegerField(default=100)
    redpoint_points = models.IntegerField(default=80)
    group_num = models.IntegerField(default=1)
    group_list = models.CharField(max_length=200, default='')
    set_num = models.IntegerField(default=1)
    set_list = models.CharField(max_length=200, default='')
    set_max_participants = models.IntegerField(default=0)
    FIELD_BIRTH_YEAR = 'birth_year'
    FIELD_CITY = 'city'
    FIELD_TEAM = 'team'
    FIELD_GENDER = 'gender'
    FIELD_GRADE = 'grade'
    REQUIRED_FIELDS = [
        (FIELD_BIRTH_YEAR, 'Год рождения'),
        (FIELD_CITY, 'Город'),
        (FIELD_TEAM, 'Команда'),
    ]
    REGISTRATION_FIELDS = [
        (FIELD_GENDER, 'Пол'),
        (FIELD_BIRTH_YEAR, 'Год рождения'),
        (FIELD_CITY, 'Город'),
        (FIELD_TEAM, 'Команда'),
        (FIELD_GRADE, 'Разряд'),
    ]
    registration_fields = MultiSelectField(choices=REGISTRATION_FIELDS,
                                           default=f'{FIELD_GENDER},{FIELD_BIRTH_YEAR},{FIELD_CITY},{FIELD_TEAM}',
                                           null=True, blank=True)
    required_fields = MultiSelectField(choices=REQUIRED_FIELDS, default=None, null=True, blank=True)
    is_without_registration = models.BooleanField(default=False)


class Participant(models.Model):
    first_name = models.CharField(max_length=32)
    last_name = models.CharField(max_length=32)
    GENDER_MALE = 'MALE'
    GENDER_FEMALE = 'FEMALE'
    GENDERS = [
        (GENDER_MALE, 'М'),
        (GENDER_FEMALE, 'Ж'),
    ]
    gender = models.CharField(max_length=6, choices=GENDERS, default=GENDER_MALE)
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
    group_index = models.IntegerField(default=0)
    set_index = models.IntegerField(default=0)

    accents = models.JSONField(default=_get_blank_json)

    def __str__(self):
        return f'<Part-t: Name={self.last_name}, PIN={self.pin}, Score={self.score}, set={self.set_index}>'


class Route(models.Model):
    points_male = models.FloatField(default=1)
    points_female = models.FloatField(default=1)
    number = models.IntegerField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='route')

    GRADE_5 = '5'
    GRADE_6A = '6A'
    GRADE_6Ap = '6A+'
    GRADE_6B = '6B'
    GRADE_6Bp = '6B+'
    GRADE_6C = '6C'
    GRADE_6Cp = '6C+'
    GRADE_7A = '7A'
    GRADE_7Ap = '7A+'
    GRADE_7B = '7B'
    GRADE_7Bp = '7B+'
    GRADE_7C = '7C'
    GRADE_7Cp = '7C+'
    GRADE_8A = '8A'
    GRADE_8Ap = '8A+'
    GRADE_8B = '8B'
    GRADE_8Bp = '8B+'
    GRADE_8C = '8C'
    GRADE_8Cp = '8C+'

    GRADES = [
        (GRADE_5, '5'),
        (GRADE_6A, '6A'),
        (GRADE_6Ap, '6A+'),
        (GRADE_6B, '6B'),
        (GRADE_6Bp, '6B+'),
        (GRADE_6C, '6C'),
        (GRADE_6Cp, '6C+'),
        (GRADE_7A, '7A'),
        (GRADE_7Ap, '7A+'),
        (GRADE_7B, '7B'),
        (GRADE_7Bp, '7B+'),
        (GRADE_7C, '7C'),
        (GRADE_7Cp, '7C+'),
        (GRADE_8A, '8A'),
        (GRADE_8Ap, '8A+'),
        (GRADE_8B, '8B'),
        (GRADE_8Bp, '8B+'),
        (GRADE_8C, '8C'),
        (GRADE_8Cp, '8C+'),
    ]

    grade = models.CharField(max_length=3, choices=GRADES, default=GRADE_5)
    color = ColorField(default='#FF0000')

    score_json = models.JSONField(default=_get_blank_json)

    def __str__(self):
        return f'N={self.number}, score={self.score_json}'


ACCENT_NO = 'NO'
ACCENT_FLASH = 'FL'
ACCENT_REDPOINT = 'RP'
ACCENT_TYPE = [
    (ACCENT_NO, 'NO'),
    (ACCENT_FLASH, 'FLASH'),
    (ACCENT_REDPOINT, 'REDPOINT'),
]
