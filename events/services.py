from dataclasses import asdict, dataclass
import io
import operator
import os
import random
import string
from datetime import datetime
from typing import Iterable
import dacite
from events.xl_tools import save_virtual_workbook

import segno
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import QuerySet, Count
from django.http import HttpResponse

from config import settings
from events import img_tools, xl_tools, mock
from events.exceptions import (
    DuplicateParticipantError, EntryClosedError, InvalidResultsError, ParticipantNotFoundError,
    ParticipantTooYoungError, RegistrationClosedError, ResultsUpdateNotAllowedError, SetFullError,
    WithoutRegistrationDisabledError,
)
from events.models import CustomUser, Event, PayDetail, PromoCode, Route, Participant, Wallet


def create_event(owner: get_user_model(), title: str, date: datetime, date_end: datetime = None) -> Event:
    superuser = CustomUser.objects.filter(is_superuser=True).first() or CustomUser.objects.filter(id=1).first()
    premium_price = superuser.premium_price if superuser else 0
    event = Event.objects.create(
        owner=owner,
        title=title,
        date=date,
        date_end=date_end,
        premium_price=premium_price,
    )
    create_event_routes(event=event)
    return event


# ================================================
# =================== Utils ======================
# ================================================


def _get_participant_json_key(gender: Participant.GENDERS, group_index: int) -> str:
    return f"{gender}_{group_index}"


def get_group_list(event: Event) -> list:
    return [item.strip() for item in event.group_list.split(',')][:event.group_num] if event.group_num > 1 else ['']


def get_set_list(event: Event) -> list:
    return [item.strip() for item in event.set_list.split(',')][:event.set_num] if event.set_num > 1 else []


def _get_all_json_keys(event: Event) -> Iterable:
    return (f"{gender[0]}_{group_index}" for group_index in range(event.group_num) for gender in Participant.GENDERS)

# ================================================
# =================== Clear ======================
# ================================================


def remove_routes(event: Event) -> None:
    event.route.all().delete()


def remove_participants(event: Event) -> None:
    event.participant.all().delete()


def remove_event(event: Event) -> None:
    event.delete()


def clear_event(event: Event) -> None:
    remove_participants(event=event)
    remove_routes(event=event)
    create_event_routes(event=event)


def clear_results(event: Event) -> None:
    participants = event.participant.all()
    for participant in participants:
        _clear_participant_score(participant=participant)
    routes = event.route.all()
    for route in routes:
        route.score_json.clear()
        route.save()


# ================================================
# =================== Events =====================
# ================================================

def update_event_settings(event: Event, cd: dict) -> None:
    # read previous values from DB: a bound ModelForm has already written cleaned_data into event
    stored = Event.objects.get(pk=event.pk)
    old_routes_num = stored.routes_num
    need_update_results = stored.score_type != cd['score_type'] or \
        stored.redpoint_points != cd['redpoint_points'] or \
        stored.flash_points_pc != cd['flash_points_pc'] or \
        stored.count_routes_num != cd['count_routes_num']

    event.routes_num = cd['routes_num']
    event.is_published = cd['is_published']
    event.is_registration_open = cd['is_registration_open']
    event.registration_close_datetime = cd.get('registration_close_datetime')
    event.is_enter_result_allowed = cd['is_enter_result_allowed']
    event.is_results_allowed = cd['is_results_allowed']
    event.is_count_only_entered_results = cd['is_count_only_entered_results']
    event.is_view_full_results = cd['is_view_full_results']
    event.is_view_route_color = cd['is_view_route_color']
    event.is_view_route_grade = cd['is_view_route_grade']
    event.is_view_route_score = cd['is_view_route_score']
    event.is_separate_score_by_groups = cd['is_separate_score_by_groups']
    event.score_type = cd['score_type']
    event.redpoint_points = cd['redpoint_points']
    event.flash_points_pc = cd['flash_points_pc']
    event.count_routes_num = cd['count_routes_num']
    event.group_num = cd['group_num']
    event.group_list = cd['group_list']
    event.set_num = cd['set_num']
    event.set_list = cd['set_list']
    event.set_max_participants = cd['set_max_participants']
    event.registration_fields = cd['registration_fields']
    event.required_fields = cd['required_fields']
    event.is_without_registration = cd['is_without_registration']
    event.is_view_pin_after_registration = cd['is_view_pin_after_registration']
    event.is_check_result_before_enter = cd['is_check_result_before_enter']
    event.is_update_result_allowed = cd['is_update_result_allowed']
    event.participant_min_age = cd['participant_min_age']
    event.reg_type_list = cd['reg_type_list']
    event.reg_type_num = 0 if event.reg_type_list == None else len(event.reg_type_list.split(','))

    event.save()

    if old_routes_num != event.routes_num:
        clear_results(event=event)
        remove_routes(event=event)
        create_event_routes(event=event)
    if need_update_results:
        update_results(event=event)


def update_event_premium_settings(event: Event, cd: dict) -> None:
    event.premium_price = cd['premium_price']
    event.is_premium = cd['is_premium']
    event.is_expired = cd['is_expired']
    event.save()


def update_event_pay_settings(event: Event, cd: dict) -> bool:
    if cd['pay_type'] == Event.PAY_TYPE_YOOMONEY and not cd['wallet']:
        return False
    event.is_pay_allowed = cd['is_pay_allowed']
    event.price = cd['price'] if 'price' in cd else 0
    price_index = 0
    price_list = {}
    while f'price_{price_index}' in cd:
        price_list.update({price_index: cd[f'price_{price_index}']})
        price_index += 1
    event.price_list = price_list
    event.wallet = cd['wallet']
    event.pay_type = cd['pay_type']
    event.save()
    return True


