from bootstrap_datepicker_plus.widgets import DatePickerInput, DateTimePickerInput
from crispy_forms.bootstrap import InlineRadios
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field
from django import forms
from django.core.files.uploadedfile import UploadedFile
from config import settings

from events import img_tools
from events.models import Participant, Event, ACCENT_TYPE, Route, PromoCode, Wallet, validate_birth_date
from tinymce.widgets import TinyMCE
from phonenumber_field.formfields import PhoneNumberField


def _birth_date_widget():
    # type=date даёт нативный календарь на телефоне, браузер отправляет дату в ISO
    return forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


def _birth_date_field(required: bool) -> forms.DateField:
    return forms.DateField(label='Дата рождения',
                           required=required,
                           widget=_birth_date_widget(),
                           input_formats=['%Y-%m-%d', '%d.%m.%Y'],
                           validators=[validate_birth_date])


class ParticipantRegistrationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        group_list = kwargs.pop('group_list')
        set_list = kwargs.pop('set_list')
        registration_fields = kwargs.pop('registration_fields')
        required_fields = kwargs.pop('required_fields')
        is_enter_form = kwargs.pop('is_enter_form')
        reg_type_list = kwargs.pop('reg_type_list')
        birth_format = kwargs.pop('birth_format', Event.BIRTH_FORMAT_YEAR)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        if is_enter_form:
            self.helper.form_tag = False
            self.helper.disable_csrf = True
        else:
            self.helper.add_input(Submit('submit', 'Зарегистрироваться'))
        self.helper.label_class = 'mb-1'

        # отчество первым из дополнительных полей, чтобы стояло сразу после имени
        if Event.FIELD_MIDDLE_NAME in registration_fields:
            self.fields[Event.FIELD_MIDDLE_NAME] = forms.CharField(label='Отчество', max_length=32,
                                                                   required=Event.FIELD_MIDDLE_NAME in required_fields)
        if Event.FIELD_GENDER in registration_fields:
            self.fields[Event.FIELD_GENDER] = forms.ChoiceField(choices=Participant.GENDERS, label='Пол',
                                                                required=False)
        if Event.FIELD_BIRTH_YEAR in registration_fields:
            is_birth_required = Event.FIELD_BIRTH_YEAR in required_fields
            if birth_format == Event.BIRTH_FORMAT_DATE:
                self.fields[Event.FIELD_BIRTH_DATE] = _birth_date_field(required=is_birth_required)
            else:
                self.fields[Event.FIELD_BIRTH_YEAR] = forms.IntegerField(label='Год рождения',
                                                                         required=is_birth_required)
        if Event.FIELD_CITY in registration_fields:
            self.fields[Event.FIELD_CITY] = forms.CharField(label='Город',
                                                            required=Event.FIELD_CITY in required_fields)
        if Event.FIELD_TEAM in registration_fields:
            self.fields[Event.FIELD_TEAM] = forms.CharField(label='Команда',
                                                            required=Event.FIELD_TEAM in required_fields)
        if Event.FIELD_GRADE in registration_fields:
            self.fields[Event.FIELD_GRADE] = forms.ChoiceField(choices=Participant.GRADES, label='Разряд',
                                                               required=False)
        if Event.FIELD_EMAIL in registration_fields:
            self.fields[Event.FIELD_EMAIL] = forms.EmailField(label='Email',
                                                              required=Event.FIELD_EMAIL in required_fields)
        if Event.FIELD_PHONE in registration_fields:
            self.fields[Event.FIELD_PHONE] = PhoneNumberField(label='Телефон',
                                                              required=Event.FIELD_PHONE in required_fields,
                                                              region='RU')

        if group_list != ['']:
            self.fields['group_index'] = forms.ChoiceField(choices=tuple([(name, name) for name in group_list]),
                                                           label='Категория',
                                                           required=False)
        if set_list:
            self.fields['set_index'] = forms.ChoiceField(choices=tuple([(name, name) for name in set_list]),
                                                         label='Сет',
                                                         required=False)
        reg_types = reg_type_list.split(',') if reg_type_list != None else []
        if len(reg_types) > 1:
            self.fields['reg_type_index'] = forms.ChoiceField(choices=tuple([(i, t.strip()) for i, t in enumerate(reg_types)]),
                                                              label='Тип регистрации',
                                                              required=False)

    class Meta:
        model = Participant
        fields = [
            'last_name',
            'first_name',
        ]
        labels = {
            'last_name': 'Фамилия',
            'first_name': 'Имя',
            'gender': 'Пол',
            'birth_year': 'Год рождения',
            'city': 'Город',
            'team': 'Команда',
            'grade': 'Спортивный разряд',
        }


