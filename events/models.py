from colorfield.fields import ColorField
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import models
from multiselectfield import MultiSelectField

from config import settings

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
    (GRADE_5, GRADE_5),
    (GRADE_6A, GRADE_6A),
    (GRADE_6Ap, GRADE_6Ap),
    (GRADE_6B, GRADE_6B),
    (GRADE_6Bp, GRADE_6Bp),
    (GRADE_6C, GRADE_6C),
    (GRADE_6Cp, GRADE_6Cp),
    (GRADE_7A, GRADE_7A),
    (GRADE_7Ap, GRADE_7Ap),
    (GRADE_7B, GRADE_7B),
    (GRADE_7Bp, GRADE_7Bp),
    (GRADE_7C, GRADE_7C),
    (GRADE_7Cp, GRADE_7Cp),
    (GRADE_8A, GRADE_8A),
    (GRADE_8Ap, GRADE_8Ap),
    (GRADE_8B, GRADE_8B),
    (GRADE_8Bp, GRADE_8Bp),
    (GRADE_8C, GRADE_8C),
    (GRADE_8Cp, GRADE_8Cp),
]

ACCENT_NO = '0'
ACCENT_FLASH = '1'
ACCENT_REDPOINT = '2'
ACCENT_TYPE = [
    (ACCENT_NO, 'NO'),
    (ACCENT_FLASH, 'FLASH'),
    (ACCENT_REDPOINT, 'REDPOINT'),
]


def _get_blank_json():
    return {}


def _get_default_route_score_json():
    return {'all': 1}


def _get_default_score_table_json():
    return {g[0]: f'{str(10 + 5 * i)}' for i, g in enumerate(GRADES)}


class CustomUser(AbstractUser):
    pass


class Wallet(models.Model):
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='wallet', default=1)
    title = models.CharField(max_length=50)
    wallet_id = models.CharField(max_length=50)
    notify_secret_key = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.title} ({ '*' * 6 + str(self.wallet_id)[-4:]})"


class Event(models.Model):
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='owner', default=1)
    title = models.CharField(max_length=128)
    gym = models.CharField(max_length=128)
    date = models.DateField(null=True)
    poster = models.ImageField(upload_to=settings.MEDIA_POSTERS_DIR,
                               default=f'..{settings.STATIC_URL}events/img/default_poster.png')
    description = models.TextField(null=True)
    short_description = models.TextField(null=True, max_length=200)
    routes_num = models.IntegerField(null=True, default=10)
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
    SCORE_GRADE = 'TBL'
    SCORE_NUM_ACCENTS = 'NUM'
    SCORE_TYPE = [
        (SCORE_SIMPLE_SUM, 'Сумма баллов'),
        (SCORE_PROPORTIONAL, 'От количества пролазов'),
        (SCORE_GRADE, 'По таблице категорий'),
        (SCORE_NUM_ACCENTS, 'По количеству Всего/Flash'),
    ]
    score_type = models.CharField(max_length=4, choices=SCORE_TYPE, default=SCORE_SIMPLE_SUM)
    redpoint_points = models.IntegerField(default=80)
    flash_points_pc = models.IntegerField(default=25)
    group_num = models.IntegerField(default=1)
    group_list = models.CharField(max_length=200, default='Общая группа')
    set_num = models.IntegerField(default=1)
    set_list = models.CharField(max_length=200, default='Общий сет')
    set_max_participants = models.IntegerField(default=0)
    FIELD_BIRTH_YEAR = 'birth_year'
    FIELD_CITY = 'city'
    FIELD_TEAM = 'team'
    FIELD_GENDER = 'gender'
    FIELD_GRADE = 'grade'
    FIELD_EMAIL = 'email'
    OPTIONAL_FIELDS = [
        FIELD_BIRTH_YEAR,
        FIELD_CITY,
        FIELD_TEAM,
        FIELD_GENDER,
        FIELD_GRADE,
        FIELD_EMAIL,
    ]
    REQUIRED_FIELDS = [
        (FIELD_BIRTH_YEAR, 'Год рождения'),
        (FIELD_CITY, 'Город'),
        (FIELD_TEAM, 'Команда'),
        (FIELD_EMAIL, 'Email'),
    ]
    REGISTRATION_FIELDS = [
        (FIELD_GENDER, 'Пол'),
        (FIELD_BIRTH_YEAR, 'Год рождения'),
        (FIELD_CITY, 'Город'),
        (FIELD_TEAM, 'Команда'),
        (FIELD_GRADE, 'Разряд'),
        (FIELD_EMAIL, 'Email')
    ]
    registration_fields = MultiSelectField(choices=REGISTRATION_FIELDS,
                                           default=f'{FIELD_GENDER},{FIELD_BIRTH_YEAR},{FIELD_CITY},{FIELD_TEAM}',
                                           null=True, blank=True)
    required_fields = MultiSelectField(choices=REQUIRED_FIELDS, default=None, null=True, blank=True)
    is_without_registration = models.BooleanField(default=False)
    is_view_pin_after_registration = models.BooleanField(default=True)
    is_check_result_before_enter = models.BooleanField(default=False)
    is_update_result_allowed = models.BooleanField(default=True)
    participant_min_age = models.IntegerField(default=0)
    is_pay_allowed = models.BooleanField(default=False)
    price = models.IntegerField(default=0, null=True, blank=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='event', blank=True, null=True)
    score_table = models.JSONField(default=_get_default_score_table_json)


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
    place = models.IntegerField(default=0)
    email = models.EmailField(max_length=100, blank=True, null=True)
    paid = models.BooleanField(default=False)

    def __str__(self):
        return f'<Part-t: Name={self.last_name}, PIN={self.pin}, Score={self.score}, set={self.set_index}>'


class Route(models.Model):
    points_male = models.FloatField(default=1)
    points_female = models.FloatField(default=1)
    number = models.IntegerField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='route')

    grade = models.CharField(max_length=3, choices=GRADES, default=GRADE_5)
    color = ColorField(default='#FF0000')

    score_json = models.JSONField(default=_get_default_route_score_json)

    def __str__(self):
        return f'N={self.number}, score={self.score_json}'


class PromoCode(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='PromoCode')
    title = models.CharField(max_length=32)
    price = models.IntegerField(default=0)
    applied_num = models.IntegerField(default=0, blank=True, null=True)
    max_applied_num = models.IntegerField(default=0, blank=True, null=True)