def mark_events_as_expired(events: QuerySet) -> None:
    for event in events:
        event.is_expired = True
        event.save()


# ================================================
# =================== Routes =====================
# ================================================


def create_event_routes(event: Event) -> None:
    for i in range(event.routes_num):
        Route.objects.create(
            number=i + 1,
            event=event,
        )


def get_route_score(route: Route, json_key: str) -> float:
    return route.score_json.get(json_key, 0)


# ================================================
# ======== Register and edit participant =========
# ================================================


def get_set_list_available(event: Event, participant: Participant = None) -> list:
    set_list_all = get_set_list(event=event)
    set_list = []
    if event.set_max_participants > 0:
        for i, item in enumerate(set_list_all):
            set_participants_num = event.participant.filter(set_index=i).count()
            if set_participants_num < event.set_max_participants or (participant.set_index == i if participant else False):
                set_list.append(item)
    else:
        set_list = set_list_all
    return set_list


def get_registration_fields(event: Event) -> list:
    registration_fields = list(event.registration_fields) if event.registration_fields else []
    if event.participant_min_age and Event.FIELD_BIRTH_YEAR not in registration_fields:
        registration_fields.append(Event.FIELD_BIRTH_YEAR)
    if Event.FIELD_EMAIL not in registration_fields and event.is_pay_allowed:
        registration_fields.append(Event.FIELD_EMAIL)
    return registration_fields


def get_registration_required_fields(event: Event) -> list:
    required_fields = list(event.required_fields) if event.required_fields else []
    if event.participant_min_age and Event.FIELD_BIRTH_YEAR not in required_fields:
        required_fields.append(Event.FIELD_BIRTH_YEAR)
    if Event.FIELD_EMAIL not in required_fields and event.is_pay_allowed:
        required_fields.append(Event.FIELD_EMAIL)
    return required_fields


def update_participant(event: Event, participant: Participant, cd: dict) -> Participant:
    current_group_index = participant.group_index
    new_group_index = get_group_list(event=event).index(cd['group_index']) if 'group_index' in cd else participant.group_index
    need_update_results = 'group_index' in cd and current_group_index != new_group_index

    participant.event = event
    if 'first_name' in cd:
        participant.first_name = cd['first_name']
    if 'last_name' in cd:
        participant.last_name = cd['last_name']
    if Event.FIELD_GENDER in cd:
        participant.gender = cd[Event.FIELD_GENDER]
    if Event.FIELD_BIRTH_YEAR in cd:
        participant.birth_year = cd[Event.FIELD_BIRTH_YEAR]
    if Event.FIELD_CITY in cd:
        participant.city = cd[Event.FIELD_CITY]
    if Event.FIELD_TEAM in cd:
        participant.team = cd[Event.FIELD_TEAM]
    if Event.FIELD_GRADE in cd:
        participant.grade = cd[Event.FIELD_GRADE]
    if 'group_index' in cd:
        participant.group_index = new_group_index
    if 'set_index' in cd:
        participant.set_index = get_set_list(event=event).index(cd['set_index']) if isinstance(cd['set_index'], int) else get_set_list(event=event).index(cd['set_index'])
    if 'paid' in cd:
        participant.paid = cd['paid']
    if 'email' in cd:
        participant.email = cd['email']
    if 'reg_type_index' in cd:
        participant.reg_type_index = cd['reg_type_index']
    if 'phone_number' in cd:
        participant.phone_number = cd['phone_number']
    participant.save()

    if need_update_results:
        _update_results(event=event, gender=participant.gender, group_index=current_group_index)
        _update_results(event=event, gender=participant.gender, group_index=new_group_index)
    return participant


def _check_participants_number_to_close_registration(event: Event) -> None:
    if event.set_max_participants > 0 \
            and event.participant.count() >= event.set_max_participants * event.set_num:
        event.is_registration_open = False
        event.save()


def _create_participant(event: Event, first_name: str, last_name: str,
                        gender: Participant.gender = Participant.GENDER_MALE,
                        birth_year: int = 2000, city: str = '', team: str = '',
                        grade: Participant.GRADES = Participant.GRADE_BR,
                        group_index: int = 0,
                        set_index: int = 0,
                        email: str = '',
                        reg_type_index: int = 0,
                        phone_number: str = '',
                        ) -> Participant or None:
    if 0 < event.set_max_participants <= event.participant.filter(set_index=set_index).count():
        return None
    pin = 1111
    while event.participant.filter(pin=pin).count() != 0:
        pin = random.randint(1000, 9999)
    participant = Participant.objects.create(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        birth_year=birth_year,
        city=city,
        team=team,
        grade=grade,
        event=event,
        pin=pin,
        group_index=group_index,
        set_index=set_index,
        email=email,
        reg_type_index=reg_type_index,
        phone_number=phone_number,
    )
    return participant


