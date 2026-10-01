from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.core import mail
from django.test import override_settings
from django.urls import reverse

from events import services
from events.models import Event, Participant, PromoCode, Wallet
from events.tests import ClimbingEventsBaseTestCase

SBP_LINK = 'https://qr.nspk.ru/AS1A0034?type=01&bank=100000000111&sum=150000&cur=RUB&crc=1234'


class PageTestBase(ClimbingEventsBaseTestCase):
    """Опубликованное событие с открытой регистрацией, двумя группами и тремя сетами."""

    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.superuser, title='Осенний фестиваль', date=date(2026, 10, 4))
        self.event.is_published = True
        self.event.is_registration_open = True
        self.event.is_results_allowed = True
        self.event.group_num = 2
        self.event.group_list = 'Новички, Спорт'
        self.event.set_num = 3
        self.event.set_list = '10:00, 13:00, 16:00'
        self.event.registration_fields = ['gender', 'birth_year', 'city', 'team', 'grade', 'email', 'phone_number']
        self.event.save()

    def make(self, last='Иванов', first='Иван', **kwargs):
        fields = dict(first_name=first, last_name=last, gender=Participant.GENDER_MALE, event=self.event,
                      pin=1000 + Participant.objects.count(), email='a@example.com', phone_number='+79990001122',
                      birth_year=1990, city='Москва', team='Магнезия', grade=Participant.GRADE_1)
        fields.update(kwargs)
        return Participant.objects.create(**fields)

    def set_event(self, **fields):
        for name, value in fields.items():
            setattr(self.event, name, value)
        self.event.save()

    def url(self, name, **query):
        url = reverse(f'api_events-{name}', args=[self.event.id])
        return url + ('?' + '&'.join(f'{k}={v}' for k, v in query.items()) if query else '')

    def get(self, name, **query):
        return self.client.get(self.url(name, **query))

    def post(self, name, data):
        return self.client.post(self.url(name), data=data, content_type='application/json')

    def page(self):
        return self.get('page').json()


class StageTests(PageTestBase):
    def stage(self):
        return self.page()['stage']

    def test_registration_is_open(self):
        self.assertEqual(self.stage(), 'reg')

    def test_registration_closed(self):
        self.set_event(is_registration_open=False)
        self.assertEqual(self.stage(), 'reg_closed')

    def test_full_event_counts_as_closed(self):
        self.set_event(set_max_participants=1)
        for i in range(3):
            self.make(last=f'Фамилия{i}', set_index=i)
        self.assertEqual(self.stage(), 'reg_closed')

    def test_live_while_entry_is_open(self):
        self.set_event(is_enter_result_allowed=True)
        self.assertEqual(self.stage(), 'live')

    def test_closed_entry_with_results_is_over(self):
        participant = self.make()
        services.enter_results(event=self.event, participant=participant, accents={'0': {'top': 1, 'zone': 1}})
        self.assertEqual(self.stage(), 'over')

    def test_closed_entry_without_results_is_not_over(self):
        self.make()
        self.assertEqual(self.stage(), 'reg')

    def test_expired_is_done_even_with_open_entry(self):
        self.set_event(is_enter_result_allowed=True, is_expired=True)
        self.assertEqual(self.stage(), 'done')


