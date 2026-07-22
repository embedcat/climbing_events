import datetime
from django import template
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