def register_participant(event: Event, cd: dict) -> Participant:
    first_name = cd.get('first_name', '')
    last_name = cd.get('last_name', '')
    if not first_name or not last_name:
        raise ValueError("First name and last name are required.")

    if event.participant.filter(first_name=first_name, last_name=last_name).exists():
        raise DuplicateParticipantError

    birth_year = cd.get(Event.FIELD_BIRTH_YEAR, 0)
    if event.participant_min_age and birth_year:
        if datetime.today().year - int(birth_year) < event.participant_min_age:
            raise ParticipantTooYoungError(event.participant_min_age)

    groups = get_group_list(event=event)
    sets = get_set_list(event=event)

    group_val = cd.get('group_index', 0)
    if isinstance(group_val, int):
        group_idx = group_val if 0 <= group_val < len(groups) else 0
    else:
        group_idx = groups.index(group_val) if group_val in groups else 0

    set_val = cd.get('set_index', 0)
    if isinstance(set_val, int):
        set_idx = set_val if 0 <= set_val < len(sets) else 0
    else:
        set_idx = sets.index(set_val) if set_val in sets else 0

    participant = _create_participant(
        event=event,
        first_name=first_name,
        last_name=last_name,
        gender=cd.get(Event.FIELD_GENDER, Participant.GENDER_MALE),
        birth_year=birth_year or 0,
        city=cd.get(Event.FIELD_CITY, ''),
        team=cd.get(Event.FIELD_TEAM, ''),
        grade=cd.get(Event.FIELD_GRADE, Participant.GRADE_BR),
        group_index=group_idx,
        set_index=set_idx,
        email=cd.get(Event.FIELD_EMAIL, ''),
        reg_type_index=cd.get('reg_type_index', 0),
        phone_number=cd.get('phone_number', ''),
    )
    _check_participants_number_to_close_registration(event=event)
    return participant


def _clear_participant_score(participant: Participant) -> None:
    participant.score = 0
    participant.place = 0
    participant.french_accents = {}
    participant.is_entered_result = False
    participant.save()


def is_registration_open(event: Event) -> bool:
    if not event.is_published:
        return False
    if not event.is_registration_open:
        return False
    if event.set_max_participants != 0 and event.participant.count() >= event.set_max_participants * event.set_num:
        return False
    if not event.is_premium:
        if event.participant.count() >= event.max_participants:
            return False        
    return True


# ================================================
# ========== Calc and update results =============
# ================================================


@dataclass
class Accent:
    top: int = 0
    zone: int = 0


def form_data_to_results(form_cleaned_data: list) -> dict:
    '''
    [{'top': 2, 'zone': 0}, {'top': 0, 'zone': 3} ... ] ->
    -> {0: {'top': 2, 'zone': 0}, 1: {'top': 0, 'zone': 3} ... }
    '''
    results = {}
    for i, result in enumerate(form_cleaned_data):
        accent = Accent(top=int(result.get('top') or 0), zone=int(result.get('zone') or 0))
        if accent.top and accent.zone == 0:
            accent.zone = accent.top
        results.update({i: asdict(accent)})
    return results


def _calc_participant_score_by_scores(scores: dict, num_of_best_scores: int) -> dict:
    sorted_scores_dict = dict(sorted(scores.items(), key=lambda item: float(item[1]), reverse=True))
    if num_of_best_scores:
        sorted_scores_dict = dict(list(sorted_scores_dict.items())[:num_of_best_scores])
    return {"score": round(sum(sorted_scores_dict.values()), 2),
            "counted_routes": list(sorted_scores_dict.keys()),
            }


def _update_participant_score(event: Event, participant: Participant, routes: QuerySet, json_key: str):
    scores = {}
    tops, tops_a, zones, zones_a = 0, 0, 0, 0
    for no, accent in participant.french_accents.items():
        score = 0
        result = dacite.from_dict(data_class=Accent, data=accent)

        if event.score_type == Event.SCORE_FRENCH:
            tops += 1 if result.top > 0 else 0
            tops_a += result.top
            zones += 1 if result.zone > 0 else 0
            zones_a += result.zone

        else:
            if result.top > 0:
                if event.score_type == Event.SCORE_NUM_ACCENTS:
                    score = 100 + (1 if result.top == 1 else 0)
                else:
                    base_route_points = routes[int(no)].score_json.get(json_key, 0)
                    flash_k = 1 + event.flash_points_pc / 100
                    base_score_with_flash = base_route_points * flash_k if result.top == 1 else base_route_points
                    if event.score_type != Event.SCORE_GRADE:
                        base_score_with_flash *= event.redpoint_points
                    score = base_score_with_flash
                scores.update({no: round(score, 2)})

    if event.score_type == Event.SCORE_FRENCH:
        participant.score = 10000*tops + 1000*zones + 100*(100-tops_a) + 10*(100-zones_a)
        participant.french_score = f'{tops}T{tops_a} {zones}z{zones_a}'
        participant.counted_routes = [i for i in range(event.routes_num)]
    else:
        participant.scores = scores
        result = _calc_participant_score_by_scores(scores=scores,
                                                   num_of_best_scores=int(event.count_routes_num) if (event.score_type == Event.SCORE_PROPORTIONAL or event.score_type == Event.SCORE_GRADE) else 0)
        participant.score = result.get("score", 0)
        participant.counted_routes = result.get("counted_routes", [])

    participant.save()

def _update_results(event: Event, gender: Participant.GENDERS, group_index: int):
    json_key = _get_participant_json_key(gender=gender, group_index=group_index)

    participants = event.participant.filter(gender=gender, group_index=group_index) if event.is_separate_score_by_groups \
        else event.participant.filter(gender=gender)

    # update routes:
    routes = event.route.all().order_by('number')
    for no, route in enumerate(routes):
        # update_route_score:
        route_score = 1
        if event.score_type == Event.SCORE_SIMPLE_SUM:
            route_score = 1.0
        elif event.score_type == Event.SCORE_PROPORTIONAL:
            accents_num = 0
            # get num of accents of route:
            if event.is_count_only_entered_results:
                for p in participants:
                    accent = dacite.from_dict(data_class=Accent, data=p.french_accents.get(
                        str(no), {})) if p.is_entered_result else Accent()
                    accents_num += 1 if accent.top > 0 else 0
            else:
                accents_num = len(participants)
            route_score = 1 / accents_num if accents_num != 0 else 0
        elif event.score_type == Event.SCORE_GRADE:
            route_score = int(event.score_table.get(route.grade, 1))
        elif event.score_type == Event.SCORE_NUM_ACCENTS:
            route_score = 1
        elif event.score_type == Event.SCORE_FRENCH:
            route_score = 1
        route.score_json.update({f'{json_key}': route_score})
        route.save()

    # update all participants in group:
    for p in participants:
        _update_participant_score(event=event, participant=p, routes=routes, json_key=json_key)

    # update participant place: место только у тех, кто ввёл результат, остальные стоят без места (place == 0)
    ranked = sorted((p for p in participants if p.is_entered_result), key=operator.attrgetter("score"), reverse=True)
    for index, p in enumerate(ranked):
        p.place = index + 1
        if index != 0 and ranked[index - 1].score == p.score:
            p.place = ranked[index - 1].place
        p.save(update_fields=['place'])
    for p in participants:
        if not p.is_entered_result and p.place != 0:
            p.place = 0
            p.save(update_fields=['place'])


