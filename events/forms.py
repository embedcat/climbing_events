from crispy_forms.bootstrap import FormActions, TabHolder, Tab
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Button
from django import forms

from events.models import Participant, Event, Accent


class ParticipantRegistrationForm(forms.ModelForm):
    def __init__(self, group_list, *args, **kwargs):
        super().__init__()
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Зарегистрироваться'))
        self.helper.label_class = 'mb-1'

        self.fields['birth_year'].required = False
        self.fields['city'].required = False
        self.fields['team'].required = False
        self.fields['grade'].required = False

        self.group_list = kwargs.get('bla', '2312')
        self.fields['group_index'] = forms.ChoiceField(choices=tuple([(name, name) for name in group_list]))

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
            'group_index',
            'set_index',
        ]
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'gender': 'Пол',
            'birth_year': 'Год рождения',
            'city': 'Город',
            'team': 'Команда',
            'grade': 'Спортивный разряд',
            'group_index': 'Категория',
            'set_index': 'Сет',
        }


class EventAdminDescriptionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Сохранить'))

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
            'description': 'Описание',
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
