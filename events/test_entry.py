import json
import tempfile
from datetime import date
from pathlib import Path

from django.template import Context, Template
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from events import services
from events.exceptions import InvalidResultsError
from events.models import Event, Participant
from events.tests import ClimbingEventsBaseTestCase

PIN = 1234


class EntryTestBase(ClimbingEventsBaseTestCase):
    """Общая подготовка: опубликованное событие с открытым вводом и один зарегистрированный участник."""

    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.superuser, title='Entry Event', date=date(2026, 10, 1))
        self.event.is_published = True
        self.event.is_enter_result_allowed = True
        self.event.is_registration_open = True
        self.event.is_results_allowed = True
        self.event.save()
        self.participant = self.make_participant()

    def make_participant(self, **kwargs):
        fields = dict(first_name='Иван', last_name='Иванов', gender=Participant.GENDER_MALE, event=self.event,
                      pin=PIN, email='ivan@example.com', phone_number='+79990001122')
        fields.update(kwargs)
        return Participant.objects.create(**fields)

    def set_event(self, **fields):
        for name, value in fields.items():
            setattr(self.event, name, value)
        self.event.save()

    def url(self, name):
        return reverse(f'api_events-entry-{name}', args=[self.event.id])

    def post(self, name, data):
        return self.client.post(self.url(name), data=data, content_type='application/json')

    def results(self, **marked):
        """Список результатов по всем трассам, отмеченные трассы (с единицы) задаются как r3=2 -> {'top': 2}."""
        items = [{'top': 0} for _ in range(self.event.routes_num)]
        for key, value in marked.items():
            items[int(key[1:]) - 1] = value if isinstance(value, dict) else {'top': value}
        return items