def update_results(event: Event):
    for gender in (Participant.GENDER_MALE, Participant.GENDER_FEMALE):
        for group_index, _ in enumerate(get_group_list(event=event)):
            _update_results(event=event, gender=gender, group_index=group_index)


def check_results(event: Event, results: dict, participant: Participant = None) -> None:
    """ Во французской системе зона не может быть позже топа: если топ есть, попытка зоны не больше попытки топа.
    Если передан участник, в ошибке будет его имя: так понятно, кого поправить при проверке сразу многих """
    if event.score_type != Event.SCORE_FRENCH:
        return
    bad_routes = sorted(int(no) + 1 for no, result in results.items()
                        if result.get('top', 0) > 0 and result.get('zone', 0) > result['top'])
    if bad_routes:
        if participant is None:
            raise InvalidResultsError(routes=bad_routes)
        raise InvalidResultsError(
            f"Зона позже топа: {participant.last_name} {participant.first_name}, "
            f"{'трассы' if len(bad_routes) > 1 else 'трасса'} {', '.join(str(r) for r in bad_routes)}.",
            routes=bad_routes, participant_id=participant.id)


def enter_results(event: Event, participant: Participant, accents: dict, force_update_disable: bool = False):
    check_results(event=event, results=accents)
    # save participant accents:
    participant.french_accents = accents
    participant.is_entered_result = True
    participant.save()

    if not force_update_disable:
        _update_results(event=event, gender=participant.gender, group_index=participant.group_index)


# ================================================
# ========== Enter results by participant ========
# ================================================

MAX_ATTEMPTS = 20  # предел номера попытки в форме ввода французской системы


def get_set_choices(event: Event) -> list:
    """ Сеты события с признаком, что в сете не осталось мест """
    choices = []
    for index, name in enumerate(get_set_list(event=event)):
        is_full = 0 < event.set_max_participants <= event.participant.filter(set_index=index).count()
        choices.append(dict(index=index, name=name, is_full=is_full))
    return choices


def get_entry_config(event: Event) -> dict:
    """ Всё, что нужно экрану ввода результатов, чтобы нарисовать форму """
    return dict(
        id=event.id,
        title=event.title,
        date=event.date_display,
        gym=event.gym,
        score_type=event.score_type,
        routes_num=event.routes_num,
        max_attempts=MAX_ATTEMPTS,
        groups=get_group_list(event=event) if event.group_num > 1 else [],
        sets=get_set_choices(event=event),
        grades=[dict(value=value, label=label) for value, label in Participant.GRADES],
        registration_fields=get_registration_fields(event=event),
        required_fields=get_registration_required_fields(event=event),
        is_enter_result_allowed=event.is_enter_result_allowed,
        is_without_registration=event.is_without_registration,
        is_check_result_before_enter=event.is_check_result_before_enter,
        is_update_result_allowed=event.is_update_result_allowed,
    )


def get_participant_public(event: Event, participant: Participant) -> dict:
    """ Данные участника, которые можно показывать ему самому: без email, телефона и PIN """
    groups = get_group_list(event=event) if event.group_num > 1 else []
    sets = get_set_list(event=event)
    return dict(
        first_name=participant.first_name,
        last_name=participant.last_name,
        gender=participant.gender,
        group_index=participant.group_index,
        group=groups[participant.group_index] if participant.group_index < len(groups) else '',
        set_index=participant.set_index,
        set=sets[participant.set_index] if participant.set_index < len(sets) else '',
        is_entered_result=participant.is_entered_result,
    )


def get_participant_results(event: Event, participant: Participant) -> list:
    """ Сохранённые результаты участника списком по трассам: [{'top': 1, 'zone': 1}, ...].
    Вне французской системы top: 0 — нет, 1 — flash, 2 — redpoint """
    stored = participant.french_accents or {}
    is_french = event.score_type == Event.SCORE_FRENCH
    results = []
    for i in range(event.routes_num):
        accent = stored.get(str(i)) or {}
        top, zone = int(accent.get('top') or 0), int(accent.get('zone') or 0)
        if not is_french:
            top, zone = min(top, 2), 0
        results.append(dict(top=top, zone=zone))
    return results


def _parse_cell(event: Event, raw) -> dict:
    """ Проверяет результат на одной трассе, пришедший от клиента, и приводит его к формату enter_results """
    is_french = event.score_type == Event.SCORE_FRENCH
    max_top = MAX_ATTEMPTS if is_french else 2
    try:
        top, zone = int(raw.get('top') or 0), int(raw.get('zone') or 0)
    except (AttributeError, TypeError, ValueError):
        raise InvalidResultsError('Результаты в неверном формате.')
    if not 0 <= top <= max_top or not 0 <= zone <= MAX_ATTEMPTS:
        raise InvalidResultsError('Номер попытки вне допустимых значений.')
    return form_data_to_results(form_cleaned_data=[dict(top=top, zone=zone if is_french else 0)])[0]