class PagePayloadTests(PageTestBase):
    def test_basic_fields(self):
        data = self.page()
        self.assertEqual(data['title'], 'Осенний фестиваль')
        self.assertEqual(data['date_long'], 'воскресенье, 4 октября 2026')
        self.assertEqual(data['date_short'], '4 октября')
        self.assertEqual(data['groups'], ['Новички', 'Спорт'])
        self.assertEqual([s['name'] for s in data['sets']], ['10:00', '13:00', '16:00'])
        self.assertFalse(data['can_manage'])
        self.assertTrue(data['registration']['is_open'])

    def test_multi_day_event_shows_the_range_instead_of_a_weekday(self):
        self.set_event(date_end=date(2026, 10, 5))
        data = self.page()
        self.assertEqual(data['date_long'], self.event.date_display)

    def test_single_group_and_set_are_not_listed(self):
        self.set_event(group_num=1, set_num=1)
        data = self.page()
        self.assertEqual(data['groups'], [])
        self.assertEqual(data['sets'], [])

    def test_set_counts_and_free_places(self):
        self.set_event(set_max_participants=2)
        self.make(last='А', set_index=1)
        self.make(last='Б', set_index=1)
        self.make(last='В', set_index=2)
        data = self.page()
        self.assertEqual([(s['count'], s['is_full']) for s in data['sets']], [(0, False), (2, True), (1, False)])
        self.assertEqual(data['registration']['free_places'], 3)
        self.assertEqual(data['participants_count'], 3)

    def test_no_limit_means_no_free_places(self):
        self.assertIsNone(self.page()['registration']['free_places'])

    def test_registration_deadline_is_formatted(self):
        deadline = datetime(2026, 10, 3, 23, 59, tzinfo=dt_timezone(timedelta(hours=3)))
        self.set_event(registration_close_datetime=deadline)
        self.assertEqual(self.page()['registration']['until'], '3 октября, 23:59')

    def test_without_registration_has_no_open_registration(self):
        self.set_event(is_without_registration=True)
        data = self.page()
        self.assertTrue(data['is_without_registration'])
        self.assertFalse(data['registration']['is_open'])

    def test_registration_settings_for_the_form(self):
        self.set_event(participant_min_age=14, required_fields=['birth_year'], is_view_pin_after_registration=False)
        registration = self.page()['registration']
        self.assertEqual(registration['min_age'], 14)
        self.assertIn('birth_year', registration['required_fields'])
        self.assertFalse(registration['show_pin'])
        self.assertIn({'value': 'BR', 'label': 'б/р'}, registration['grades'])

    def test_unpublished_event_is_hidden_from_anonymous_but_not_from_owner(self):
        self.set_event(is_published=False)
        self.assertEqual(self.get('page').status_code, 404)
        self.client.force_login(self.superuser)
        data = self.get('page').json()
        self.assertTrue(data['can_manage'])

    def test_price_is_shown_only_when_payment_is_on(self):
        self.set_event(is_pay_allowed=False, price='1500')
        self.assertIsNone(self.page()['pay']['price'])
        wallet = Wallet.objects.create(owner=self.superuser, title='W', wallet_id='4100', notify_secret_key='k')
        self.set_event(is_pay_allowed=True, wallet=wallet, price='1500')
        pay = self.page()['pay']
        self.assertEqual((pay['is_allowed'], pay['price']), (True, 1500))

    def test_sbp_price_is_taken_from_the_link(self):
        self.set_event(is_pay_allowed=True, pay_type=Event.PAY_TYPE_SBP, price=SBP_LINK)
        self.assertEqual(self.page()['pay']['price'], 1500)

    def test_registration_types_with_prices(self):
        wallet = Wallet.objects.create(owner=self.superuser, title='W', wallet_id='4100', notify_secret_key='k')
        self.set_event(is_pay_allowed=True, wallet=wallet, reg_type_list='Участник, + футболка', reg_type_num=2,
                       price_list={'0': '1500', '1': '2000'})
        registration = self.page()['registration']
        self.assertEqual(registration['reg_types'], [{'index': 0, 'name': 'Участник', 'price': 1500},
                                                     {'index': 1, 'name': '+ футболка', 'price': 2000}])
        self.assertEqual(self.page()['pay']['price'], 1500)


class PodiumTests(PageTestBase):
    def finish(self):
        for gender, last_names in ((Participant.GENDER_MALE, 'АБВГ'), (Participant.GENDER_FEMALE, 'ДЕЖЗ')):
            for index, last in enumerate(last_names):
                participant = self.make(last=last, gender=gender, group_index=1)
                accents = {str(i): {'top': 2, 'zone': 2} for i in range(4 - index)}
                services.enter_results(event=self.event, participant=participant, accents=accents,
                                       force_update_disable=True)
        services.update_results(event=self.event)
        self.set_event(is_expired=True)

    def test_three_places_per_group_and_gender(self):
        self.finish()
        podium = self.page()['podium']
        self.assertEqual([g['group'] for g in podium], ['Новички', 'Спорт'])
        self.assertEqual(podium[0]['male'], [])
        self.assertEqual([p['last_name'] for p in podium[1]['male']], ['А', 'Б', 'В'])
        self.assertEqual([p['place'] for p in podium[1]['female']], [1, 2, 3])

    def test_no_podium_before_the_end(self):
        self.finish()
        self.set_event(is_expired=False)
        self.assertEqual(self.page()['podium'], [])

    def test_no_podium_while_results_are_hidden(self):
        self.finish()
        self.set_event(is_results_allowed=False)
        self.assertEqual(self.page()['podium'], [])


