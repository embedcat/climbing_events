import datetime
from django import template
from django.urls import reverse
from events import services

register = template.Library()


@register.filter
def set_label(index, event):
    set_list = services.get_set_list(event=event)
    return set_list[index]


@register.filter
def group_label(index, event):
    group_list = services.get_group_list(event=event)
    return group_list[index]


@register.filter
def reg_type_label(index, event):
    reg_type_list = event.reg_type_list.split(',')
    return reg_type_list[index].strip()


@register.filter(name='zip')
def zip_lists(a, b):
    return zip(a, b)


@register.filter
def event_is_today(val):
    if hasattr(val, 'is_today'):
        return val.is_today
    if isinstance(val, (datetime.date, datetime.datetime)):
        if isinstance(val, datetime.datetime):
            val = val.date()
        return val == datetime.date.today()
    return False


# Раздел сайта по имени адреса: полоса сайта подсвечивает «События», «Мои события» или «Инструкции»
_EVENTS_PAGES = {'main', 'event', 'enter_results', 'results', 'participants', 'registration', 'event_pay',
                 'event_pay_done'}
_HELP_PAGES = {'help', 'about'}
_PROJECT_PAGES = {'stat'}
_ACCOUNT_PAGES = {'account_login', 'account_signup', 'account_logout', 'account_reset_password'}


def section_of(url_name: str) -> str:
    if url_name in _EVENTS_PAGES:
        return 'events'
    if url_name in _HELP_PAGES:
        return 'help'
    if not url_name or url_name in _ACCOUNT_PAGES or url_name in _PROJECT_PAGES or url_name.startswith('account_'):
        return ''
    # остальное — кабинет организатора: панель события, кошельки, создание
    return 'mine'


@register.simple_tag(takes_context=True)
def site_section(context):
    match = getattr(context.get('request'), 'resolver_match', None)
    return section_of(match.url_name if match else '')


# Разделы панели события (docs/mockups/site.html): группа, адрес, название, подсказка для списка на телефоне.
# Адреса других страниц панели подсвечивают свой раздел: карточка участника — «Участники», платежи — «Оплата»
_PANEL_SECTIONS = [
    ('', [('admin_actions', 'Обзор', 'Главное в день события', False, ())]),
    ('Подготовка', [
        ('admin_description', 'Описание и афиша', 'Название, дата, афиша, текст', False, ()),
        ('admin_settings', 'Настройки', 'Регистрация, группы и сеты, подсчёт', False, ()),
        ('route_editor', 'Трассы', 'Категории и цвета', False, ()),
        ('pay_settings', 'Оплата', 'Взнос, промокоды, кошелёк', False, ('pay_details',)),
    ]),
    ('В день события', [
        ('panel_participants', 'Участники', 'PIN, контакты, оплата', False,
         ('participant', 'participant_routes', 'participant_remove')),
        ('matrix', 'Ввод результатов', 'Матрица для бумажных карточек', True, ()),
    ]),
    ('Итоги', [('admin_protocols', 'Протоколы и файлы', 'Excel, QR-коды, карточки с PIN', False, ())]),
    ('Служебное', [('premium_settings', 'Полный доступ', 'Только суперадмин', False, ())]),
]


def _panel_groups(context):
    request, event = context.get('request'), context.get('event')
    match = getattr(request, 'resolver_match', None)
    current = match.url_name if match else ''
    is_superuser = bool(getattr(getattr(request, 'user', None), 'is_superuser', False))
    groups = []
    for title, items in _PANEL_SECTIONS:
        rows = []
        for url_name, label, hint, external, aliases in items:
            if url_name == 'premium_settings' and not is_superuser:
                continue
            rows.append({
                'url_name': url_name,
                'url': reverse(url_name, args=[event.id]),
                'title': label,
                'hint': hint,
                'external': external,
                'current': current == url_name or current in aliases,
            })
        if rows:
            groups.append({'title': title, 'items': rows})
    return groups


@register.simple_tag(takes_context=True)
def panel_sections(context):
    """ Разделы панели события для бокового меню и списка на телефоне: [{'title', 'items': [...]}] """
    return _panel_groups(context)


@register.simple_tag(takes_context=True)
def panel_current(context):
    """ Раздел панели, на странице которого мы сейчас, или None (страница вне разделов, например оплата доступа) """
    for group in _panel_groups(context):
        for item in group['items']:
            if item['current']:
                return item
    return None


_STAGE_PILLS = {
    services.STAGE_REGISTRATION: ('Регистрация открыта', 'ok'),
    services.STAGE_REGISTRATION_CLOSED: ('Регистрация закрыта', ''),
    services.STAGE_LIVE: ('Идёт сейчас', 'ok'),
    services.STAGE_OVER: ('Ввод закрыт', ''),
    services.STAGE_DONE: ('Завершено', ''),
}


@register.simple_tag
def event_stage_pill(event):
    """ Подпись и вид метки этапа события: черновик, если событие ещё не опубликовано """
    if not event.is_published:
        return {'label': 'Черновик', 'kind': 'warn'}
    label, kind = _STAGE_PILLS[services.get_event_stage(event=event)]
    return {'label': label, 'kind': kind}