def parse_results(event: Event, raw) -> dict:
    """ Проверяет результаты, пришедшие от клиента списком по трассам, и приводит их к формату enter_results.
    Вне французской системы достаточно top: 0 — нет, 1 — flash, 2 — redpoint """
    if not isinstance(raw, list) or len(raw) != event.routes_num:
        raise InvalidResultsError(f'Ожидались результаты по {event.routes_num} трассам.')
    results = {i: _parse_cell(event=event, raw=item) for i, item in enumerate(raw)}
    check_results(event=event, results=results)
    return results


def find_participant_by_pin(event: Event, pin) -> Participant:
    try:
        pin = int(pin)
    except (TypeError, ValueError):
        raise ParticipantNotFoundError
    participant = event.participant.filter(pin=pin).first() if 0 <= pin <= 32767 else None
    if participant is None:
        raise ParticipantNotFoundError
    return participant


def _ensure_entry_open(event: Event) -> None:
    if not event.is_enter_result_allowed:
        raise EntryClosedError


def _ensure_update_allowed(event: Event, participant: Participant) -> None:
    if participant.is_entered_result and not event.is_update_result_allowed:
        raise ResultsUpdateNotAllowedError


def identify_participant(event: Event, pin) -> Participant:
    """ Участник, который по PIN открывает ввод результатов """
    _ensure_entry_open(event=event)
    participant = find_participant_by_pin(event=event, pin=pin)
    _ensure_update_allowed(event=event, participant=participant)
    return participant


def get_participant_standing(event: Event, participant: Participant) -> dict:
    """ Место участника в своей группе и сколько всего участников в этом зачёте """
    ranked = event.participant.filter(gender=participant.gender)
    if event.is_separate_score_by_groups:
        ranked = ranked.filter(group_index=participant.group_index)
    if event.is_count_only_entered_results:
        ranked = ranked.filter(is_entered_result=True)
    return dict(place=participant.place, of=ranked.count())


def submit_results_by_pin(event: Event, pin, raw_results) -> Participant:
    participant = identify_participant(event=event, pin=pin)
    enter_results(event=event, participant=participant, accents=parse_results(event=event, raw=raw_results))
    participant.refresh_from_db()
    return participant


def submit_results_without_registration(event: Event, cd: dict, raw_results) -> Participant:
    """ Ввод без регистрации: участник находится по имени и фамилии, а если его нет, регистрируется """
    _ensure_entry_open(event=event)
    if not event.is_without_registration:
        raise WithoutRegistrationDisabledError
    results = parse_results(event=event, raw=raw_results)
    participant = event.participant.filter(first_name__iexact=cd['first_name'],
                                           last_name__iexact=cd['last_name']).first()
    if participant:
        _ensure_update_allowed(event=event, participant=participant)
    else:
        if not is_registration_open(event=event):
            raise RegistrationClosedError
        participant = register_participant(event=event, cd=cd)
        if participant is None:
            raise SetFullError
    enter_results(event=event, participant=participant, accents=results)
    participant.refresh_from_db()
    return participant


def get_registration_msg_html(event: Event, participant: Participant, pay_url: str) -> str:
    html = f"<h3>Вы успешно зарегистрированы на \"{event.title}\", {event.date}, скалодром \"{event.gym}\"</h3><br>" \
           f"<p>Ваш PIN-код: <strong>{participant.pin}</strong>. " \
           f"PIN-код понадобится Вам для ввода результатов! Также он будет указан в вашей карточке участника.</p>"
    if event.is_pay_allowed:
        html += f"<p>Для завершения регистрации Вам необходимо оплатить стартовый взнос по ссылке: <a href=\"{pay_url}\">{pay_url}</a>.</p>"
        if event.pay_type == Event.PAY_TYPE_SBP:
            html += f"<p>Внимание! После оплаты вам необходимо связаться с организаторами и сообщить об оплате.</p>"
    return html


def get_registration_email_msg_html(event: Event, participant: Participant, pay_url: str) -> str:
    html = get_registration_msg_html(event=event, participant=participant, pay_url=pay_url)
    html += f"<hr><p style='color:grey'>Это письмо сформировано автоматически, не отвечайте на него. Контакты для связи с организатором ищите на странице описания соревнования.</p>"
    return html


# ================================================
# =============== Get results ====================
# ================================================
def _accent_attempt_to_literal(attempt: str) -> str:
    if attempt == '0':
        return '-'
    if attempt == '1':
        return 'F'
    return 'RP'


def _french_accents_to_string(event: Event, accents: list) -> list:
    if event.score_type == Event.SCORE_FRENCH:
        return [f"{result.get('top', 0)}T {result.get('zone', 0)}z" for result in accents]
    return [_accent_attempt_to_literal(str(result.get('top', '0'))) for result in accents]


def _get_score_view(participant: Participant, score_type) -> str:
    if score_type == Event.SCORE_NUM_ACCENTS:
        return f'{int(participant.score / 100)}/{int(participant.score % 100)}'
    if score_type == Event.SCORE_FRENCH:
        return str(participant.french_score)
    return str(participant.score)


def _get_sorted_participants_results(event: Event, participants: QuerySet, full_results: bool = False) -> list:
    """ Возвращем сортированный список результатов участников из переданного списка """
    data = []
    for participant in participants:
        if (not event.is_count_only_entered_results) or participant.is_entered_result:
            french_accents = participant.french_accents or {}
            accents = [french_accents.get(str(i), {})
                       for i in range(event.routes_num)] if full_results else []
            accents = _french_accents_to_string(event=event, accents=accents)

            counted_routes = [True if i in participant.counted_routes else False for i in range(event.routes_num)]
            data.append(dict(participant=participant,
                             accents=accents,
                             score=participant.score,
                             score_view=_get_score_view(participant=participant, score_type=event.score_type),
                             counted_routes=counted_routes))
    return sorted(data, key=lambda k: (-k['score'], k['participant'].last_name), reverse=False)