class PosterFormMixin:
    def clean_poster(self):
        poster = self.cleaned_data.get('poster')
        if not isinstance(poster, UploadedFile):
            return poster
        width, height = poster.image.size
        if width * height > img_tools.POSTER_MAX_PIXELS:
            raise forms.ValidationError(
                f'Слишком большое разрешение ({width}×{height}), '
                f'максимум — {img_tools.POSTER_MAX_PIXELS // 1_000_000} мегапикселей.')
        try:
            return img_tools.compress_poster(poster)
        except (OSError, ValueError):
            raise forms.ValidationError('Не удалось обработать изображение, попробуйте сохранить его в JPEG или PNG.')


class AdminDescriptionForm(PosterFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        is_expired = kwargs.pop('is_expired')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Сохранить'))

        self.fields['description'] = forms.CharField(widget=TinyMCE(attrs={'rows': 30}), label='Описание')
        self.fields['date'].input_formats = settings.INPUT_DATE_FORMATS
        self.fields['date'].widget.attrs['readonly'] = is_expired
        self.fields['date'].help_text = 'Событие уже состоялось, поменять дату нельзя' if is_expired else ''
        self.fields['date_end'].input_formats = settings.INPUT_DATE_FORMATS
        self.fields['date_end'].widget.attrs['readonly'] = is_expired
        self.fields['date_end'].help_text = 'Событие уже состоялось, поменять дату нельзя' if is_expired else ''

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        date_end = cleaned_data.get('date_end')
        if date and date_end and date_end < date:
            self.add_error('date_end', 'Дата окончания не может быть раньше даты начала.')
        return cleaned_data

    class Meta:
        model = Event
        fields = [
            'title',
            'gym',
            'date',
            'date_end',
            'poster',
            'description',
            'short_description',
        ]
        labels = {
            'title': 'Название',
            'gym': 'Скалодром',
            'date': 'Дата (MM/DD/YYYY)',
            'date_end': 'Дата окончания (MM/DD/YYYY)',
            'poster': 'Афиша',
            'short_description': 'Краткое описание',
        }
        widgets = {
            'date': DatePickerInput(),
            'date_end': DatePickerInput(),
        }


class EventSettingsForm(forms.ModelForm):
    registration_fields = forms.MultipleChoiceField(
        choices=Event.REGISTRATION_FIELDS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Дополнительные поля формы регистрации'
    )
    required_fields = forms.MultipleChoiceField(
        choices=Event.REQUIRED_FIELDS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Обязательные поля при регистрации'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Сохранить'))
        self.fields['registration_close_datetime'].input_formats = settings.INPUT_DATE_FORMATS + [
            '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%m/%d/%Y %H:%M', '%m/%d/%Y %H:%M:%S'
        ]
        # радиокнопки в браузере всегда присылают значение, а без ключа update_event_settings оставит текущее
        self.fields['birth_format'].required = False

    def clean(self):
        cleaned_data = super().clean()
        reg_close = cleaned_data.get('registration_close_datetime')
        if reg_close and self.instance and self.instance.date:
            if reg_close.date() >= self.instance.date:
                self.add_error(
                    'registration_close_datetime',
                    'Дата закрытия регистрации должна быть раньше даты начала события.'
                )
        return cleaned_data

    class Meta:
        model = Event
        fields = [
            'routes_num',
            'is_published',
            'is_registration_open',
            'registration_close_datetime',
            'is_results_allowed',
            'is_enter_result_allowed',
            'is_count_only_entered_results',
            'is_view_full_results',
            'is_view_route_color',
            'is_view_route_grade',
            'is_view_route_score',
            'is_separate_score_by_groups',
            'is_without_registration',
            'is_view_pin_after_registration',
            'is_check_result_before_enter',
            'is_update_result_allowed',
            'score_type',
            'redpoint_points',
            'flash_points_pc',
            'count_routes_num',
            'group_num',
            'group_list',
            'set_num',
            'set_list',
            'set_max_participants',
            'registration_fields',
            'required_fields',
            'birth_format',
            'participant_min_age',
            'reg_type_list',
        ]
        labels = {
            'routes_num': 'Количество трасс',
            'is_published': 'Событие опубликовано',
            'is_registration_open': 'Регистрация на событие разрешена',
            'registration_close_datetime': 'Дата и время автоматического закрытия регистрации',
            'is_results_allowed': 'Просмотр результатов разрешён',
            'is_enter_result_allowed': 'Ввод результатов разрешён',
            'is_count_only_entered_results': 'Учитывать только введённые результаты',
            'is_view_full_results': 'Показывать полные результаты',
            'is_view_route_color': 'Показывать цвет трассы',
            'is_view_route_grade': 'Показывать категорию трассы',
            'is_view_route_score': 'Показывать стоимость трассы',
            'is_separate_score_by_groups': 'Рассчитывать стоимость трассы отдельно по каждой группе',
            'is_without_registration': 'Ввод результатов без регистрации',
            'is_view_pin_after_registration': 'Показывать участнику пин-код после регистрации',
            'is_check_result_before_enter': 'При вводе результата показывать участнику страницу потверждения',
            'is_update_result_allowed': 'Разрешить участнику обновлять свои результаты',
            'score_type': 'Тип подсчёта результатов',
            'redpoint_points': 'Очки за трассу',
            'flash_points_pc': 'Увеличение баллов за Flash в %',
            'count_routes_num': 'Учитывать количество лучших трасс (0 - учитывать все)',
            'group_num': 'Количество групп участников',
            'group_list': 'Список групп через запятую',
            'set_num': 'Количество сетов',
            'set_list': 'Список сетов через запятую',
            'set_max_participants': 'Максимальное число участников в сете (0 - не ограничено)',
            'registration_fields': 'Дополнительные поля формы регистрации',
            'required_fields': 'Обязательные поля при регистрации',
            'birth_format': 'Формат даты рождения',
            'participant_min_age': 'Минимальный возраст участника',
            'reg_type_list': 'Список типов регистрации участников, через запятую',
        }
        widgets = {
            'registration_close_datetime': DateTimePickerInput(options={'format': 'MM/DD/YYYY HH:00', 'stepping': 60}),
            'birth_format': forms.RadioSelect,
        }
        help_texts = {
            'registration_close_datetime': 'Оставьте пустым для отмены автоматического закрытия регистрации',
            'birth_format': 'Что спрашивать в поле «Год/дата рождения». Полную дату видит только организатор. '
                            'При смене формата уже введённые годы рождения сохраняются.',
            'group_list': 'Например: "Спорт, Любители, Новички"',
            'set_list': 'Например: "Утренний сет (8:00), Дневной сет (13:00), Вечерний сет (18:00)"',
            'reg_type_list': 'Например: "Стандарт, + Футболка, + Футболка и сувенир"',
        }


class EventPremiumSettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Сохранить'))

    class Meta:
        model = Event
        fields = [
            'premium_price',
            'is_premium',
            'is_expired',

        ]
        labels = {
            'premium_price': 'Стоимость премиум-доступа',
            'is_premium': 'Премиум-доступ',
            'is_expired': 'Событие состоялось',
        }

price_field_help_text = 'При оплате по Yoomoney - стоимость в рублях, по СБП - ссылка (QR-код) для оплаты'
class EventPaySettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        reg_type_list = kwargs.pop('reg_type_list')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('pay_settings', 'Сохранить'))

        if len(reg_type_list) > 1:
            for item in reg_type_list:
                self.fields[f'price_{item[0]}'] = forms.CharField(label=f'Стоимость/ссылка для типа "{item[1]}"',
                                                                     required=True, help_text=price_field_help_text)
            del self.fields['price']

    class Meta:
        model = Event
        fields = [
            'is_pay_allowed',
            'pay_type',
            'price',
            'wallet',
        ]
        labels = {
            'is_pay_allowed': 'Оплачивать стартовые взносы на сайте',
            'pay_type': 'Тип оплаты',
            'price': 'Стоимость/ссылка',
            'wallet': 'Кошелек для оплаты',
        }
        help_texts = {
            'price': price_field_help_text,
        }


class EventAdminServiceForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

        self.helper.add_input(Submit('clear_event', 'Очистить событие', css_class='btn-primary'))
        self.helper.add_input(Submit('create_routes', 'Создать трассы', css_class='btn-primary'))
        self.helper.add_input(Submit('create_participant', 'Создать участника', css_class='btn-primary'))
        self.helper.add_input(Submit('update_score', 'Посчтитать рузультаты', css_class='btn-primary'))


class AccentForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['top'] = forms.ChoiceField(widget=forms.RadioSelect, choices=ACCENT_TYPE)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            InlineRadios('top', template='events/snippets/sn-form-accent.html'),
        )


class AccentFrenchForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['top'] = forms.IntegerField(label="T", required=False)
        self.fields['zone'] = forms.IntegerField(label="Z", required=False)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            Field('top', template='events/snippets/sn-form-accent_french.html'),
            Field('zone', template='events/snippets/sn-form-accent_french.html'),
        )


class AccentParticipantForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields['pin'].required = False
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False

    class Meta:
        model = Participant
        fields = [
            'first_name',
            'last_name',
            'pin',
        ]
        labels = {
            'pin': 'PIN-код',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
        }


class ScoreTableForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['score'] = forms.IntegerField(label='')

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            Field('score'),
        )


class RouteEditForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.form_style = 'inline'
        self.fields['grade'].required = False
        self.fields['color'].required = False

    class Meta:
        model = Route
        fields = [
            'grade',
            'color',
        ]
        labels = {
            'grade': 'Категория',
            'color': 'Цвет зацепок',
        }


class ParticipantForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        group_list = kwargs.pop('group_list')
        set_list = kwargs.pop('set_list')
        registration_fields = kwargs.pop('registration_fields')
        is_pay_allowed = kwargs.pop('is_pay_allowed')
        reg_type_list = kwargs.pop('reg_type_list')
        birth_format = kwargs.pop('birth_format', Event.BIRTH_FORMAT_YEAR)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Сохранить'))
        self.fields['pin'].widget.attrs['readonly'] = True
        self.fields['email'].widget.attrs['readonly'] = True

        for field in self.Meta.fields:
            self.fields[field].required = False
        if group_list:
            self.fields['group_index'] = forms.ChoiceField(choices=tuple([(name, name) for name in group_list]),
                                                           label='Категория',
                                                           required=False)
        if set_list:
            self.fields['set_index'] = forms.ChoiceField(choices=tuple([(name, name) for name in set_list]),
                                                         label='Сет',
                                                         required=False)
        reg_types = reg_type_list.split(',') if reg_type_list != None else []
        if len(reg_types) > 1:
            self.fields['reg_type_index'] = forms.ChoiceField(choices=tuple([(i, t.strip()) for i, t in enumerate(reg_types)]),
                                                              label='Тип регистрации',
                                                              required=False)
        
        deleting_fields = list(set(Event.OPTIONAL_FIELDS) - set(registration_fields))
        # birth_year в registration_fields включает одно из двух полей, в зависимости от формата события
        if Event.FIELD_BIRTH_YEAR not in registration_fields:
            deleting_fields.append(Event.FIELD_BIRTH_DATE)
        elif birth_format == Event.BIRTH_FORMAT_DATE:
            deleting_fields.append(Event.FIELD_BIRTH_YEAR)
        else:
            deleting_fields.append(Event.FIELD_BIRTH_DATE)
        for field in deleting_fields:
            del self.fields[field]
        if not is_pay_allowed:
            del self.fields['paid']

    class Meta:
        model = Participant
        fields = [
            'last_name',
            'first_name',
            Event.FIELD_MIDDLE_NAME,
            'pin',
            Event.FIELD_GENDER,
            Event.FIELD_BIRTH_YEAR,
            Event.FIELD_BIRTH_DATE,
            Event.FIELD_CITY,
            Event.FIELD_TEAM,
            Event.FIELD_GRADE,
            Event.FIELD_EMAIL,
            Event.FIELD_PHONE,
            'paid',
        ]
        labels = {
            'last_name': 'Фамилия',
            'first_name': 'Имя',
            Event.FIELD_MIDDLE_NAME: 'Отчество',
            'pin': 'Пин-код',
            Event.FIELD_GENDER: 'Пол',
            Event.FIELD_BIRTH_YEAR: 'Год рождения',
            Event.FIELD_BIRTH_DATE: 'Дата рождения',
            Event.FIELD_CITY: 'Город',
            Event.FIELD_TEAM: 'Команда',
            Event.FIELD_GRADE: 'Спортивный разряд',
            Event.FIELD_EMAIL: 'E-mail',
            Event.FIELD_PHONE: 'Телефон',
            'paid': 'Оплата произведена',
        }
        widgets = {
            Event.FIELD_BIRTH_DATE: _birth_date_widget(),
        }


class CreateEventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Создать'))
        self.fields['date'].input_formats = settings.INPUT_DATE_FORMATS
        self.fields['date_end'].input_formats = settings.INPUT_DATE_FORMATS

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        date_end = cleaned_data.get('date_end')
        if date and date_end and date_end < date:
            self.add_error('date_end', 'Дата окончания не может быть раньше даты начала.')
        return cleaned_data

    class Meta:
        model = Event
        fields = [
            'title',
            'date',
            'date_end',
        ]
        labels = {
            'title': 'Название',
            'date': 'Дата (MM/DD/YYYY)',
            'date_end': 'Дата окончания (MM/DD/YYYY)',
        }
        widgets = {
            'date': DatePickerInput(),
            'date_end': DatePickerInput(),
        }


class PromoCodeAddForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('add_promocode', 'Добавить'))

    class Meta:
        model = PromoCode
        fields = [
            'title',
            'price',
            'max_applied_num',
        ]
        labels = {
            'title': 'Промо Код',
            'price': 'Стоимость',
            'max_applied_num': 'Ограничить число применений',
        }
        help_texts = {
            'title': 'Например "SUPERSALE10"',
            'max_applied_num': '0 - не ограничивать',
        }


class WalletForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('wallet', 'Отправить'))

    class Meta:
        model = Wallet
        fields = [
            'title',
            'wallet_id',
            'notify_secret_key',
        ]
        labels = {
            'title': 'Название кошелька',
            'wallet_id': 'ID кошелька',
            'notify_secret_key': 'Секрет для проверки подлинности',
        }