class ParticipantsApiTests(PageTestBase):
    def test_sorted_by_name_without_private_data(self):
        self.make(last='Яковлев', first='Пётр', pin=4321)
        self.make(last='Андреев', first='Иван')
        body = self.get('participant-list').content.decode()
        for private in ('a@example.com', '+79990001122', '"pin"', '"email"', '"phone"', '"paid"'):
            self.assertNotIn(private, body)
        data = self.get('participant-list').json()
        self.assertFalse(data['can_manage'])
        self.assertEqual([p['last_name'] for p in data['participants']], ['Андреев', 'Яковлев'])

    def test_public_fields_follow_the_registration_settings(self):
        self.make()
        row = self.get('participant-list').json()['participants'][0]
        self.assertEqual((row['birth_year'], row['grade'], row['city'], row['team']),
                         (1990, '1 сп.р.', 'Москва', 'Магнезия'))
        self.set_event(registration_fields=['gender'])
        row = self.get('participant-list').json()['participants'][0]
        self.assertEqual((row['birth_year'], row['grade'], row['city'], row['team']), (None, '', '', ''))

    def test_organizer_also_sees_pin_contacts_and_payment(self):
        self.make(pin=4321, paid=True)
        self.client.force_login(self.superuser)
        data = self.get('participant-list').json()
        row = data['participants'][0]
        self.assertTrue(data['can_manage'])
        self.assertEqual((row['pin'], row['phone'], row['email'], row['paid']),
                         (4321, '+79990001122', 'a@example.com', True))

    def test_another_user_is_not_an_organizer(self):
        self.make()
        self.client.force_login(self.user)
        self.assertFalse(self.get('participant-list').json()['can_manage'])

    def test_place_is_hidden_until_results_are_opened(self):
        participant = self.make()
        services.enter_results(event=self.event, participant=participant, accents={'0': {'top': 1, 'zone': 1}})
        row = self.get('participant-list').json()['participants'][0]
        self.assertEqual((row['entered'], row['place'], row['place_of']), (True, 1, 1))
        self.set_event(is_results_allowed=False)
        row = self.get('participant-list').json()['participants'][0]
        self.assertEqual((row['entered'], row['place'], row['place_of']), (True, None, None))

    def test_unpublished_event_is_hidden(self):
        self.set_event(is_published=False)
        self.assertEqual(self.get('participant-list').status_code, 404)