def get_results(event: Event, full_results: bool = False) -> dict:
    """ Возвращаем словарь с отсортированным списком участников по полу и группам.
     full_results добавляет информацию о всех прохождениях
    data = {
        'MALE': [
            {
                'name': 'Спорт',
                'data': [{'participant': Participant, 'accents': ['NO', 'FL', 'RP', ...], 'score': 100.0, 'score_view': 100.0, 'counted_routes': [True, False, False, True,]}, 
                        {...}],
                'scores': ['100.00\n80.00', '0 0', ...]
            },
            {...},
        ],
        'FEMALE': [...]
    }
     """

    data = {}

    for gender in (Participant.GENDER_MALE, Participant.GENDER_FEMALE):
        gender_data = []
        for group_index, group in enumerate(get_group_list(event=event)):
            json_key = _get_participant_json_key(gender=gender, group_index=group_index)
            scores = [
                f"{round(get_route_score(route=route, json_key=json_key) * (event.redpoint_points if event.score_type != Event.SCORE_GRADE else 1) * (1 + event.flash_points_pc / 100), 2)}\n"
                f"{round(get_route_score(route=route, json_key=json_key) * (event.redpoint_points if event.score_type != Event.SCORE_GRADE else 1), 2)}"
                for route in event.route.all().order_by('number')] if full_results else []

            gender_data.append(dict(name=group,
                                    data=_get_sorted_participants_results(
                                        event=event,
                                        participants=event.participant.filter(gender=gender,
                                                                              group_index=group_index),
                                        full_results=full_results),
                                    scores=scores))
        data.update({gender: gender_data})
    return data


def is_event_live(event: Event) -> bool:
    """ Событие идёт: ввод результатов открыт и оно не завершено. Пока идёт, результаты меняются """
    return event.is_enter_result_allowed and not event.is_expired


def _get_route_points(event: Event, routes: list, json_key: str) -> list:
    """ Очки за flash и redpoint по каждой трассе для таблицы группы """
    redpoint_k = 1 if event.score_type == Event.SCORE_GRADE else event.redpoint_points
    points = []
    for route in routes:
        base = get_route_score(route=route, json_key=json_key) * redpoint_k
        points.append(dict(flash=round(base * (1 + event.flash_points_pc / 100), 2), redpoint=round(base, 2)))
    return points


def _get_public_result_row(event: Event, participant: Participant, sets: list, grades: dict,
                           is_view_full_results: bool) -> dict:
    """ Строка таблицы результатов. Только то, что видно всем: без PIN, email и телефона """
    entered = participant.is_entered_result
    show_routes = entered and is_view_full_results
    counted = set(participant.counted_routes or [])
    return dict(
        id=participant.id,
        last_name=participant.last_name,
        first_name=participant.first_name,
        gender=participant.gender,
        birth_year=participant.birth_year or None,
        grade=grades.get(participant.grade, ''),
        city=participant.city or '',
        team=participant.team or '',
        set_index=participant.set_index,
        set=sets[participant.set_index] if participant.set_index < len(sets) else '',
        place=participant.place if entered and participant.place > 0 else None,
        score=participant.score,
        score_view=_get_score_view(participant=participant, score_type=event.score_type),
        results=get_participant_results(event=event, participant=participant) if show_routes else [],
        counted=[i in counted for i in range(event.routes_num)] if show_routes else [],
    )


def get_results_payload(event: Event, can_edit: bool = False) -> dict:
    """ Результаты события для экрана и API: по таблице на каждый пол и группу.
    В таблице участники с результатом (ranked, по местам) и без него (waiting, без места).
    {
        'event': {...}, 'display': {...}, 'routes': [...], 'groups': ['Новички', ...],
        'tables': [{'gender': 'MALE', 'group_index': 0, 'group': 'Новички', 'route_points': [...] or None,
                    'ranked': [{...}], 'waiting': [{...}]}, ...]
    }
    """
    routes = list(event.route.all().order_by('number'))
    sets = get_set_list(event=event)
    groups = get_group_list(event=event)
    grades = dict(Participant.GRADES)
    is_view_full_results = event.is_view_full_results
    view_points = (is_view_full_results and event.is_view_route_score
                   and event.score_type not in (Event.SCORE_NUM_ACCENTS, Event.SCORE_FRENCH))
    participants = list(event.participant.all().order_by('last_name', 'first_name'))

    tables = []
    for gender in (Participant.GENDER_MALE, Participant.GENDER_FEMALE):
        for group_index, group in enumerate(groups):
            members = [p for p in participants if p.gender == gender and p.group_index == group_index]
            rows = [_get_public_result_row(event, p, sets, grades, is_view_full_results) for p in members]
            ranked = sorted((row for row in rows if row['place'] is not None),
                            key=lambda row: (-row['score'], row['last_name'], row['first_name']))
            tables.append(dict(
                gender=gender,
                group_index=group_index,
                group=group,
                route_points=_get_route_points(event, routes, _get_participant_json_key(gender, group_index))
                if view_points else None,
                ranked=ranked,
                waiting=[row for row in rows if row['place'] is None],
            ))

    return dict(
        event=dict(
            id=event.id,
            title=event.title,
            date=event.date_display,
            gym=event.gym,
            score_type=event.score_type,
            routes_num=event.routes_num,
            is_live=is_event_live(event=event),
            is_expired=event.is_expired,
            can_edit=can_edit,
        ),
        display=dict(
            is_view_full_results=is_view_full_results,
            best_routes_num=int(event.count_routes_num or 0)
            if event.score_type in (Event.SCORE_PROPORTIONAL, Event.SCORE_GRADE) else 0,
        ),
        routes=[dict(number=route.number,
                     grade=route.grade if event.is_view_route_grade else None,
                     color=route.color if event.is_view_route_color else None) for route in routes],
        groups=groups if event.group_num > 1 else [],
        tables=tables,
    )


