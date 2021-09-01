import random
import string
from typing import List

from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils import timezone

from events import xl_tools
from events.models import Event, Route, Accent, Participant


def get_random_string(length):
    # Random string with the combination of lower and upper case
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(length))


def create_event_routes(event: Event) -> None:
    for i in range(event.routes_num):
        Route.objects.create(
            number=i + 1,
            event=event,
        )


def create_default_accents(event: Event, participant: Participant) -> None:
    for route in event.route.all():
        Accent.objects.create(
            accent=Accent.ACCENT_NO,
            route=route,
            participant=participant,
            event=event,
        )


def create_default_accents_for_all(event: Event) -> None:
    for p in event.participant.all():
        create_default_accents(event=event, participant=p)


def clear_routes(event: Event) -> None:
    event.route.all().delete()


def clear_participants(event: Event) -> None:
    event.participant.all().delete()


def clear_event(event: Event) -> None:
    clear_participants(event=event)
    clear_routes(event=event)


def create_participant(event: Event, first_name: str, last_name: str,
                       gender: Participant.gender = Participant.GENDER_MALE,
                       birth_year: int = 2000, city: str = '', team: str = '',
                       grade: Participant.GRADES = Participant.GRADE_BR,
                       group_index: int = 0,
                       set_index: int = 0,
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
    )
    return participant

# =========== Routes ===========


def get_route_score(route: Route, gender_index: int, group_index: int) -> float:
    return route.score[gender_index][group_index]


def get_route_point(event: Event, route: Route) -> dict:
    points = {'male': 1, 'female': 1}
    if event.score_type == Event.SCORE_PROPORTIONAL:
        accents_male = len(event.accent.filter(route=route, participant__gender=Participant.GENDER_MALE).exclude(
            accent=Accent.ACCENT_NO))
        accents_female = len(
            event.accent.filter(route=route, participant__gender=Participant.GENDER_FEMALE).exclude(
                accent=Accent.ACCENT_NO))
        if accents_male != 0:
            points.update({'male': round(1 / accents_male, 2)})
        if accents_female != 0:
            points.update({'female': round(1 / accents_female, 2)})
    return points


def _calc_route_score(event: Event, routes: List[Route], accents: QuerySet) -> List[float]:
    """ Вычисляем очки каждой трассы """
    score = [1.0] * len(routes)
    if event.score_type == Event.SCORE_PROPORTIONAL:
        for index, route in enumerate(routes):
            accent_num = len(accents.filter(route=route))
            if accent_num != 0:
                score[index] = round(1 / accent_num, 2)
    return score


def update_routes_scores(event: Event) -> None:
    """ Вычисляем очки всех трасс на основе прохождений и сохраняем """
    all_accents = event.accent.all()
    routes = event.route.all()
    is_separate_scores_by_group = event.is_separate_score_by_groups
    for group_index, group in enumerate(get_group_list(event=event)) if is_separate_scores_by_group else [(0, "")]:
        for gender_index, gender in enumerate([Participant.GENDER_MALE, Participant.GENDER_FEMALE]):
            if is_separate_scores_by_group:
                accents = all_accents.filter(participant__gender=gender, participant__group_index=group_index).exclude(
                    accent=Accent.ACCENT_NO)
            else:
                accents = all_accents.filter(participant__gender=gender).exclude(accent=Accent.ACCENT_NO)
            scores = _calc_route_score(event=event, routes=routes, accents=accents)
            _save_routes_score(routes=routes, scores=scores, gender_index=gender_index, group_index=group_index)


def _save_routes_score(routes: List[Route], scores: List[float], gender_index: int, group_index: int) -> None:
    """ Сохраняем очки трасс в route.score """
    for route, score in zip(routes, scores):
        route.score[gender_index][group_index] = score
        route.save()


# =========== Participants ============

def update_participant_score(event: Event, participant: Participant) -> None:
    """ Вычисляем результат учасника, сохраняем его в поле score """
    score = 0
    accents = Accent.objects.filter(participant=participant).exclude(accent=Accent.ACCENT_NO)
    for accent in accents:
        base_points = event.flash_points if accent.accent == Accent.ACCENT_FLASH else event.redpoint_points
        if event.score_type == Event.SCORE_SIMPLE_SUM:
            score += base_points
        else:
            score += accent.route.score[0 if participant.gender == Participant.GENDER_MALE else 1][
                         participant.group_index] * base_points
        score = round(score, 2)
    participant.score = score
    participant.save()


def update_all_participants_score(event: Event) -> None:
    """ Вычисляем и сохраняем результаты всех участников """
    for participant in event.participant.filter(is_entered_result=True):
        update_participant_score(event=event, participant=participant)


def get_participant_score(participant: Participant) -> float:
    return participant.score

# ======================================
# ========== Getting results ===========


def _get_sorted_participants_results(event: Event, participants: QuerySet, full_results: bool = False) -> list:
    """ Возвращем сортированный список результатов участников из переданного списка """
    data = []
    for participant in participants:
        if (not event.is_count_only_entered_results) or participant.is_entered_result:
            accents = Accent.objects.filter(participant=participant).order_by(
                'route__number') if full_results else []
            data.append(dict(participant=participant,
                             accents=accents,
                             score=participant.score))
    return sorted(data, key=lambda k: (-k['score'], k['participant'].last_name), reverse=False)