class RegistrationApiTests(PageTestBase):
    def form(self, **kwargs):
        data = dict(last_name='Зайцева', first_name='Юлия', gender='FEMALE', birth_year=1996, grade='2C',
                    city='Москва', team='Магнезия', group_index=1, set_index=2, email='yulia@example.com',
                    phone_number='+79001234567')
        data.update(kwargs)
        return data

    def test_registers_and_returns_pin(self):
        response = self.post('registration', self.form())
        self.assertEqual(response.status_code, 201)
        data = response.json()
        participant = Participant.objects.get(event=self.event)
        self.assertEqual(data['participant']['id'], participant.id)
        self.assertEqual(data['participant']['set_index'], 2)
        self.assertEqual(data['participant']['group'], 'Спорт')
        self.assertEqual(data['pin'], participant.pin)
        self.assertFalse(data['paid'])
        self.assertFalse(data['emailed'])
        self.assertEqual((participant.last_name, participant.group_index, participant.grade), ('Зайцева', 1, '2C'))

    def test_pin_is_not_shown_when_the_organizer_turned_it_off(self):
        self.set_event(is_view_pin_after_registration=False)
        self.assertIsNone(self.post('registration', self.form()).json()['pin'])

    def test_duplicate(self):
        self.make(last='Зайцева', first='Юлия')
        response = self.post('registration', self.form())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'duplicate')
        self.assertEqual(Participant.objects.count(), 1)

    def test_too_young(self):
        self.set_event(participant_min_age=14, registration_fields=['gender', 'birth_year'])
        response = self.post('registration', self.form(birth_year=2013))
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual((data['code'], data['min_age']), ('too_young', 14))
        self.assertEqual(Participant.objects.count(), 0)

    def test_set_filled_while_the_form_was_open(self):
        self.set_event(set_max_participants=1)
        self.make(last='Первый', set_index=2)
        response = self.post('registration', self.form())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'set_full')
        self.assertEqual(Participant.objects.count(), 1)

    def test_closed_registration(self):
        self.set_event(is_registration_open=False)
        response = self.post('registration', self.form())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'registration_closed')

    def test_event_without_registration_does_not_register(self):
        self.set_event(is_without_registration=True)
        response = self.post('registration', self.form())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'registration_not_needed')

    def test_required_fields_and_choices_are_checked(self):
        self.set_event(required_fields=['city'])
        broken_forms = ({'city': ''}, {'group_index': 5}, {'set_index': -1}, {'last_name': ''}, {'email': 'abc'},
                        {'gender': 'X'})
        for broken in broken_forms:
            response = self.post('registration', self.form(**broken))
            self.assertEqual(response.status_code, 400, broken)
            self.assertEqual(response.json()['code'], 'invalid_fields')
        self.assertEqual(Participant.objects.count(), 0)

    def test_registration_type_is_chosen_by_index(self):
        self.set_event(reg_type_list='Участник, + футболка', reg_type_num=2)
        self.assertEqual(self.post('registration', self.form(reg_type_index=1)).status_code, 201)
        self.assertEqual(Participant.objects.get().reg_type_index, 1)
        self.assertEqual(self.post('registration', self.form(last_name='Другая', reg_type_index=7)).status_code, 400)

    def test_email_with_pin_and_pay_link_is_sent_only_with_payment(self):
        self.post('registration', self.form())
        self.assertEqual(len(mail.outbox), 0)
        wallet = Wallet.objects.create(owner=self.superuser, title='W', wallet_id='4100', notify_secret_key='k')
        self.set_event(is_pay_allowed=True, wallet=wallet, price='1500')
        response = self.post('registration', self.form(last_name='Другая'))
        self.assertTrue(response.json()['emailed'])
        self.assertEqual(len(mail.outbox), 1)
        participant = Participant.objects.get(last_name='Другая')
        self.assertIn(f"/e/{self.event.id}/pay/?p={participant.id}", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['yulia@example.com'])

    def test_last_free_seat_closes_the_registration(self):
        self.set_event(set_max_participants=1, set_num=1, group_num=1)
        data = self.form()
        del data['group_index'], data['set_index']
        self.assertEqual(self.post('registration', data).status_code, 201)
        self.assertEqual(self.page()['stage'], 'reg_closed')
        self.assertEqual(self.post('registration', {**data, 'last_name': 'Второй'}).status_code, 403)


class MeApiTests(PageTestBase):
    def test_payment_status_and_standing(self):
        participant = self.make(paid=True)
        services.enter_results(event=self.event, participant=participant, accents={'0': {'top': 1, 'zone': 1}})
        data = self.get('me', participant=participant.id).json()
        self.assertEqual(data['participant']['id'], participant.id)
        self.assertTrue(data['paid'])
        self.assertEqual(data['standing'], {'place': 1, 'of': 1})

    def test_no_standing_before_the_result_or_while_results_are_hidden(self):
        participant = self.make()
        self.assertIsNone(self.get('me', participant=participant.id).json()['standing'])
        services.enter_results(event=self.event, participant=participant, accents={'0': {'top': 1, 'zone': 1}})
        self.set_event(is_results_allowed=False)
        self.assertIsNone(self.get('me', participant=participant.id).json()['standing'])

    def test_unknown_participant_or_one_from_another_event(self):
        other = services.create_event(owner=self.superuser, title='Other', date=date(2026, 10, 5))
        other.is_published = True
        other.save()
        foreign = Participant.objects.create(first_name='Чужой', last_name='Чужой', event=other, pin=1111)
        for value in (foreign.id, 999999, 'abc', ''):
            response = self.get('me', participant=value)
            self.assertEqual(response.status_code, 404, value)
            self.assertEqual(response.json()['code'], 'participant_not_found')
        self.assertEqual(self.client.get(self.url('me')).status_code, 404)

    def test_email_and_phone_are_not_exposed(self):
        participant = self.make()
        body = self.get('me', participant=participant.id).content.decode()
        for private in ('a@example.com', '+79990001122', '"pin"'):
            self.assertNotIn(private, body)