class CheckResultsTests(EntryTestBase):
    def test_french_zone_later_than_top_is_rejected(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        with self.assertRaises(InvalidResultsError) as ctx:
            services.enter_results(event=self.event, participant=self.participant,
                                   accents={'0': {'top': 2, 'zone': 3}, '1': {'top': 1, 'zone': 1},
                                            '4': {'top': 1, 'zone': 5}})
        self.assertEqual(ctx.exception.routes, [1, 5])
        self.participant.refresh_from_db()
        self.assertFalse(self.participant.is_entered_result)

    def test_french_zone_without_top_and_zone_equal_to_top_are_fine(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        services.enter_results(event=self.event, participant=self.participant,
                               accents={'0': {'top': 0, 'zone': 4}, '1': {'top': 3, 'zone': 3},
                                        '2': {'top': 3, 'zone': 1}})
        self.participant.refresh_from_db()
        self.assertTrue(self.participant.is_entered_result)

    def test_other_score_types_are_not_checked(self):
        services.enter_results(event=self.event, participant=self.participant, accents={'0': {'top': 1, 'zone': 9}})
        self.participant.refresh_from_db()
        self.assertTrue(self.participant.is_entered_result)


class OldEditLinkTests(EntryTestBase):
    """Старая страница правки результатов участника заменена матрицей: закладки не должны ломаться."""

    def test_old_link_opens_the_matrix_on_that_participant(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('participant_routes', args=[self.event.id, self.participant.id]))
        self.assertRedirects(response, f"{reverse('matrix', args=[self.event.id])}#p={self.participant.id}",
                             fetch_redirect_response=False)

    def test_old_link_is_still_for_the_organizer_only(self):
        self.client.logout()
        response = self.client.get(reverse('participant_routes', args=[self.event.id, self.participant.id]))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('matrix', response['Location'])


class ParseResultsTests(EntryTestBase):
    def test_route_count_must_match(self):
        for raw in ([], [{'top': 1}] * 3, None, 'text', {'0': {'top': 1}}):
            with self.assertRaises(InvalidResultsError, msg=raw):
                services.parse_results(self.event, raw)

    def test_prop_accepts_top_only_and_fills_zone(self):
        parsed = services.parse_results(self.event, self.results(r1=1, r2=2))
        self.assertEqual(parsed[0], {'top': 1, 'zone': 1})
        self.assertEqual(parsed[1], {'top': 2, 'zone': 2})
        self.assertEqual(parsed[2], {'top': 0, 'zone': 0})

    def test_prop_ignores_zone_and_rejects_unknown_top(self):
        parsed = services.parse_results(self.event, self.results(r1={'top': 0, 'zone': 7}))
        self.assertEqual(parsed[0], {'top': 0, 'zone': 0})
        with self.assertRaises(InvalidResultsError):
            services.parse_results(self.event, self.results(r1=3))

    def test_french_fills_zone_when_only_top_given(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        parsed = services.parse_results(self.event, self.results(r1={'top': 3}, r2={'top': 0, 'zone': 2}))
        self.assertEqual(parsed[0], {'top': 3, 'zone': 3})
        self.assertEqual(parsed[1], {'top': 0, 'zone': 2})

    def test_french_rejects_zone_later_than_top_and_huge_attempts(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        with self.assertRaises(InvalidResultsError) as ctx:
            services.parse_results(self.event, self.results(r2={'top': 1, 'zone': 2}))
        self.assertEqual(ctx.exception.routes, [2])
        with self.assertRaises(InvalidResultsError):
            services.parse_results(self.event, self.results(r1={'top': services.MAX_ATTEMPTS + 1}))

    def test_garbage_items_are_rejected(self):
        for item in ('x', 5, None, {'top': 'abc'}, {'top': -1}, {'top': [1]}):
            raw = self.results()
            raw[0] = item
            with self.assertRaises(InvalidResultsError, msg=item):
                services.parse_results(self.event, raw)


class ParticipantResultsTests(EntryTestBase):
    def test_empty_results_for_every_route(self):
        results = services.get_participant_results(self.event, self.participant)
        self.assertEqual(results, [{'top': 0, 'zone': 0}] * self.event.routes_num)

    def test_prop_results_are_normalized_to_no_flash_redpoint(self):
        services.enter_results(event=self.event, participant=self.participant,
                               accents={'0': {'top': 1, 'zone': 1}, '1': {'top': 4, 'zone': 4}})
        self.participant.refresh_from_db()
        results = services.get_participant_results(self.event, self.participant)
        self.assertEqual(results[0], {'top': 1, 'zone': 0})
        self.assertEqual(results[1], {'top': 2, 'zone': 0})

    def test_french_results_keep_attempts(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        services.enter_results(event=self.event, participant=self.participant,
                               accents={'0': {'top': 4, 'zone': 2}})
        self.participant.refresh_from_db()
        self.assertEqual(services.get_participant_results(self.event, self.participant)[0], {'top': 4, 'zone': 2})


class EntryConfigApiTests(EntryTestBase):
    def test_config_for_anonymous(self):
        self.set_event(group_num=2, group_list='Новички, Спорт', set_num=2, set_list='Утро, Вечер',
                       is_check_result_before_enter=True)
        data = self.client.get(self.url('config')).json()
        self.assertEqual(data['id'], self.event.id)
        self.assertEqual(data['routes_num'], 10)
        self.assertEqual(data['score_type'], Event.SCORE_SIMPLE_SUM)
        self.assertEqual(data['groups'], ['Новички', 'Спорт'])
        self.assertEqual(data['sets'], [{'index': 0, 'name': 'Утро', 'is_full': False},
                                        {'index': 1, 'name': 'Вечер', 'is_full': False}])
        self.assertEqual(data['grades'][0], {'value': 'BR', 'label': 'б/р'})
        self.assertTrue(data['is_enter_result_allowed'])
        self.assertTrue(data['is_check_result_before_enter'])
        self.assertFalse(data['is_without_registration'])

    def test_single_group_and_set_are_not_listed(self):
        data = self.client.get(self.url('config')).json()
        self.assertEqual(data['groups'], [])
        self.assertEqual(data['sets'], [])

    def test_full_set_is_marked(self):
        self.set_event(set_num=2, set_list='Утро, Вечер', set_max_participants=1)
        data = self.client.get(self.url('config')).json()
        self.assertEqual([s['is_full'] for s in data['sets']], [True, False])

    def test_unpublished_event_is_hidden_from_anonymous(self):
        self.set_event(is_published=False)
        self.assertEqual(self.client.get(self.url('config')).status_code, 404)
        self.assertEqual(self.post('identify', {'pin': PIN}).status_code, 404)

    def test_unpublished_event_is_available_to_owner(self):
        self.set_event(is_published=False)
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(self.url('config')).status_code, 200)


class IdentifyApiTests(EntryTestBase):
    def test_found_by_pin(self):
        self.set_event(group_num=2, group_list='Новички, Спорт')
        self.participant.group_index = 1
        self.participant.save()
        response = self.post('identify', {'pin': PIN})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['participant']['last_name'], 'Иванов')
        self.assertEqual(data['participant']['group'], 'Спорт')
        self.assertFalse(data['participant']['is_entered_result'])
        self.assertEqual(len(data['results']), self.event.routes_num)

    def test_pin_may_be_a_string(self):
        self.assertEqual(self.post('identify', {'pin': str(PIN)}).status_code, 200)

    def test_private_data_is_not_exposed(self):
        body = self.post('identify', {'pin': PIN}).content.decode()
        for private in ('ivan@example.com', '+79990001122', '"pin"', 'email', 'phone'):
            self.assertNotIn(private, body)

    def test_unknown_or_broken_pin(self):
        for pin in (1111, 'abc', '', None, 99999999999, -5):
            response = self.post('identify', {'pin': pin})
            self.assertEqual(response.status_code, 404, pin)
            self.assertEqual(response.json()['code'], 'pin_not_found')

    def test_pin_of_another_event_is_not_found(self):
        other = services.create_event(owner=self.superuser, title='Other', date=date(2026, 10, 2))
        other.is_published = True
        other.is_enter_result_allowed = True
        other.save()
        response = self.client.post(reverse('api_events-entry-identify', args=[other.id]), {'pin': PIN},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_entry_closed(self):
        self.set_event(is_enter_result_allowed=False)
        response = self.post('identify', {'pin': PIN})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'entry_closed')

    def test_not_locked_by_default(self):
        data = self.post('identify', {'pin': PIN}).json()
        self.assertFalse(data['locked'])
        self.assertNotIn('standing', data)

    def test_update_not_allowed_locks_only_after_first_entry(self):
        """Повторный ввод запрещён: после первого ввода PIN открывает не ошибку, а результаты только для просмотра"""
        self.set_event(is_update_result_allowed=False)
        self.assertFalse(self.post('identify', {'pin': PIN}).json()['locked'])
        services.enter_results(event=self.event, participant=self.participant, accents={'0': {'top': 1, 'zone': 1}})
        response = self.post('identify', {'pin': PIN})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['locked'])
        self.assertEqual(data['standing'], {'place': 1, 'of': 1})
        self.assertEqual(data['results'][0]['top'], 1)

    def test_locked_screen_has_no_place_while_results_are_hidden(self):
        self.set_event(is_update_result_allowed=False, is_results_allowed=False)
        services.enter_results(event=self.event, participant=self.participant, accents={'0': {'top': 1, 'zone': 1}})
        data = self.post('identify', {'pin': PIN}).json()
        self.assertTrue(data['locked'])
        self.assertIsNone(data['standing'])

    def test_entered_participant_may_edit_when_updates_are_allowed(self):
        services.enter_results(event=self.event, participant=self.participant, accents={'0': {'top': 1, 'zone': 1}})
        self.assertFalse(self.post('identify', {'pin': PIN}).json()['locked'])

    def test_returns_saved_results(self):
        services.enter_results(event=self.event, participant=self.participant,
                               accents={'0': {'top': 1, 'zone': 1}, '2': {'top': 2, 'zone': 2}})
        data = self.post('identify', {'pin': PIN}).json()
        self.assertTrue(data['participant']['is_entered_result'])
        self.assertEqual([r['top'] for r in data['results'][:3]], [1, 0, 2])


class SubmitApiTests(EntryTestBase):
    def test_submit_saves_results_and_returns_standing(self):
        response = self.post('submit', {'pin': PIN, 'results': self.results(r1=1, r2=2)})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['standing'], {'place': 1, 'of': 1})
        self.assertEqual([r['top'] for r in data['results'][:3]], [1, 2, 0])
        self.participant.refresh_from_db()
        self.assertTrue(self.participant.is_entered_result)
        self.assertEqual(self.participant.french_accents['0'], {'top': 1, 'zone': 1})
        self.assertGreater(self.participant.score, 0)

    def test_standing_counts_only_own_group_and_gender(self):
        self.set_event(group_num=2, group_list='Новички, Спорт')
        stronger = self.make_participant(first_name='Пётр', last_name='Петров', pin=2222)
        other_group = self.make_participant(first_name='Анна', last_name='Антонова', pin=3333, group_index=1,
                                            gender=Participant.GENDER_FEMALE)
        services.enter_results(event=self.event, participant=stronger,
                               accents={str(i): {'top': 1, 'zone': 1} for i in range(10)})
        services.enter_results(event=self.event, participant=other_group, accents={'0': {'top': 1, 'zone': 1}})
        data = self.post('submit', {'pin': PIN, 'results': self.results(r1=2)}).json()
        self.assertEqual(data['standing'], {'place': 2, 'of': 2})

    def test_resubmit_overwrites_results(self):
        self.post('submit', {'pin': PIN, 'results': self.results(r1=1)})
        self.post('submit', {'pin': PIN, 'results': self.results(r2=2)})
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.french_accents['0'], {'top': 0, 'zone': 0})
        self.assertEqual(self.participant.french_accents['1'], {'top': 2, 'zone': 2})

    def test_all_zeros_is_a_result(self):
        self.assertEqual(self.post('submit', {'pin': PIN, 'results': self.results()}).status_code, 200)
        self.participant.refresh_from_db()
        self.assertTrue(self.participant.is_entered_result)

    def test_french_zone_later_than_top_is_rejected(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        response = self.post('submit', {'pin': PIN, 'results': self.results(r3={'top': 1, 'zone': 4})})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_results')
        self.assertEqual(response.json()['routes'], [3])
        self.participant.refresh_from_db()
        self.assertFalse(self.participant.is_entered_result)

    def test_french_results_saved(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        response = self.post('submit', {'pin': PIN, 'results': self.results(r1={'top': 3, 'zone': 2})})
        self.assertEqual(response.status_code, 200)
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.french_accents['0'], {'top': 3, 'zone': 2})

    def test_wrong_route_count_is_rejected(self):
        response = self.post('submit', {'pin': PIN, 'results': [{'top': 1}]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_results')

    def test_missing_results_are_rejected(self):
        self.assertEqual(self.post('submit', {'pin': PIN}).status_code, 400)

    def test_wrong_pin_and_closed_entry(self):
        self.assertEqual(self.post('submit', {'pin': 1111, 'results': self.results()}).status_code, 404)
        self.set_event(is_enter_result_allowed=False)
        self.assertEqual(self.post('submit', {'pin': PIN, 'results': self.results()}).status_code, 403)
        self.participant.refresh_from_db()
        self.assertFalse(self.participant.is_entered_result)

    def test_hidden_results_mean_no_place_in_the_answer(self):
        self.set_event(is_results_allowed=False)
        data = self.post('submit', {'pin': PIN, 'results': self.results(r1=1)}).json()
        self.assertIsNone(data['standing'])

    def test_answer_has_the_participant_id(self):
        data = self.post('submit', {'pin': PIN, 'results': self.results(r1=1)}).json()
        self.assertEqual(data['participant']['id'], self.participant.id)

    def test_update_not_allowed(self):
        self.set_event(is_update_result_allowed=False)
        self.assertEqual(self.post('submit', {'pin': PIN, 'results': self.results(r1=1)}).status_code, 200)
        response = self.post('submit', {'pin': PIN, 'results': self.results(r1=2)})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'update_not_allowed')
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.french_accents['0'], {'top': 1, 'zone': 1})


class SubmitWithoutRegistrationApiTests(EntryTestBase):
    def setUp(self):
        super().setUp()
        self.set_event(is_without_registration=True, registration_fields=['gender'])

    def body(self, **fields):
        data = dict(first_name='Мария', last_name='Маркова', gender=Participant.GENDER_FEMALE,
                    results=self.results(r1=1, r2=2))
        data.update(fields)
        return data

    def test_new_participant_is_registered_with_results(self):
        response = self.post('submit-without-registration', self.body())
        self.assertEqual(response.status_code, 200)
        participant = Participant.objects.get(event=self.event, last_name='Маркова')
        self.assertEqual(participant.gender, Participant.GENDER_FEMALE)
        self.assertTrue(participant.is_entered_result)
        self.assertEqual(participant.french_accents['1'], {'top': 2, 'zone': 2})
        self.assertIsNotNone(participant.pin)
        self.assertEqual(response.json()['standing'], {'place': 1, 'of': 1})
        self.assertNotIn('"pin"', response.content.decode())

    def test_same_name_updates_existing_participant(self):
        self.post('submit-without-registration', self.body())
        response = self.post('submit-without-registration',
                             self.body(first_name=' мария ', last_name='МАРКОВА', results=self.results(r3=2)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Participant.objects.filter(event=self.event, last_name__iexact='маркова').count(), 1)
        participant = Participant.objects.get(event=self.event, last_name='Маркова')
        self.assertEqual(participant.french_accents['0'], {'top': 0, 'zone': 0})
        self.assertEqual(participant.french_accents['2'], {'top': 2, 'zone': 2})

    def test_existing_participant_registered_earlier_can_enter(self):
        response = self.post('submit-without-registration', self.body(first_name='Иван', last_name='Иванов'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Participant.objects.filter(event=self.event).count(), 1)

    def test_update_not_allowed_for_entered_participant(self):
        self.set_event(is_update_result_allowed=False)
        self.assertEqual(self.post('submit-without-registration', self.body()).status_code, 200)
        response = self.post('submit-without-registration', self.body(results=self.results(r5=2)))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'update_not_allowed')

    def test_disabled_for_event_with_registration(self):
        self.set_event(is_without_registration=False)
        response = self.post('submit-without-registration', self.body())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'without_registration_disabled')
        self.assertFalse(Participant.objects.filter(last_name='Маркова').exists())

    def test_entry_closed(self):
        self.set_event(is_enter_result_allowed=False)
        self.assertEqual(self.post('submit-without-registration', self.body()).status_code, 403)

    def test_registration_closed_blocks_only_new_participants(self):
        self.set_event(is_registration_open=False)
        response = self.post('submit-without-registration', self.body())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'registration_closed')
        response = self.post('submit-without-registration', self.body(first_name='Иван', last_name='Иванов'))
        self.assertEqual(response.status_code, 200)

    def test_names_are_required(self):
        for field in ('first_name', 'last_name'):
            data = self.body()
            del data[field]
            response = self.post('submit-without-registration', data)
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.json()['fields'])
        response = self.post('submit-without-registration', self.body(first_name='   '))
        self.assertEqual(response.status_code, 400)

    def test_gender_is_required_when_event_asks_for_it(self):
        data = self.body()
        del data['gender']
        response = self.post('submit-without-registration', data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('gender', response.json()['fields'])
        self.assertEqual(self.post('submit-without-registration', self.body(gender='X')).status_code, 400)

    def test_required_registration_fields(self):
        self.set_event(registration_fields=['gender', 'birth_year', 'city'], required_fields=['birth_year'])
        response = self.post('submit-without-registration', self.body())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(response.json()['fields']), ['birth_year'])
        response = self.post('submit-without-registration', self.body(birth_year=1990, city='Тула'))
        self.assertEqual(response.status_code, 200)
        participant = Participant.objects.get(last_name='Маркова')
        self.assertEqual((participant.birth_year, participant.city), (1990, 'Тула'))

    def test_fields_the_event_does_not_ask_for_are_ignored(self):
        self.assertEqual(self.post('submit-without-registration', self.body(city='Тула', email='x@y.ru')).status_code,
                         200)
        participant = Participant.objects.get(last_name='Маркова')
        self.assertFalse(participant.city)
        self.assertFalse(participant.email)

    def test_too_young(self):
        self.set_event(registration_fields=['gender', 'birth_year'], participant_min_age=18)
        response = self.post('submit-without-registration', self.body(birth_year=date.today().year - 10))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'too_young')
        self.assertFalse(Participant.objects.filter(last_name='Маркова').exists())

    def test_email_and_phone_are_validated_and_normalized(self):
        self.set_event(registration_fields=['gender', 'email', 'phone_number'],
                       required_fields=['email', 'phone_number'])
        response = self.post('submit-without-registration', self.body(email='not-an-email', phone_number='123'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(sorted(response.json()['fields']), ['email', 'phone_number'])
        response = self.post('submit-without-registration', self.body(email='m@example.com',
                                                                      phone_number='8 (999) 123-45-67'))
        self.assertEqual(response.status_code, 200)
        participant = Participant.objects.get(last_name='Маркова')
        self.assertEqual(participant.email, 'm@example.com')
        self.assertEqual(str(participant.phone_number), '+79991234567')

    def test_group_and_set_are_chosen_by_index(self):
        self.set_event(group_num=2, group_list='Новички, Спорт', set_num=2, set_list='Утро, Вечер')
        response = self.post('submit-without-registration', self.body())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(sorted(response.json()['fields']), ['group_index', 'set_index'])
        response = self.post('submit-without-registration', self.body(group_index=2, set_index=0))
        self.assertEqual(response.status_code, 400)
        response = self.post('submit-without-registration', self.body(group_index=1, set_index=1))
        self.assertEqual(response.status_code, 200)
        participant = Participant.objects.get(last_name='Маркова')
        self.assertEqual((participant.group_index, participant.set_index), (1, 1))
        self.assertEqual(response.json()['participant']['group'], 'Спорт')
        self.assertEqual(response.json()['participant']['set'], 'Вечер')

    def test_full_set(self):
        self.set_event(set_num=2, set_list='Утро, Вечер', set_max_participants=1)
        response = self.post('submit-without-registration', self.body(set_index=0))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'set_full')
        self.assertFalse(Participant.objects.filter(last_name='Маркова').exists())
        self.assertEqual(self.post('submit-without-registration', self.body(set_index=1)).status_code, 200)

    def test_invalid_results_do_not_register_anyone(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        response = self.post('submit-without-registration',
                             self.body(results=self.results(r1={'top': 1, 'zone': 3})))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_results')
        self.assertFalse(Participant.objects.filter(last_name='Маркова').exists())


class ViteTagTests(SimpleTestCase):
    def render(self, **settings_override):
        with override_settings(**settings_override):
            return Template("{% load vite %}{% vite_entry 'src/entries/entry.ts' %}").render(Context())

    def test_dev_server(self):
        html = self.render(VITE_DEV_SERVER='http://localhost:5173/')
        base = 'http://localhost:5173/static/events/vue'
        self.assertIn(f'<script type="module" src="{base}/@vite/client"></script>', html)
        self.assertIn(f'<script type="module" src="{base}/src/entries/entry.ts"></script>', html)

    def test_manifest_with_shared_chunk_and_css(self):
        manifest = {
            'src/entries/entry.ts': {'file': 'assets/entry-aaa.js', 'isEntry': True, 'css': ['assets/entry-aaa.css'],
                                     'imports': ['_vendor-bbb.js']},
            '_vendor-bbb.js': {'file': 'assets/vendor-bbb.js', 'css': ['assets/vendor-bbb.css']},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            html = self.render(VITE_DEV_SERVER='', VITE_MANIFEST=path, DEBUG=True)
        self.assertIn('<link rel="stylesheet" href="/static/events/vue/assets/entry-aaa.css">', html)
        self.assertIn('<link rel="stylesheet" href="/static/events/vue/assets/vendor-bbb.css">', html)
        self.assertIn('<link rel="modulepreload" href="/static/events/vue/assets/vendor-bbb.js">', html)
        self.assertIn('<script type="module" src="/static/events/vue/assets/entry-aaa.js"></script>', html)

    def test_missing_build_renders_nothing_in_production_and_fails_in_debug(self):
        missing = Path(tempfile.gettempdir()) / 'no-such-dir' / 'manifest.json'
        with self.assertLogs('EventLogger', level='ERROR'):
            self.assertEqual(self.render(VITE_DEV_SERVER='', VITE_MANIFEST=missing, DEBUG=False), '')
        with self.assertLogs('EventLogger', level='ERROR'), self.assertRaises(OSError):
            self.render(VITE_DEV_SERVER='', VITE_MANIFEST=missing, DEBUG=True)