def get_results(event: Event, full_results: bool = False) -> dict:
    """ Возвращаем словарь с отсортированным списком участников по полу и группам.
     full_results добавляет информацию о всех прохождениях (очень долго)
     """
    male, female = [], []
    routes_score_male, routes_score_female = [], []

    group_list = get_group_list(event=event) if len(get_group_list(event=event)) else ['']

    for group_index, group in enumerate(group_list):
        male.append(dict(name=group,
                         data=_get_sorted_participants_results(
                             event=event,
                             participants=event.participant.filter(gender=Participant.GENDER_MALE,
                                                                   group_index=group_index),
                             full_results=full_results)))
        if full_results:
            routes_score_male.append(dict(group_index=group_index,
                                          scores=[
                                              f"{round(get_route_score(route=route, gender_index=0, group_index=group_index) * event.flash_points, 2)}/"
                                              f"{round(get_route_score(route=route, gender_index=0, group_index=group_index) * event.redpoint_points, 2)}"
                                              for route in event.route.all()]))
    for group_index, group in enumerate(group_list):
        female.append(dict(name=group,
                           data=_get_sorted_participants_results(
                               event=event,
                               participants=event.participant.filter(gender=Participant.GENDER_FEMALE,
                                                                     group_index=group_index),
                               full_results=full_results)))
        if full_results:
            routes_score_female.append(dict(group_index=group_index,
                                            scores=[
                                                f"{round(get_route_score(route=route, gender_index=1, group_index=group_index) * event.flash_points, 2)}/"
                                                f"{round(get_route_score(route=route, gender_index=1, group_index=group_index) * event.redpoint_points, 2)}"
                                                for route in event.route.all()]))
    return {
        'male': male,
        'female': female,
        'routes_score_male': routes_score_male,
        'routes_score_female': routes_score_female,
    }

# ==========================================


def update_last_result_time(event: Event) -> None:
    event.last_calc_results_time = timezone.now()
    event.save()


def get_group_list(event: Event) -> list:
    return [item.strip() for item in event.group_list.split(',')][:event.group_num] if event.group_num > 1 else []


def get_set_list(event: Event) -> list:
    return [item.strip() for item in event.set_list.split(',')][:event.set_num] if event.set_num > 1 else []


def get_set_list_for_registration_available(event: Event) -> list:
    set_list_all = get_set_list(event=event)
    set_list = []
    if event.set_max_participants > 0:
        for i, item in enumerate(set_list_all):
            set_participants_num = event.participant.filter(set_index=i).count()
            if set_participants_num < event.set_max_participants:
                set_list.append(item)
    else:
        set_list = set_list_all
    return set_list


def debug_create_random_participant(event: Event) -> Participant:
    return create_participant(
        event=event,
        first_name=get_random_string(4),
        last_name=get_random_string(6),
        gender=random.choice([g[0] for g in Participant.GENDERS]),
        birth_year=random.randint(1950, 2020),
        city=get_random_string(5),
        team=get_random_string(5),
        grade=random.choice([g[0] for g in Participant.GRADES]),
        group_index=random.randrange(event.group_num),
        set_index=random.randrange(event.set_num),
    )


def debug_create_participants(event: Event, num: int) -> None:
    for i in range(num):
        debug_create_random_participant(event=event)


def check_participants_number_to_close_registration(event: Event) -> None:
    if event.set_max_participants > 0 \
            and event.participant.count() >= event.set_max_participants * event.set_num:
        event.is_registration_open = False
        event.save()


def save_accent(accent: Accent, result: Accent.ACCENT_TYPE, route: Route) -> None:
    accent.accent = result
    accent.route = route
    accent.save()


def get_maintenance_context(request):
    return {'code': '', 'msg': 'Сервер на обслуживании'}


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


def update_participant(event: Event, participant: Participant, cd: dict) -> Participant:
    participant.event = event
    participant.first_name = cd['first_name']
    participant.last_name = cd['last_name']
    participant.gender = cd[Event.FIELD_GENDER] if Event.FIELD_GENDER in cd else Participant.GENDER_MALE
    participant.birth_year = cd[Event.FIELD_BIRTH_YEAR] if Event.FIELD_BIRTH_YEAR in cd else 0
    participant.city = cd[Event.FIELD_CITY] if Event.FIELD_CITY in cd else ''
    participant.team = cd[Event.FIELD_TEAM] if Event.FIELD_TEAM in cd else ''
    participant.grade = cd[Event.FIELD_GRADE] if Event.FIELD_GRADE in cd else Participant.GRADE_BR
    participant.group_index = get_group_list(event=event).index(cd['group_index']) if 'group_index' in cd else 0
    participant.set_index = get_set_list(event=event).index(cd['set_index']) if 'set_index' in cd else 0
    participant.save()
    return participant


def register_participant(event: Event, cd: dict) -> Participant:
    participant = create_participant(
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
    )
    create_default_accents(event=event, participant=participant)
    check_participants_number_to_close_registration(event=event)
    return participant
