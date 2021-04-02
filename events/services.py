import random
import string

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


def clear_participnts(event: Event) -> None:
    event.participant.all().delete()


def clear_event(event: Event) -> None:
    clear_participnts(event=event)
    clear_routes(event=event)


def create_participant_with_default_accents(event: Event, first_name: str, last_name: str,
                                            gender: Participant.gender = Participant.GENDER_MALE,
                                            birth_year: int = 2000, city: str = '', team: str = '',
                                            grade: Participant.GRADES = Participant.GRADE_BR,
                                            group_index: int = 0,
                                            set_index: int = 0,
                                            ) -> Participant:

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


def update_routes_points(event: Event) -> None:
    for route in event.route.all():
        if event.score_type == Event.SCORE_PROPORTIONAL:
            accents_male = len(event.accent.filter(route=route, participant__gender=Participant.GENDER_MALE).exclude(
                accent=Accent.ACCENT_NO))
            accents_female = len(
                event.accent.filter(route=route, participant__gender=Participant.GENDER_FEMALE).exclude(
                    accent=Accent.ACCENT_NO))
            if accents_male != 0:
                route.points_male = round(1 / accents_male, 2)
            if accents_female != 0:
                route.points_female = round(1 / accents_female, 2)
        else:
            route.points_male = 1
            route.points_female = 1
        route.save()


def update_participants_score(event: Event) -> None:
    for participant in event.participant.all():
        participant.score = 0
        score_type = event.score_type
        for index, accent in enumerate(participant.accent.all()):
            accent_points = accent.route.points_male if participant.gender == Participant.GENDER_MALE else accent.route.points_female
            if accent.accent == Accent.ACCENT_FLASH:
                if score_type == Event.SCORE_SIMPLE_SUM:
                    participant.score += event.flash_points
                else:
                    participant.score += event.flash_points * accent_points
            if accent.accent == Accent.ACCENT_REDPOINT:
                if score_type == Event.SCORE_SIMPLE_SUM:
                    participant.score += event.redpoint_points
                else:
                    participant.score += event.redpoint_points * accent_points
        participant.score = round(participant.score, 2)
        participant.save()


def get_sorted_participants_scores_by_gender(event: Event, gender: Participant.GENDERS) -> list:
    sorted_participants = event.participant.filter(gender=gender).order_by('-score')
    sorted_accents = []
    for p in sorted_participants:
        accents = event.accent.filter(participant=p).order_by('route__number')
        sorted_accents.append(accents)

    data = []
    for i, p in enumerate(sorted_participants):
        data.append({'p': p, 'a': sorted_accents[i]})
    return data


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


def debug_create_participants(event: Event, num: int):
    for i in range(num):
        set_index = random.randrange(event.set_num)
        if event.participant.filter(set_index=set_index).count() < event.set_max_participants:
            print(f"in set #{set_index}:{event.participant.filter(set_index=set_index).count()}")
            p = create_participant_with_default_accents(
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
            print(p)