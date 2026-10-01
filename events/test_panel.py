from datetime import date

from django.urls import reverse

from events import services
from events.models import Event, Participant, Wallet
from events.tests import ClimbingEventsBaseTestCase


class PanelApiBase(ClimbingEventsBaseTestCase):
    """Событие обычного организатора (user), суперпользователь — admin"""

    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.user, title='Осенний фестиваль', date=date(2026, 10, 4))
        self.client.force_login(self.user)

    def url(self, name='panel'):
        return reverse(f'api_events-{name.replace("/", "-")}', args=[self.event.id])

    def overview(self):
        response = self.client.get(self.url('panel'))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def set_flags(self, flags):
        return self.client.post(self.url('panel-flags'), data=flags, content_type='application/json')

    def act(self, action):
        return self.client.post(self.url('panel-actions'), data={'action': action}, content_type='application/json')

    def person(self, **fields):
        data = dict(first_name='Иван', last_name='Иванов', gender=Participant.GENDER_MALE, event=self.event,
                    pin=1000 + Participant.objects.count())
        data.update(fields)
        return Participant.objects.create(**data)


class OverviewTests(PanelApiBase):
    def test_payload_has_flags_counts_and_stage(self):
        self.person(is_entered_result=True, paid=True)
        self.person()
        data = self.overview()
        self.assertEqual(data['id'], self.event.id)
        self.assertEqual(data['stage'], 'draft')
        self.assertEqual(data['flags'], {
            'is_published': False, 'is_registration_open': False, 'is_enter_result_allowed': False,
            'is_results_allowed': False,
        })
        self.assertEqual((data['participants_count'], data['entered_count'], data['paid_count']), (2, 1, 1))

    def test_stage_follows_the_switches(self):
        self.event.is_published = True
        self.event.is_registration_open = True
        self.event.save()
        self.assertEqual(self.overview()['stage'], 'reg')
        self.event.is_enter_result_allowed = True
        self.event.save()
        self.assertEqual(self.overview()['stage'], 'live')

    def test_checklist_starts_with_untouched_description_and_unpublished_event(self):
        items = {item['id']: item for item in self.overview()['checklist']}
        self.assertFalse(items['description']['done'])
        self.assertFalse(items['description']['poster'])
        self.assertFalse(items['publish']['done'])
        self.assertTrue(items['pay']['optional'])
        self.assertFalse(items['pay']['done'])
        self.assertNotIn('optional', items['description'])

    def test_checklist_marks_done_what_is_done(self):
        self.event.description = '<p>Регламент соревнований</p>'
        self.event.is_published = True
        self.event.is_pay_allowed = True
        self.event.price = 1500
        self.event.wallet = Wallet.objects.create(owner=self.user, title='Кошелёк', wallet_id='1234567890123456',
                                                  notify_secret_key='secret')
        self.event.save()
        items = {item['id']: item for item in self.overview()['checklist']}
        self.assertTrue(items['description']['done'])
        self.assertTrue(items['publish']['done'])
        self.assertTrue(items['pay']['done'])
        self.assertEqual(items['pay']['price'], 1500)

    def test_blank_description_is_not_done(self):
        self.event.description = '   '
        self.event.save()
        self.assertFalse(self.overview()['checklist'][0]['done'])

    def test_only_the_owner_or_superuser_may_read_it(self):
        self.event.is_published = True
        self.event.save()
        self.client.logout()
        self.assertIn(self.client.get(self.url('panel')).status_code, (401, 403))
        outsider = self.user.__class__.objects.create_user(id=3, username='outsider', password='password123')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.url('panel')).status_code, 403)
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(self.url('panel')).status_code, 200)

    def test_unpublished_event_of_someone_else_is_not_found(self):
        outsider = self.user.__class__.objects.create_user(id=3, username='outsider', password='password123')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.url('panel')).status_code, 404)


