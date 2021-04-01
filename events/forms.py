from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Button
from django import forms

from events.models import Participant, Event, Accent
from tinymce.widgets import TinyMCE


class ParticipantRegistrationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        group_list = kwargs.pop('group_list')
        set_list = kwargs.pop('set_list')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Зарегистрироваться'))
        self.helper.label_class = 'mb-1'

        self.fields['birth_year'].required = False
        self.fields['city'].required = False
        self.fields['team'].required = False
        self.fields['grade'].required = False

        if group_list:
            self.fields['group_index'] = forms.ChoiceField(choices=tuple([(name, name) for name in group_list]),
                                                           label='Категория')
        if set_list:
            self.fields['set_index'] = forms.ChoiceField(choices=tuple([(name, name) for name in set_list]),
                                                         label='Сет')

    class Meta:
        model = Participant
        fields = [
            'first_name',
            'last_name',
            'gender',
            'birth_year',
            'city',
            'team',
            'grade',
        ]
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
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
            'score_type',
            'flash_points',
            'redpoint_points',
            'group_num',
            'group_list',
            'set_num',
            'set_list',
        ]
        labels = {
            'routes_num': 'Количество трасс',
            'is_published': 'Событие опубликовано',
            'is_registration_open': 'Регистрация на событие разрешена',
            'is_results_allowed': 'Просмотр результатов разрешён',
            'is_enter_result_allowed': 'Ввод результатов разрешён',
            'is_count_only_entered_results': 'Учитывать только введённые результаты',
            'is_view_full_results': 'Показывать полные результаты',
            'score_type': 'Тип подсчёта результатов',
            'flash_points': 'Очки за Flash',
            'redpoint_points': 'Очки за Redpoint',
            'group_num': 'Количество групп участников',
            'group_list': 'Список групп через запятую',
            'set_num': 'Количество сетов',
            'set_list': 'Список сетов через запятую',
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
        self.helper = FormHelper()
        # self.helper.form_method = 'post'
        # self.helper.add_input(Submit("submit", "Save"))
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.field_class = 'form-check form-check-inline'

    accent = forms.TypedChoiceField(
        label='',
        choices=Accent.ACCENT_TYPE,
        widget=forms.RadioSelect,
        initial=Accent.ACCENT_NO,
        required=True,
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
