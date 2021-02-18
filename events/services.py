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


def clear_event(event: Event) -> None:
    event.participant.all().delete()
    event.route.all().delete()


def create_participant_with_default_accents(event: Event, first_name: str, last_name: str,
                                            gender: Participant.gender = Participant.GENDER_MALE,
                                            birth_year: int = 2000, city: str = '', team: str = '',
                                            grade: Participant.GRADES = Participant.GRADE_BR,
                                            ) -> Participant:
    participant = Participant.objects.create(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        birth_year=birth_year,
        city=city,
        team=team,
        grade=grade,
        event=event,
        pin=random.randint(1000, 9999),
    )

    create_default_accents(event=event, participant=participant)

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