class PayApiTests(PageTestBase):
    def setUp(self):
        super().setUp()
        self.wallet = Wallet.objects.create(owner=self.superuser, title='W', wallet_id='4100123', notify_secret_key='k')
        self.set_event(is_pay_allowed=True, wallet=self.wallet, price='1500')
        self.participant = self.make()

    def test_yoomoney_form_fields(self):
        data = self.get('pay', participant=self.participant.id).json()
        self.assertEqual(data['type'], 'yoomoney')
        self.assertEqual(data['amount'], 1500)
        self.assertEqual(data['receiver'], '4100123')
        self.assertEqual(data['label'], f'e{self.event.id}_p{self.participant.id}')
        self.assertEqual(data['action'], 'https://yoomoney.ru/quickpay/confirm.xml')
        self.assertTrue(data['success_url'].endswith(f'/e/{self.event.id}/pay/done/'))

    def test_price_by_registration_type(self):
        self.set_event(reg_type_list='Участник, + футболка', reg_type_num=2, price_list={'0': '1500', '1': '2000'})
        self.participant.reg_type_index = 1
        self.participant.save()
        self.assertEqual(self.get('pay', participant=self.participant.id).json()['amount'], 2000)

    def test_sbp_link_amount_and_qr(self):
        self.set_event(pay_type=Event.PAY_TYPE_SBP, price=SBP_LINK)
        data = self.get('pay', participant=self.participant.id).json()
        self.assertEqual((data['type'], data['amount'], data['link']), ('sbp', 1500, SBP_LINK))
        self.assertTrue(data['qr'].startswith('data:image/svg+xml'))

    def test_already_paid(self):
        self.participant.paid = True
        self.participant.save()
        self.assertEqual(self.get('pay', participant=self.participant.id).json(), {'type': 'paid'})

    def test_unavailable(self):
        for fields in ({'is_pay_allowed': False}, {'wallet': None}, {'price': 'много'}, {'price': None}):
            self.set_event(**fields)
            response = self.get('pay', participant=self.participant.id)
            self.assertEqual(response.status_code, 403, fields)
            self.assertEqual(response.json()['code'], 'pay_unavailable')
            self.set_event(is_pay_allowed=True, wallet=self.wallet, price='1500')

    def test_unknown_participant(self):
        self.assertEqual(self.get('pay', participant=999999).status_code, 404)

    def test_promo_code_gives_a_new_price(self):
        promo = PromoCode.objects.create(event=self.event, title='LESNAYA', price=1200)
        data = self.get('pay-promo', code='lesnaya').json()
        self.assertEqual(data, {'valid': True, 'price': 1200, 'promocode_id': promo.id})

    def test_unknown_empty_or_used_up_promo_code(self):
        PromoCode.objects.create(event=self.event, title='ONCE', price=1000, max_applied_num=1, applied_num=1)
        for code in ('NOPE', '', 'ONCE'):
            self.assertEqual(self.get('pay-promo', code=code).json(), {'valid': False}, code)

    def test_promo_code_of_another_event_does_not_work(self):
        other = services.create_event(owner=self.superuser, title='Other', date=date(2026, 10, 5))
        PromoCode.objects.create(event=other, title='ELSE', price=1)
        self.assertFalse(self.get('pay-promo', code='ELSE').json()['valid'])

    @override_settings(VITE_DEV_SERVER='http://localhost:5173')
    def test_pay_page_opens_for_the_event(self):
        response = self.client.get(f"{reverse('event_pay', args=[self.event.id])}?p={self.participant.id}")
        self.assertContains(response, 'id="event-app"')