# ================================================
# ====== Bulk entry by organizer (matrix) ========
# ================================================

def get_matrix_payload(event: Event) -> dict:
    """ Данные для массового ввода организатором: все участники события с PIN и результатами.
    Только для организатора: PIN и результаты тех, кто ещё не вводил, не для всех """
    participants = event.participant.order_by('last_name', 'first_name')
    return dict(
        event=dict(
            id=event.id,
            title=event.title,
            date=event.date_display,
            score_type=event.score_type,
            routes_num=event.routes_num,
            max_attempts=MAX_ATTEMPTS,
            groups=get_group_list(event=event) if event.group_num > 1 else [],
            sets=[dict(index=i, name=name) for i, name in enumerate(get_set_list(event=event))],
        ),
        participants=[dict(
            id=p.id,
            last_name=p.last_name,
            first_name=p.first_name,
            gender=p.gender,
            pin=p.pin,
            group_index=p.group_index,
            set_index=p.set_index,
            is_entered_result=p.is_entered_result,
            results=get_participant_results(event=event, participant=p),
            score=p.score,
            score_view=_get_score_view(participant=p, score_type=event.score_type),
            place=p.place if p.is_entered_result and p.place > 0 else None,
        ) for p in participants],
    )


def _parse_matrix_changes(event: Event, changes) -> dict:
    """ [{'participant': 5, 'results': {'3': {'top': 2}}}] -> {5: {3: {'top': 2, 'zone': 2}}}, ключи трасс с нуля """
    if not isinstance(changes, list):
        raise InvalidResultsError('Изменения в неверном формате.')
    parsed = {}
    for change in changes:
        if not isinstance(change, dict) or not isinstance(change.get('results'), dict):
            raise InvalidResultsError('Изменения в неверном формате.')
        try:
            participant_id = int(change.get('participant'))
        except (TypeError, ValueError):
            raise InvalidResultsError('Изменения в неверном формате.')
        cells = parsed.setdefault(participant_id, {})
        for key, raw in change['results'].items():
            try:
                index = int(key)
            except (TypeError, ValueError):
                raise InvalidResultsError('Изменения в неверном формате.')
            if not 0 <= index < event.routes_num:
                raise InvalidResultsError(f'В событии нет трассы {index + 1}.', participant_id=participant_id)
            cells[index] = _parse_cell(event=event, raw=raw)
    return parsed


def save_matrix_changes(event: Event, changes) -> dict:
    """ Сохраняет изменённые ячейки матрицы. У участника меняются только переданные трассы, остальное
    (например, то, что он сам ввёл с телефона) остаётся как есть. Участник без результата после этого считается
    внёсшим результат, даже если все изменённые трассы «нет».
    Всё или ничего: при ошибке в любом участнике не записывается ничего. Баллы и места пересчитываются после записи """
    parsed = _parse_matrix_changes(event=event, changes=changes)
    participants = {p.id: p for p in event.participant.filter(id__in=list(parsed))}
    if len(participants) != len(parsed):
        raise ParticipantNotFoundError

    for participant_id, cells in parsed.items():
        # проверяем только то, что меняли: старые некорректные ячейки не должны мешать править остальное
        check_results(event=event, results=cells, participant=participants[participant_id])

    with transaction.atomic():
        groups = set()
        for participant_id, cells in parsed.items():
            participant = participants[participant_id]
            stored = participant.french_accents or {}
            merged = {str(i): stored.get(str(i)) or {'top': 0, 'zone': 0} for i in range(event.routes_num)}
            merged.update({str(i): cell for i, cell in cells.items()})
            participant.french_accents = merged
            participant.is_entered_result = True
            participant.save(update_fields=['french_accents', 'is_entered_result'])
            groups.add((participant.gender, participant.group_index))
        for gender, group_index in sorted(groups):
            _update_results(event=event, gender=gender, group_index=group_index)
    return dict(cells=sum(len(cells) for cells in parsed.values()), participants=len(parsed))


# ================================================
# ============== Excel responses =================
# ================================================


