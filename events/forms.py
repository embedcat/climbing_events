from crispy_forms.bootstrap import InlineRadios
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div
from django import forms

from events.models import Participant, Event, Accent, Route
from tinymce.widgets import TinyMCE


class ParticipantRegistrationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        group_list = kwargs.pop('group_list')
        set_list = kwargs.pop('set_list')
        registration_fields = kwargs.pop('registration_fields')
        required_fields = kwargs.pop('required_fields')
        is_enter_form = kwargs.pop('is_enter_form')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        if is_enter_form:
            self.helper.form_tag = False
            self.helper.disable_csrf = True
        else:
            self.helper.add_input(Submit('submit', 'Зарегистрироваться'))
        self.helper.label_class = 'mb-1'

        if Event.FIELD_GENDER in registration_fields:
            self.fields[Event.FIELD_GENDER] = forms.ChoiceField(choices=Participant.GENDERS, label='Пол',
                                                                required=False)
        if Event.FIELD_BIRTH_YEAR in registration_fields:
            self.fields[Event.FIELD_BIRTH_YEAR] = forms.IntegerField(label='Год рождения',
                                                                     required=Event.FIELD_BIRTH_YEAR in required_fields)
        if Event.FIELD_CITY in registration_fields:
            self.fields[Event.FIELD_CITY] = forms.CharField(label='Город',
                                                            required=Event.FIELD_CITY in required_fields)
        if Event.FIELD_TEAM in registration_fields:
            self.fields[Event.FIELD_TEAM] = forms.CharField(label='Команда',
                                                            required=Event.FIELD_TEAM in required_fields)
        if Event.FIELD_GRADE in registration_fields:
            self.fields[Event.FIELD_GRADE] = forms.ChoiceField(choices=Participant.GRADES, label='Разряд',
                                                               required=False)

        if group_list:
            self.fields['group_index'] = forms.ChoiceField(choices=tuple([(name, name) for name in group_list]),
                                                           label='Категория',
                                                           required=False)
        if set_list:
            self.fields['set_index'] = forms.ChoiceField(choices=tuple([(name, name) for name in set_list]),
                                                         label='Сет',
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


class EventAdminDescriptionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Сохранить'))

        self.fields['description'] = forms.CharField(widget=TinyMCE(attrs={'cols': 80, 'rows': 30}),
                                                     label='Описание')

    class Meta:
        model = Event
        fields = [
            'title',
            'date',
            'poster',
            'description',
        ]
        labels = {
            'title': 'Название',
            'date': 'Дата (YYYY-MM-DD)',
            'poster': 'Афиша',
        }


class EventAdminSettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Сохранить'))

    class Meta:
        model = Event
        fields = [
            'routes_num',
            'is_published',
            'is_registration_open',
            'is_results_allowed',
            'is_enter_result_allowed',
            'is_count_only_entered_results',
            'is_view_full_results',
            'is_view_route_color',
            'is_view_route_grade',
            'is_view_route_score',
            'score_type',
            'flash_points',
            'redpoint_points',
            'group_num',
            'group_list',
            'set_num',
            'set_list',
            'set_max_participants',
            'registration_fields',
            'required_fields',
            'is_without_registration',
        ]
        labels = {
            'routes_num': 'Количество трасс',
            'is_published': 'Событие опубликовано',
            'is_registration_open': 'Регистрация на событие разрешена',
            'is_results_allowed': 'Просмотр результатов разрешён',
            'is_enter_result_allowed': 'Ввод результатов разрешён',
            'is_count_only_entered_results': 'Учитывать только введённые результаты',
            'is_view_full_results': 'Показывать полные результаты',
            'is_view_route_color': 'Показывать цвет трассы',
            'is_view_route_grade': 'Показывать ктегорию трассы',
            'is_view_route_score': 'Показывать стоимость трассы',
            'score_type': 'Тип подсчёта результатов',
            'flash_points': 'Очки за Flash',
            'redpoint_points': 'Очки за Redpoint',
            'group_num': 'Количество групп участников',
            'group_list': 'Список групп через запятую',
            'set_num': 'Количество сетов',
            'set_list': 'Список сетов через запятую',
            'set_max_participants': 'Максимальное число участников в сете (0 - не ограничено)',
            'registration_fields': 'Дополнительные поля формы регистрации',
            'required_fields': 'Обязательные поля при регистрации',
            'is_without_registration': 'Ввод результатов без регистрации',
        }


class EventAdminServiceForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

        self.helper.add_input(Submit('clear_event', 'Очистить событие', css_class='btn-primary'))
        self.helper.add_input(Submit('create_routes', 'Создать трассы', css_class='btn-primary'))
        self.helper.add_input(Submit('create_participant', 'Создать участника', css_class='btn-primary'))
        self.helper.add_input(Submit('update_score', 'Посчтитать рузультаты', css_class='btn-primary'))


class AccentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            InlineRadios('accent', template='events/form-accent.html'),
        )

    class Meta:
        model = Accent
        fields = [
            'accent',
        ]


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
        registration_fields = kwargs.pop('registration_fields')
        required_fields = kwargs.pop('required_fields')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Сохранить'))
        self.fields['pin'].widget.attrs['readonly'] = True
        self.fields[Event.FIELD_GENDER].required = False
        self.fields[Event.FIELD_BIRTH_YEAR].required = False
        self.fields[Event.FIELD_CITY].required = False
        self.fields[Event.FIELD_TEAM].required = False
        self.fields[Event.FIELD_GRADE].required = False

    class Meta:
        model = Participant
        fields = [
            'last_name',
            'first_name',
            'pin',
            Event.FIELD_GENDER,
            Event.FIELD_BIRTH_YEAR,
            Event.FIELD_CITY,
            Event.FIELD_TEAM,
            Event.FIELD_GRADE,
        ]