class FlagsTests(PanelApiBase):
    def test_switches_save_and_the_answer_is_the_fresh_overview(self):
        response = self.set_flags({'is_published': True, 'is_registration_open': True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['stage'], 'reg')
        self.event.refresh_from_db()
        self.assertTrue(self.event.is_published)
        self.assertTrue(self.event.is_registration_open)

    def test_each_switch_works_in_both_directions(self):
        for name in services.PANEL_FLAGS:
            self.assertEqual(self.set_flags({name: True}).json()['flags'][name], True, name)
            self.assertEqual(self.set_flags({name: False}).json()['flags'][name], False, name)

    def test_other_settings_stay_as_they_were(self):
        self.event.group_num = 3
        self.event.group_list = 'А, Б, В'
        self.event.save()
        self.set_flags({'is_published': True})
        self.event.refresh_from_db()
        self.assertEqual((self.event.group_num, self.event.group_list), (3, 'А, Б, В'))

    def test_unknown_name_or_non_boolean_value_is_rejected(self):
        for body in ({'is_premium': True}, {'is_published': 'yes'}, {'is_published': 1}, {}, {'is_published': None}):
            response = self.set_flags(body)
            self.assertEqual(response.status_code, 400, body)
            self.assertEqual(response.json()['code'], 'invalid_flags')
        self.event.refresh_from_db()
        self.assertFalse(self.event.is_published)

    def test_a_valid_switch_next_to_an_invalid_one_changes_nothing(self):
        self.assertEqual(self.set_flags({'is_published': True, 'nope': True}).status_code, 400)
        self.event.refresh_from_db()
        self.assertFalse(self.event.is_published)

    def test_outsider_cannot_switch(self):
        self.event.is_published = True
        self.event.save()
        outsider = self.user.__class__.objects.create_user(id=3, username='outsider', password='password123')
        self.client.force_login(outsider)
        self.assertEqual(self.set_flags({'is_results_allowed': True}).status_code, 403)
        self.event.refresh_from_db()
        self.assertFalse(self.event.is_results_allowed)


class ActionsTests(PanelApiBase):
    def test_clear_results_keeps_participants(self):
        person = self.person(is_entered_result=True)
        self.assertEqual(self.act('clear_results').status_code, 200)
        self.assertEqual(self.event.participant.count(), 1)
        person.refresh_from_db()
        self.assertFalse(person.is_entered_result)

    def test_update_score_answers_with_the_overview(self):
        response = self.act('update_score')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.event.id)

    def test_clear_event_removes_participants_and_recreates_routes(self):
        self.person()
        response = self.act('clear_event')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['participants_count'], 0)
        self.assertEqual(self.event.route.count(), self.event.routes_num)

    def test_finished_event_cannot_be_cleared(self):
        self.event.is_expired = True
        self.event.save()
        self.person()
        response = self.act('clear_event')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'action_not_allowed')
        self.assertEqual(self.event.participant.count(), 1)

    def test_remove_event_deletes_it_and_says_where_to_go(self):
        response = self.act('remove_event')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'removed': True, 'redirect': reverse('my_events')})
        self.assertFalse(Event.objects.filter(id=self.event.id).exists())

    def test_test_data_is_for_superuser_only(self):
        response = self.act('mock_data')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.event.participant.count(), 0)
        self.client.force_login(self.superuser)
        self.assertEqual(self.act('mock_data').status_code, 200)
        self.assertEqual(self.event.participant.count(), 50)

    def test_unknown_action_is_rejected(self):
        for name in ('drop_database', '', None):
            response = self.act(name)
            self.assertEqual(response.status_code, 400, name)
            self.assertEqual(response.json()['code'], 'invalid_action')

    def test_outsider_cannot_run_actions(self):
        self.event.is_published = True
        self.event.save()
        outsider = self.user.__class__.objects.create_user(id=3, username='outsider', password='password123')
        self.client.force_login(outsider)
        self.assertEqual(self.act('remove_event').status_code, 403)
        self.assertTrue(Event.objects.filter(id=self.event.id).exists())