def get_startlist_response(event: Event) -> HttpResponse:
    book = xl_tools.export_participants_to_start_list(event=event)
    response = HttpResponse(content=book,
                            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=startlist.xlsx'
    return response


def get_result_response(event: Event) -> HttpResponse:
    book = xl_tools.export_result(event=event)
    response = HttpResponse(content=book,
                            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=result.xlsx'
    return response


def get_result_example_response(event: Event) -> HttpResponse:
    book = xl_tools.load_template('events/xl_templates/results_example.xlsx')
    content = save_virtual_workbook(book)
    response = HttpResponse(content=content,
                            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=results_example.xlsx'
    return response


# ================================================
# =================== Debug ======================
# ================================================


def _get_random_string(length):
    # Random string with the combination of lower and upper case
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(length))


def _debug_create_random_participant(event: Event) -> Participant:
    gender = random.choice([g[0] for g in Participant.GENDERS])
    return _create_participant(
        event=event,
        first_name=random.choice(
            mock.male_names) if gender == Participant.GENDER_MALE else random.choice(mock.female_names),
        last_name=random.choice(mock.last_names) + ("а" if gender == Participant.GENDER_FEMALE else ""),
        gender=gender,
        birth_year=random.randint(1950, 2020),
        city=random.choice(mock.cities),
        team=f"Команда №{random.randrange(5)}",
        grade=random.choice([g[0] for g in Participant.GRADES]),
        group_index=random.randrange(event.group_num),
        set_index=random.randrange(event.set_num),
        reg_type_index=random.randint(0, event.reg_type_num - 1) if event.reg_type_num > 1 else 0,
    )


def debug_create_participants(event: Event, num: int) -> None:
    for i in range(num):
        _debug_create_random_participant(event=event)


def _debug_get_random_accent() -> Accent:
    top = random.randint(0, 5)
    zone = random.randint(1, top) if top else random.randint(0, 5)
    return Accent(top=top, zone=zone)


def debug_apply_random_results(event: Event) -> None:
    for participant in event.participant.all():
        accents = {i: asdict(_debug_get_random_accent()) for i in range(event.routes_num)}
        enter_results(event=event, participant=participant, accents=accents, force_update_disable=True)
    update_results(event=event)


# ================================================
# =================== Utils ======================
# ================================================


def get_maintenance_context(request):
    return {'code': '', 'msg': 'Сервер на обслуживании'}


# ================================================
# =================== Files ======================
# ================================================


def get_list_of_protocols(event: Event) -> list:
    path = settings.PROTOCOLS_PATH + f'/{event.id}'
    if not os.path.exists(path=path):
        return []
    files = [f for f in os.scandir(path) if not f.is_dir()]
    files.sort(key=os.path.getctime, reverse=True)
    return [{"name": f.name, "size": os.stat(f).st_size, "mtime": datetime.fromtimestamp(os.stat(f).st_mtime)} for f in
            files]


def download_xlsx_response(file: str) -> HttpResponse:
    path = os.path.join(settings.PROTOCOLS_PATH, str(file))
    if os.path.exists(path):
        with open(path, 'rb') as fh:
            response = HttpResponse(content=fh.read(),
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(path)
            return response


def remove_file(file: str) -> bool:
    path = os.path.join(settings.PROTOCOLS_PATH, str(file))
    if os.path.exists(path):
        os.remove(path=path)
        return True
    return False


def get_uploaded_poster_events() -> QuerySet:
    # у событий без своего постера в поле лежит путь к дефолтной картинке из static
    return Event.objects.filter(poster__startswith=f'{settings.MEDIA_POSTERS_DIR}/').order_by('id')


def compress_event_poster(event: Event) -> None:
    old_name = event.poster.name
    with event.poster.open('rb') as f:
        content = img_tools.compress_poster(f)
    event.poster.save(content.name, content, save=False)
    event.save(update_fields=['poster'])
    if not Event.objects.filter(poster=old_name).exists():
        event.poster.storage.delete(old_name)


# ================================================
# ================= QR-codes =====================
# ================================================


def qr_create(text: str, version: int = 4) -> io.BytesIO:
    qr = segno.make_qr(text, version=version)
    out = io.BytesIO()
    qr.save(out=out, kind='png', scale=50)
    return out


def qr_create_response(text: str, title: str = 'qrcode') -> HttpResponse:
    out = qr_create(text=text)
    response = HttpResponse(content=out.getvalue(),
                            content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename={title}.png'
    return response


# ================================================
# ================= PayDetails ===================
# ================================================

def save_pay_detail(event: Event, participant: Participant, promo_code: PromoCode or None, wallet: Wallet,
                    amount: float, operation_id: str) -> PayDetail:
    pd = PayDetail.objects.create(
        event=event,
        participant=participant,
        promo_code=promo_code,
        wallet=wallet,
        amount=amount,
        operation_id=operation_id
    )
    return pd


# ================================================
# ================= Statistics ===================
# ================================================

def get_platform_stats() -> dict:
    CACHE_KEY = 'platform_stats_data'
    stats = cache.get(CACHE_KEY)
    if stats is not None:
        return stats

    total_events = Event.objects.count()
    published_events = Event.objects.filter(is_published=True).count()
    expired_events = Event.objects.filter(is_expired=True).count()

    total_participants = Participant.objects.count()
    male_participants = Participant.objects.filter(gender=Participant.GENDER_MALE).count()
    female_participants = Participant.objects.filter(gender=Participant.GENDER_FEMALE).count()

    total_routes = Route.objects.count()

    cities_qs = Participant.objects.exclude(city__isnull=True).exclude(city__exact='').values('city').distinct()
    total_cities = cities_qs.count()

    gyms_qs = Event.objects.exclude(gym__isnull=True).exclude(gym__exact='').values('gym').distinct()
    total_gyms = gyms_qs.count()

    all_gyms = list(
        Event.objects.exclude(gym__isnull=True).exclude(gym__exact='')
        .values('gym')
        .annotate(count=Count('id'))
        .order_by('-count', 'gym')
    )

    all_cities = list(
        Participant.objects.exclude(city__isnull=True).exclude(city__exact='')
        .values('city')
        .annotate(count=Count('id'))
        .order_by('-count', 'city')
    )

    top_events = list(
        Event.objects.annotate(participants_count=Count('participant'))
        .order_by('-participants_count')
        .values('id', 'title', 'date', 'gym', 'participants_count')[:5]
    )

    stats = {
        'total_events': total_events,
        'published_events': published_events,
        'expired_events': expired_events,
        'total_participants': total_participants,
        'male_participants': male_participants,
        'female_participants': female_participants,
        'total_routes': total_routes,
        'total_cities': total_cities,
        'total_gyms': total_gyms,
        'all_cities': all_cities,
        'all_gyms': all_gyms,
        'top_cities': all_cities[:5],
        'top_gyms': all_gyms[:5],
        'top_events': top_events,
    }

    cache.set(CACHE_KEY, stats, timeout=3600)
    return stats
