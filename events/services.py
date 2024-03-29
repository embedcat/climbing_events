from dataclasses import asdict, dataclass
import io
import operator
import os
import random
import string
from datetime import datetime
from typing import Iterable
import dacite
from openpyxl import load_workbook
from openpyxl.writer.excel import save_virtual_workbook

import segno
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.http import HttpResponse

from config import settings
from events import xl_tools, mock
from events.exceptions import DuplicateParticipantError, ParticipantTooYoungError
from events.models import ACCENT_REDPOINT, CustomUser, Event, PayDetail, PromoCode, Route, Participant, Wallet
from events.models import ACCENT_NO, ACCENT_FLASH


def create_event(owner: get_user_model(), title: str, date: datetime) -> Event:
    superuser = CustomUser.objects.get(id=1)
    event = Event.objects.create(
        owner=owner,
        title=title,
        date=date,
        premium_price=superuser.premium_price,
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
    old_routes_num = event.routes_num
    need_update_results = event.score_type != cd['score_type'] or \
        event.redpoint_points != cd['redpoint_points'] or \
        event.flash_points_pc != cd['flash_points_pc'] or \
        event.count_routes_num != cd['count_routes_num']

    event.routes_num = cd['routes_num']
    event.is_published = cd['is_published']
    event.is_registration_open = cd['is_registration_open']
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


def check_expired_events(events: QuerySet) -> None:
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
    registration_fields = event.registration_fields
    if event.participant_min_age:
        registration_fields.append(Event.FIELD_BIRTH_YEAR)
    if Event.FIELD_EMAIL not in registration_fields and event.is_pay_allowed:
        registration_fields.append(Event.FIELD_EMAIL)
    return registration_fields


def get_registration_required_fields(event: Event) -> list:
    required_fields = event.required_fields
    if event.participant_min_age:
        required_fields.append(Event.FIELD_BIRTH_YEAR)
    if Event.FIELD_EMAIL not in required_fields and event.is_pay_allowed:
        required_fields.append(Event.FIELD_EMAIL)
    return required_fields


def update_participant(event: Event, participant: Participant, cd: dict) -> Participant:
    current_group_index = participant.group_index
    new_group_index = get_group_list(event=event).index(cd['group_index']) if 'group_index' in cd else 0
    need_update_results = 'group_index' in cd and current_group_index != new_group_index

    participant.event = event
    participant.first_name = cd['first_name']
    participant.last_name = cd['last_name']
    participant.gender = cd[Event.FIELD_GENDER] if Event.FIELD_GENDER in cd else Participant.GENDER_MALE
    participant.birth_year = cd[Event.FIELD_BIRTH_YEAR] if Event.FIELD_BIRTH_YEAR in cd else 0
    participant.city = cd[Event.FIELD_CITY] if Event.FIELD_CITY in cd else ''
    participant.team = cd[Event.FIELD_TEAM] if Event.FIELD_TEAM in cd else ''
    participant.grade = cd[Event.FIELD_GRADE] if Event.FIELD_GRADE in cd else Participant.GRADE_BR
    participant.group_index = new_group_index
    participant.set_index = get_set_list(event=event).index(cd['set_index']) if 'set_index' in cd else 0
    participant.paid = cd['paid'] if 'paid' in cd else False
    participant.email = cd['email'] if 'email' in cd else ''
    participant.reg_type_index = cd['reg_type_index'] if 'reg_type_index' in cd else 0
    participant.phone_number = cd['phone_number'] if 'phone_number' in cd else ''
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
    if event.participant.filter(first_name=cd['first_name'], last_name=cd['last_name']):
        raise DuplicateParticipantError
    if event.participant_min_age and datetime.today().year - cd[Event.FIELD_BIRTH_YEAR] < event.participant_min_age:
        raise ParticipantTooYoungError(event.participant_min_age)
    participant = _create_participant(
        event=event,
        first_name=cd['first_name'],
        last_name=cd['last_name'],
        gender=cd[Event.FIELD_GENDER] if Event.FIELD_GENDER in cd else Participant.GENDER_MALE,
        birth_year=cd[Event.FIELD_BIRTH_YEAR] if Event.FIELD_BIRTH_YEAR in cd else 0,
        city=cd[Event.FIELD_CITY] if Event.FIELD_CITY in cd else '',
        team=cd[Event.FIELD_TEAM] if Event.FIELD_TEAM in cd else '',
        grade=cd[Event.FIELD_GRADE] if Event.FIELD_GRADE in cd else Participant.GRADE_BR,
        group_index=get_group_list(event=event).index(cd['group_index']) if 'group_index' in cd else 0,
        set_index=get_set_list(event=event).index(cd['set_index']) if 'set_index' in cd else 0,
        email=cd[Event.FIELD_EMAIL] if Event.FIELD_EMAIL in cd else '',
        reg_type_index=cd['reg_type_index'] if 'reg_type_index' in cd else 0,
        phone_number = cd['phone_number'] if 'phone_number' in cd else '',
    )
    _check_participants_number_to_close_registration(event=event)
    return participant


def _clear_participant_score(participant: Participant) -> None:
    participant.score = 0
    participant.accents = {}
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
        accent = Accent(top=int(result.get('top', 0)), zone=int(result.get('zone', 0)))
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

    # update participant place:
    participants = sorted(participants, key=operator.attrgetter("score"), reverse=True)
    for index, p in enumerate(participants):
        p.place = index + 1
        if index != 0 and participants[index - 1].score == p.score:
            p.place = participants[index - 1].place
        p.save()


def get_form_initial_results(event: Event, participant: Participant) -> list:
    initial = []
    if event.score_type == Event.SCORE_FRENCH:
        for i in range(event.routes_num):
            result = participant.french_accents.get(str(i), {'top': 0, 'zone': 0})
            initial.append({'top': str(result.get('top', 0)), 'zone': str(result.get('zone', 0))})
    else:
        if participant.french_accents:
            for i in range(event.routes_num):
                result = participant.french_accents.get(str(i), {'top': 0}).get('top', 0)
                accent = ACCENT_NO if result == 0 else (ACCENT_FLASH if result == 1 else ACCENT_REDPOINT)
                initial.append({'top': accent,})
        else:
            initial = [{'label': i, 'accent': participant.accents.get(
                str(i), ACCENT_NO)} for i in range(event.routes_num)]
    return initial


def update_results(event: Event):
    for gender in (Participant.GENDER_MALE, Participant.GENDER_FEMALE):
        for group_index, _ in enumerate(get_group_list(event=event)):
            _update_results(event=event, gender=gender, group_index=group_index)


def enter_results(event: Event, participant: Participant, accents: dict, force_update_disable: bool = False):
    # save participant accents:
    participant.french_accents = accents
    participant.is_entered_result = True
    participant.save()

    if not force_update_disable:
        _update_results(event=event, gender=participant.gender, group_index=participant.group_index)


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


def _accents_to_string(event: Event, accents: list) -> list:
    return [_accent_attempt_to_literal(attempt) for attempt in accents]


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
            accents = []
            if participant.french_accents:
                accents = [participant.french_accents.get(str(i), {})
                           for i in range(event.routes_num)] if full_results else []
                accents = _french_accents_to_string(event=event, accents=accents)
            else:
                accents = [participant.accents.get(str(i), ACCENT_NO)
                           for i in range(event.routes_num)] if full_results else []
                accents = _accents_to_string(event=event, accents=accents)

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
    book = load_workbook(filename='static/events/xl_templates/results_example.xlsx')
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
