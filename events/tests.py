import io
import re
import tempfile
from datetime import datetime, date
from unittest import mock
from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db.utils import IntegrityError
from events.models import CustomUser, Event, Participant, Route, Wallet, PromoCode, PayDetail
from events import img_tools, services
from events.forms import CreateEventForm
from events.exceptions import DuplicateParticipantError, ParticipantTooYoungError

class ClimbingEventsBaseTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        # Create user with id=1, as required by create_event service
        self.superuser = CustomUser.objects.create_superuser(
            id=1,
            username='admin',
            email='admin@example.com',
            password='password123',
            premium_price=100
        )
        # Create normal user with explicit id=2 to avoid Postgres PK sequence collision
        self.user = CustomUser.objects.create_user(
            id=2,
            username='user',
            email='user@example.com',
            password='password123'
        )

class ModelsTestCase(ClimbingEventsBaseTestCase):
    def test_wallet_creation_and_str(self):
        wallet = Wallet.objects.create(
            owner=self.user,
            title='My Wallet',
            wallet_id='1234567890123456',
            notify_secret_key='secret'
        )
        self.assertEqual(str(wallet), 'My Wallet (******3456)')

    def test_event_creation_and_defaults(self):
        event = Event.objects.create(
            owner=self.user,
            title='Autumn Boulder 2026',
            date=date(2026, 10, 1)
        )
        self.assertEqual(event.gym, 'Скалодром')
        self.assertEqual(event.score_type, Event.SCORE_SIMPLE_SUM)
        self.assertTrue(event.is_premium)
        self.assertFalse(event.is_published)

    def test_participant_creation_and_str(self):
        event = services.create_event(owner=self.superuser, title="Test Event", date=datetime(2026, 10, 1))
        participant = Participant.objects.create(
            first_name='Иван',
            last_name='Иванов',
            gender=Participant.GENDER_MALE,
            birth_year=1995,
            event=event,
            pin=1234,
            set_index=0
        )
        self.assertEqual(str(participant), f'<Part-t: Name=Иванов, PIN=1234, Score={participant.score}, set=0>')

    def test_route_creation_and_str(self):
        event = services.create_event(owner=self.superuser, title="Test Event", date=datetime(2026, 10, 1))
        route = Route.objects.get(event=event, number=1)
        self.assertEqual(str(route), f"N=1, score={route.score_json}")


class ServicesTestCase(ClimbingEventsBaseTestCase):
    def test_create_event_routes(self):
        event = services.create_event(owner=self.superuser, title="Bouldering Event", date=datetime(2026, 10, 1))
        self.assertEqual(event.routes_num, 10)
        self.assertEqual(Route.objects.filter(event=event).count(), 10)

    def test_group_and_set_lists(self):
        event = services.create_event(owner=self.superuser, title="Test Lists", date=datetime(2026, 10, 1))
        event.group_num = 2
        event.group_list = "Новички, Любители"
        event.set_num = 3
        event.set_list = "Сет 1, Сет 2, Сет 3"
        event.save()

        self.assertEqual(services.get_group_list(event), ['Новички', 'Любители'])
        self.assertEqual(services.get_set_list(event), ['Сет 1', 'Сет 2', 'Сет 3'])

    def test_clear_event(self):
        event = services.create_event(owner=self.superuser, title="Clear Event", date=datetime(2026, 10, 1))
        Participant.objects.create(first_name='A', last_name='B', event=event, pin=1234)
        
        self.assertEqual(Route.objects.filter(event=event).count(), 10)
        self.assertEqual(Participant.objects.filter(event=event).count(), 1)

        services.clear_event(event)
        self.assertEqual(Participant.objects.filter(event=event).count(), 0)
        self.assertEqual(Route.objects.filter(event=event).count(), 10)

    def test_is_registration_open_published_logic(self):
        event = services.create_event(owner=self.superuser, title="Reg Event", date=datetime(2026, 10, 1))
        
        # Initially not published and registration not open
        self.assertFalse(services.is_registration_open(event))

        event.is_published = True
        event.is_registration_open = True
        event.save()
        self.assertTrue(services.is_registration_open(event))

        # Check limit for set participants
        event.set_num = 2
        event.set_max_participants = 1
        event.save()
        
        # Max participants in all sets is 2 * 1 = 2
        Participant.objects.create(first_name='A', last_name='B', event=event, pin=1234, set_index=0)
        self.assertTrue(services.is_registration_open(event))
        Participant.objects.create(first_name='C', last_name='D', event=event, pin=5678, set_index=1)
        # Reached limit
        self.assertFalse(services.is_registration_open(event))

    def test_register_participant_success_and_failures(self):
        event = services.create_event(owner=self.superuser, title="Reg Flow", date=datetime(2026, 10, 1))
        event.is_published = True
        event.is_registration_open = True
        event.participant_min_age = 18
        event.save()

        # Age requirement failure
        data_young = {
            'first_name': 'Young',
            'last_name': 'Climber',
            'gender': Participant.GENDER_FEMALE,
            'birth_year': datetime.today().year - 10,  # 10 years old
            'city': 'City',
            'team': 'Team',
            'grade': Participant.GRADE_BR,
        }
        with self.assertRaises(ParticipantTooYoungError):
            services.register_participant(event, data_young)

        # Successful registration
        data_valid = {
            'first_name': 'Adult',
            'last_name': 'Climber',
            'gender': Participant.GENDER_MALE,
            'birth_year': datetime.today().year - 20,  # 20 years old
            'city': 'City',
            'team': 'Team',
            'grade': Participant.GRADE_3,
        }
        p = services.register_participant(event, data_valid)
        self.assertIsNotNone(p)
        self.assertEqual(p.first_name, 'Adult')
        self.assertTrue(1000 <= p.pin <= 9999)

        # Duplicate registration failure
        with self.assertRaises(DuplicateParticipantError):
            services.register_participant(event, data_valid)

    def test_calculate_results_simple_sum(self):
        event = services.create_event(owner=self.superuser, title="Simple Sum Event", date=datetime(2026, 10, 1))
        event.score_type = Event.SCORE_SIMPLE_SUM
        event.is_published = True
        event.save()

        p = Participant.objects.create(
            first_name='Petr',
            last_name='Petrov',
            gender=Participant.GENDER_MALE,
            event=event,
            pin=1122
        )
        
        # 10 routes. Send route index 0 with Flash, index 1 with Redpoint.
        # Format of french_accents is: { route_index_string: { "top": accent_type, "zone": accent_type } }
        # where accent_type: 1 = FLASH, 2 = REDPOINT, 0 = NO ACCENT
        # We need to populate french_accents and set is_entered_result = True
        p.french_accents = {
            "0": {"top": 1, "zone": 1},  # Flash
            "1": {"top": 2, "zone": 2},  # Redpoint
        }
        p.is_entered_result = True
        p.save()

        # Update results
        services.update_results(event=event)
        
        p.refresh_from_db()
        # For simple sum, default route score is 1.
        # For index 0: score = 1 * (1 + flash_points_pc/100) = 1 * 1.25 = 1.25 * redpoint_points (80) = 100
        # For index 1: score = 1 * redpoint_points (80) = 80
        # Total score = 100 + 80 = 180
        self.assertEqual(p.score, 180.0)
        self.assertEqual(p.place, 1)

    def test_calculate_results_advanced(self):
        # Create event with 3 sets, 2 groups
        event = services.create_event(owner=self.superuser, title="Advanced Event", date=datetime(2026, 10, 1))
        event.is_published = True
        event.group_num = 2
        event.group_list = "Group 0, Group 1"
        event.set_num = 3
        event.set_list = "Set 0, Set 1, Set 2"
        event.is_separate_score_by_groups = True
        event.is_count_only_entered_results = True
        event.score_type = Event.SCORE_PROPORTIONAL
        event.save()

        # Route 0
        r0 = Route.objects.get(event=event, number=1)

        # 1. Proportional scoring: check set independence & gender/group separation
        # We create participants in different sets, genders, and groups.
        
        # Male, Group 0, Set 0 - Sends Route 0 (Flash)
        p1 = Participant.objects.create(
            first_name='M00', last_name='S0', gender=Participant.GENDER_MALE,
            group_index=0, set_index=0, event=event, pin=1001, is_entered_result=True,
            french_accents={"0": {"top": 1, "zone": 1}}
        )
        
        # Male, Group 0, Set 1 - Sends Route 0 (Redpoint)
        # Since p1 and p2 are in the same group and gender, but different sets:
        # both should contribute to Route 0 score for (MALE, Group 0).
        p2 = Participant.objects.create(
            first_name='M01', last_name='S1', gender=Participant.GENDER_MALE,
            group_index=0, set_index=1, event=event, pin=1002, is_entered_result=True,
            french_accents={"0": {"top": 2, "zone": 2}}
        )

        # Male, Group 1, Set 0 - Sends Route 0 (Flash)
        # Should be completely separate because of group separation.
        p3 = Participant.objects.create(
            first_name='M10', last_name='S0', gender=Participant.GENDER_MALE,
            group_index=1, set_index=0, event=event, pin=1003, is_entered_result=True,
            french_accents={"0": {"top": 1, "zone": 1}}
        )

        # Female, Group 0, Set 0 - Sends Route 0 (Flash)
        # Should be completely separate because of gender separation.
        p4 = Participant.objects.create(
            first_name='F00', last_name='S0', gender=Participant.GENDER_FEMALE,
            group_index=0, set_index=0, event=event, pin=1004, is_entered_result=True,
            french_accents={"0": {"top": 1, "zone": 1}}
        )

        services.update_results(event=event)

        r0.refresh_from_db()
        # Verify Route 0 scores in route.score_json.
        # Format of keys is: "{gender}_{group_index}"
        # For MALE_0: there are 2 sends. Route score = 1 / 2 = 0.5.
        self.assertEqual(r0.score_json.get("MALE_0"), 0.5)
        # For MALE_1: there is 1 send. Route score = 1 / 1 = 1.0.
        self.assertEqual(r0.score_json.get("MALE_1"), 1.0)
        # For FEMALE_0: there is 1 send. Route score = 1 / 1 = 1.0.
        self.assertEqual(r0.score_json.get("FEMALE_0"), 1.0)

        # Verify participant scores for Proportional logic:
        p1.refresh_from_db()
        p2.refresh_from_db()
        # For p1: Route 0 score is 0.5. Flash bonus (1 + 25/100) = 1.25. Redpoint points = 80.
        # Score = 0.5 * 1.25 * 80 = 50.0
        self.assertEqual(p1.score, 50.0)

        # For p2: Route 0 score is 0.5. No Flash bonus. Redpoint points = 80.
        # Score = 0.5 * 1.0 * 80 = 40.0
        self.assertEqual(p2.score, 40.0)

        # 2. Table scoring: SCORE_GRADE
        event.score_type = Event.SCORE_GRADE
        event.score_table = {"5": "15", "6A": "25"}
        event.save()
        r0.grade = "6A"
        r0.save()

        # Update results again
        services.update_results(event=event)
        p1.refresh_from_db()
        p2.refresh_from_db()
        # For SCORE_GRADE, route score is 25 (from table).
        # For p1: Flash bonus is applied (1.25) but not redpoint_points.
        # Score = 25 * 1.25 = 31.25
        self.assertEqual(p1.score, 31.25)
        # For p2: Redpoint (1.0). Score = 25 * 1.0 = 25.0
        self.assertEqual(p2.score, 25.0)

        # 3. Num Accents scoring: SCORE_NUM_ACCENTS
        event.score_type = Event.SCORE_NUM_ACCENTS
        event.save()
        services.update_results(event=event)
        p1.refresh_from_db()
        p2.refresh_from_db()
        # For p1: Flash = 101.0
        self.assertEqual(p1.score, 101.0)
        # For p2: Redpoint = 100.0
        self.assertEqual(p2.score, 100.0)

        # 4. French scoring: SCORE_FRENCH
        event.score_type = Event.SCORE_FRENCH
        event.save()
        p1.french_accents = {
            "0": {"top": 2, "zone": 3}
        }
        p1.save()
        services.update_results(event=event)
        p1.refresh_from_db()
        # Calculation:
        # tops = 1, zones = 1, tops_a = 2, zones_a = 3
        # score = 10000*1 + 1000*1 + 100*(100-2) + 10*(100-3) = 10000 + 1000 + 9800 + 970 = 21770
        self.assertEqual(p1.score, 21770.0)


class ViewsTestCase(ClimbingEventsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.superuser, title="View Event", date=datetime(2026, 10, 1))
        self.event.is_published = True
        self.event.is_registration_open = True
        self.event.save()

    @override_settings(VITE_DEV_SERVER='http://localhost:5173')
    def test_main_view_mounts_vue_with_first_catalog_page_inside(self):
        # каталог на главной — Vue; первую страницу Django кладёт в HTML, остальное экран берёт из API
        for i in range(14):
            e = services.create_event(owner=self.superuser, title=f"Event {i}", date=datetime(2026, 10, 1))
            e.is_published = True
            e.save()

        response = self.client.get(reverse('main'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="home-app"')
        self.assertContains(response, 'src/entries/home.ts')
        initial = response.context['home_initial']
        self.assertEqual(len(initial['results']), services.SITE_PAGE_SIZE)
        self.assertTrue(initial['has_more'])
        self.assertEqual(initial['counts'], {'upcoming': 15, 'past': 0})
        self.assertContains(response, 'id="home-initial"')
        self.assertContains(response, 'id="site-context"')

    @override_settings(VITE_DEV_SERVER='http://localhost:5173')
    def test_my_events_view_mounts_vue_for_organizer_and_redirects_guest(self):
        self.assertEqual(self.client.get(reverse('my_events')).status_code, 302)
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('my_events'))
        self.assertContains(response, 'id="mine-app"')
        self.assertContains(response, 'src/entries/mine.ts')
        self.assertEqual([c['title'] for c in response.context['mine_initial']['results']], ['View Event'])

    @override_settings(VITE_DEV_SERVER='http://localhost:5173')
    def test_every_event_address_mounts_the_same_vue_app(self):
        for name in ('event', 'enter_results', 'results', 'participants', 'registration', 'event_pay',
                     'event_pay_done'):
            response = self.client.get(reverse(name, kwargs={'event_id': self.event.id}))
            self.assertEqual(response.status_code, 200, name)
            self.assertContains(response, f'id="event-app" data-event-id="{self.event.id}"')

    @override_settings(VITE_DEV_SERVER='http://localhost:5173')
    def test_page_has_link_preview_tags(self):
        response = self.client.get(reverse('event', kwargs={'event_id': self.event.id}))
        self.assertContains(response, '<meta property="og:title" content="View Event">')
        self.assertContains(response, '<title>View Event — RockEvents</title>')

    def test_event_page_hidden_for_unpublished_event(self):
        self.event.is_published = False
        self.event.save()
        response = self.client.get(reverse('enter_results', kwargs={'event_id': self.event.id}))
        self.assertNotContains(response, 'id="event-app"')
        self.assertContains(response, 'Событие не опубликовано')

    def test_event_page_is_open_to_its_owner_when_unpublished(self):
        self.event.is_published = False
        self.event.save()
        self.client.force_login(self.superuser)
        with override_settings(VITE_DEV_SERVER='http://localhost:5173'):
            response = self.client.get(reverse('event', kwargs={'event_id': self.event.id}))
        self.assertContains(response, 'id="event-app"')

    def test_old_pay_and_registration_links_lead_to_the_event_page(self):
        pid = 5
        eid = self.event.id
        self.assertRedirects(self.client.get(reverse('pay_create', args=[eid, pid])),
                             f"{reverse('event_pay', args=[eid])}?p={pid}", fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('pay_ok', args=[eid])), reverse('event_pay_done', args=[eid]),
                             fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('pay_unavailable', args=[eid])), reverse('event_pay', args=[eid]),
                             fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('event_registration_ok', args=[eid, pid])),
                             reverse('event', args=[eid]), fetch_redirect_response=False)

    def test_enter_wo_reg_old_link_redirects_to_enter_page(self):
        response = self.client.get(reverse('enter_wo_reg', kwargs={'event_id': self.event.id}))
        self.assertRedirects(response, reverse('enter_results', kwargs={'event_id': self.event.id}))


class APITestCase(ClimbingEventsBaseTestCase):
    def test_jwt_token_obtain_and_refresh(self):
        url = reverse('token_obtain_pair')
        # Login using superuser credentials
        data = {
            'username': 'admin',
            'password': 'password123'
        }
        response = self.client.post(url, data=data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.json())
        self.assertIn('refresh', response.json())

        access_token = response.json()['access']
        refresh_token = response.json()['refresh']

        # Try refresh
        url_refresh = reverse('token_refresh')
        response_refresh = self.client.post(
            url_refresh, 
            data={'refresh': refresh_token}, 
            content_type='application/json'
        )
        self.assertEqual(response_refresh.status_code, 200)
        self.assertIn('access', response_refresh.json())

    def test_events_api_read_write(self):
        # Create an event via ORM
        event = services.create_event(owner=self.superuser, title="Public Event", date=date(2026, 10, 1))
        event.is_published = True
        event.save()

        # Anonymous request to list events (published only)
        url = reverse('api_events-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        # Attempt to create event anonymously should fail
        response_create_anon = self.client.post(
            url, 
            data={'title': 'New Anon Event', 'date': '2026-10-02'}, 
            content_type='application/json'
        )
        self.assertEqual(response_create_anon.status_code, 401)

        # Login and obtain token
        token_url = reverse('token_obtain_pair')
        token_response = self.client.post(
            token_url, 
            data={'username': 'admin', 'password': 'password123'}, 
            content_type='application/json'
        )
        access_token = token_response.json()['access']
        headers = {'HTTP_AUTHORIZATION': f'Bearer {access_token}'}

        # Create event as superuser
        response_create = self.client.post(
            url, 
            data={'title': 'Authorized Event', 'date': '2026-10-02'}, 
            content_type='application/json',
            **headers
        )
        self.assertEqual(response_create.status_code, 201)
        self.assertEqual(Event.objects.filter(title='Authorized Event').count(), 1)
        # Verify routes were created automatically via services.create_event inside perform_create
        new_event = Event.objects.get(title='Authorized Event')
        self.assertEqual(Route.objects.filter(event=new_event).count(), 10)

    def test_participants_api_registration_and_results(self):
        event = services.create_event(owner=self.superuser, title="API Reg Event", date=date(2026, 10, 1))
        event.is_published = True
        event.is_registration_open = True
        event.save()

        # Register participant via API (anonymous POST is allowed if reg is open)
        url = reverse('api_participants-list')
        reg_data = {
            'event': event.id,
            'first_name': 'Семён',
            'last_name': 'Семёнов',
            'gender': Participant.GENDER_MALE,
            'birth_year': 1992,
            'city': 'Питер',
            'team': 'Нева',
            'grade': Participant.GRADE_BR,
            'group_index': 0,
            'set_index': 0
        }
        response = self.client.post(url, data=reg_data, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('pin', response.json())
        pin = response.json()['pin']
        p_id = response.json()['id']

        # Enter results via custom action
        url_enter = reverse('api_participants-enter-results', kwargs={'pk': p_id})
        accents_data = {
            'pin': pin,
            'accents': {
                "0": {"top": 1, "zone": 1},  # Flash route 0
                "1": {"top": 2, "zone": 2}   # Redpoint route 1
            }
        }
        response_enter = self.client.post(url_enter, data=accents_data, content_type='application/json')
        self.assertEqual(response_enter.status_code, 200)

        # Check results were processed
        participant = Participant.objects.get(id=p_id)
        self.assertTrue(participant.is_entered_result)
        self.assertEqual(participant.french_accents.get("0"), {"top": 1, "zone": 1})


class ProtocolAsyncTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.superuser = CustomUser.objects.create_superuser(
            id=1,
            username='admin',
            email='admin@example.com',
            password='password123',
            premium_price=100
        )

    def test_async_get_results_generates_protocol(self):
        self.client.force_login(self.superuser)
        event = services.create_event(owner=self.superuser, title="Premium Event", date=date(2026, 10, 1))
        event.is_premium = True
        event.save()

        url = reverse('async_get_results', args=[event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        import threading
        threads = [t for t in threading.enumerate() if t.name == f"export_results_{event.id}"]
        for t in threads:
            t.join(timeout=5)

        protocols = services.get_list_of_protocols(event)
        self.assertGreater(len(protocols), 0)
        self.assertTrue(protocols[0]['name'].startswith("results_"))
        self.assertTrue(protocols[0]['name'].endswith(".xlsx"))

        for item in protocols:
            services.remove_file(f"{event.id}/{item['name']}")


class LegacyAccentsConversionTests(TestCase):
    """Конвертация устаревшего Participant.accents в french_accents (миграция 0033).

    Само поле accents удалено в 0034, поэтому проверяем функцию преобразования: на
    восстановленной из старого бэкапа базе 0033 отработает до 0034 и данные перенесёт.
    """

    @staticmethod
    def _convert(accents):
        import importlib
        migration = importlib.import_module('events.migrations.0033_backfill_french_accents')
        return migration.convert_legacy_accents(accents)

    def test_accent_codes_converted_to_top_and_zone(self):
        self.assertEqual(self._convert({'0': '2', '1': '1', '2': '0'}), {
            '0': {'top': 2, 'zone': 2},
            '1': {'top': 1, 'zone': 1},
            '2': {'top': 0, 'zone': 0},
        })

    def test_empty_input_gives_empty_result(self):
        self.assertEqual(self._convert(None), {})
        self.assertEqual(self._convert({}), {})

    def test_broken_values_are_skipped_not_raised(self):
        self.assertEqual(self._convert({'0': 'RP', '1': '2', '2': None}), {'1': {'top': 2, 'zone': 2}})


class XlTemplateTests(ClimbingEventsBaseTestCase):
    """Шаблоны протоколов лежат в static-исходниках приложения и должны находиться без collectstatic."""

    XLSX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.superuser, title="XL Event", date=date(2026, 10, 1))
        Participant.objects.create(
            first_name='Иван',
            last_name='Иванов',
            gender=Participant.GENDER_MALE,
            birth_year=1995,
            event=self.event,
            pin=1234,
            set_index=0,
        )
        self.client.force_login(self.superuser)

    def test_load_template_finds_all_xl_templates(self):
        from events import xl_tools
        for name in ('result_template.xlsx', 'startlist_template.xlsx', 'results_example.xlsx'):
            self.assertIsNotNone(xl_tools.load_template(f'events/xl_templates/{name}'))

    def test_load_template_raises_on_unknown_name(self):
        from events import xl_tools
        with self.assertRaises(FileNotFoundError):
            xl_tools.load_template('events/xl_templates/no_such_template.xlsx')

    def test_export_result_creates_protocol_file(self):
        from events import xl_tools
        xl_tools.export_result(event=self.event)
        protocols = services.get_list_of_protocols(self.event)
        self.assertEqual(len(protocols), 1)
        self.assertTrue(protocols[0]['name'].startswith('results_'))
        self.assertTrue(protocols[0]['name'].endswith('.xlsx'))
        for item in protocols:
            services.remove_file(f"{self.event.id}/{item['name']}")

    def test_export_startlist_response(self):
        response = self.client.post(reverse('admin_protocols', args=[self.event.id]),
                                    data={'export_startlist': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], self.XLSX_CONTENT_TYPE)
        self.assertGreater(len(response.content), 0)

    def test_export_result_example_response_for_non_premium_event(self):
        self.event.is_premium = False
        self.event.save()
        response = self.client.post(reverse('admin_protocols', args=[self.event.id]),
                                    data={'export_result': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], self.XLSX_CONTENT_TYPE)
        self.assertGreater(len(response.content), 0)


class MultiDayEventTests(TestCase):
    def setUp(self):
        self.superuser = CustomUser.objects.create_superuser(
            id=1,
            username='admin',
            email='admin@example.com',
            password='password123',
            premium_price=100
        )

    def test_multi_day_event_creation(self):
        start_date = date(2026, 10, 1)
        end_date = date(2026, 10, 5)
        event = services.create_event(
            owner=self.superuser,
            title="Multi Day Event",
            date=start_date,
            date_end=end_date
        )
        self.assertEqual(event.date, start_date)
        self.assertEqual(event.date_end, end_date)
        self.assertEqual(event.date_display, "1 — 5 октября 2026 г.")

    def test_single_day_event_date_display(self):
        start_date = date(2026, 10, 1)
        event = services.create_event(owner=self.superuser, title="Single Day Event", date=start_date)
        self.assertEqual(event.date_display, "1 октября 2026 г.")

    def test_event_is_today_multi_day(self):
        import datetime
        from events.templatetags import events_tags
        today = date.today()
        yesterday = today - datetime.timedelta(days=1)
        tomorrow = today + datetime.timedelta(days=1)

        event = Event.objects.create(owner=self.superuser, title="Test Today", date=yesterday, date_end=tomorrow)
        self.assertTrue(event.is_today)
        self.assertTrue(events_tags.event_is_today(event))

        expired_event = Event.objects.create(
            owner=self.superuser,
            title="Past Event",
            date=today - datetime.timedelta(days=5),
            date_end=today - datetime.timedelta(days=2)
        )
        self.assertFalse(expired_event.is_today)
        self.assertFalse(events_tags.event_is_today(expired_event))

    def test_create_event_form_validation(self):
        from events.forms import CreateEventForm
        form = CreateEventForm(data={
            'title': 'Invalid Date Event',
            'date': '10/10/2026',
            'date_end': '10/05/2026'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('date_end', form.errors)

    def test_check_expired_command_with_date_end(self):
        import datetime
        from django.core.management import call_command
        today = date.today()
        # Event 1: past start date but date_end is in the future -> NOT expired
        e1 = Event.objects.create(
            owner=self.superuser,
            title="Ongoing Event",
            date=today - datetime.timedelta(days=3),
            date_end=today + datetime.timedelta(days=2),
            is_expired=False
        )
        # Event 2: date_end in the past -> EXPIRED
        e2 = Event.objects.create(
            owner=self.superuser,
            title="Finished Multi-Day Event",
            date=today - datetime.timedelta(days=5),
            date_end=today - datetime.timedelta(days=1),
            is_expired=False
        )
        call_command('check_expired')
        e1.refresh_from_db()
        e2.refresh_from_db()
        self.assertFalse(e1.is_expired)
        self.assertTrue(e2.is_expired)

    def test_registration_close_datetime_setting_and_clear(self):
        import datetime
        from django.utils import timezone
        close_time = timezone.now() + datetime.timedelta(hours=5)
        event = services.create_event(owner=self.superuser, title="Close Reg Event", date=date(2026, 10, 1))

        cd = {
            'routes_num': 10,
            'is_published': True,
            'is_registration_open': True,
            'registration_close_datetime': close_time,
            'is_results_allowed': True,
            'is_enter_result_allowed': True,
            'is_count_only_entered_results': True,
            'is_view_full_results': True,
            'is_view_route_color': False,
            'is_view_route_grade': False,
            'is_view_route_score': True,
            'is_separate_score_by_groups': True,
            'score_type': 'SUM',
            'redpoint_points': 80,
            'flash_points_pc': 25,
            'count_routes_num': 0,
            'group_num': 1,
            'group_list': 'Общая группа',
            'set_num': 1,
            'set_list': 'Общий сет',
            'set_max_participants': 0,
            'registration_fields': [],
            'required_fields': [],
            'is_without_registration': False,
            'is_view_pin_after_registration': True,
            'is_check_result_before_enter': False,
            'is_update_result_allowed': True,
            'participant_min_age': 0,
            'reg_type_list': None,
        }
        services.update_event_settings(event=event, cd=cd)
        event.refresh_from_db()
        self.assertIsNotNone(event.registration_close_datetime)

        cd['registration_close_datetime'] = None
        services.update_event_settings(event=event, cd=cd)
        event.refresh_from_db()
        self.assertIsNone(event.registration_close_datetime)

    def test_check_close_registration_command(self):
        import datetime
        from django.utils import timezone
        from django.core.management import call_command
        now = timezone.now()

        e1 = Event.objects.create(
            owner=self.superuser,
            title="Past Close Event",
            date=date(2026, 10, 1),
            is_registration_open=True,
            registration_close_datetime=now - datetime.timedelta(hours=1)
        )
        e2 = Event.objects.create(
            owner=self.superuser,
            title="Future Close Event",
            date=date(2026, 10, 1),
            is_registration_open=True,
            registration_close_datetime=now + datetime.timedelta(hours=2)
        )
        e3 = Event.objects.create(
            owner=self.superuser,
            title="No Close Event",
            date=date(2026, 10, 1),
            is_registration_open=True,
            registration_close_datetime=None
        )

        call_command('check_close_registration')
        e1.refresh_from_db()
        e2.refresh_from_db()
        e3.refresh_from_db()

        self.assertFalse(e1.is_registration_open)
        self.assertTrue(e2.is_registration_open)
        self.assertTrue(e3.is_registration_open)

    def test_event_settings_form_registration_close_validation(self):
        from events.forms import EventSettingsForm
        event = Event.objects.create(owner=self.superuser, title="Validation Event", date=date(2026, 10, 10))
        form_invalid = EventSettingsForm(
            instance=event,
            data={
                'routes_num': 10,
                'is_published': True,
                'is_registration_open': True,
                'registration_close_datetime': '10/10/2026 12:00',
                'score_type': 'SUM',
                'redpoint_points': 80,
                'flash_points_pc': 25,
                'count_routes_num': 0,
                'group_num': 1,
                'group_list': 'Общая группа',
                'set_num': 1,
                'set_list': 'Общий сет',
                'set_max_participants': 0,
                'participant_min_age': 0,
            }
        )
        self.assertFalse(form_invalid.is_valid())
        self.assertIn('registration_close_datetime', form_invalid.errors)

        form_valid = EventSettingsForm(
            instance=event,
            data={
                'routes_num': 10,
                'is_published': True,
                'is_registration_open': True,
                'registration_close_datetime': '10/09/2026 23:00',
                'score_type': 'SUM',
                'redpoint_points': 80,
                'flash_points_pc': 25,
                'count_routes_num': 0,
                'group_num': 1,
                'group_list': 'Общая группа',
                'set_num': 1,
                'set_list': 'Общий сет',
                'set_max_participants': 0,
                'participant_min_age': 0,
            }
        )
        self.assertTrue(form_valid.is_valid())


class PlatformStatTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.superuser = CustomUser.objects.create_superuser(
            id=1,
            username='admin',
            email='admin@example.com',
            password='password123',
            premium_price=100
        )
        self.client = Client()

    def test_get_platform_stats(self):
        event = services.create_event(owner=self.superuser, title="Stat Event", date=date(2026, 10, 1))
        event.gym = "Тестовый Скалодром"
        event.is_published = True
        event.save()

        Participant.objects.create(
            first_name="Иван",
            last_name="Иванов",
            event=event,
            gender=Participant.GENDER_MALE,
            city="Москва"
        )

        stats = services.get_platform_stats()
        self.assertEqual(stats['total_events'], 1)
        self.assertEqual(stats['published_events'], 1)
        self.assertEqual(stats['total_participants'], 1)
        self.assertEqual(stats['male_participants'], 1)
        self.assertEqual(stats['female_participants'], 0)
        self.assertEqual(stats['total_cities'], 1)
        self.assertEqual(stats['total_gyms'], 1)

    def test_stat_web_view(self):
        url = reverse('stat')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Статистика платформы RockEvents")

    def test_stat_api_view(self):
        url = reverse('api_stat')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('total_events', data)
        self.assertIn('total_participants', data)
        self.assertIn('top_gyms', data)
        self.assertIn('top_cities', data)
        self.assertIn('all_gyms', data)
        self.assertIn('all_cities', data)


class ApiPatchAndValidationTests(ClimbingEventsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.superuser, title="Test Event", date=date(2026, 10, 1))
        self.participant = Participant.objects.create(
            first_name="Иван",
            last_name="Петров",
            gender=Participant.GENDER_MALE,
            birth_year=1995,
            city="тула",
            team="Скалолаз",
            event=self.event,
            pin=1234,
            set_index=0
        )
        self.client.force_login(self.superuser)

    def test_participant_patch_partial_city_update(self):
        url = f"/api/participants/{self.participant.id}/"
        response = self.client.patch(url, data={"city": "Москва"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.city, "Москва")
        self.assertEqual(self.participant.first_name, "Иван")

    def test_participant_patch_empty_team_and_city(self):
        url = f"/api/participants/{self.participant.id}/"
        response = self.client.patch(url, data={"team": "", "city": ""}, content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_enter_results_invalid_pin(self):
        url = f"/api/participants/{self.participant.id}/enter_results/"
        response = self.client.post(url, data={"pin": "invalid_pin", "accents": {}}, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())



class RoutesNumChangeTests(ClimbingEventsBaseTestCase):
    """Изменение количества трасс в настройках события и отображение их в формах ввода."""

    ROUTES_NUM = 15

    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.superuser, title="Routes Num Event", date=date(2026, 10, 1))
        self.event.is_published = True
        self.event.is_enter_result_allowed = True
        self.event.save()
        self.participant = Participant.objects.create(
            first_name='Иван',
            last_name='Иванов',
            gender=Participant.GENDER_MALE,
            birth_year=1995,
            event=self.event,
            pin=1234,
            set_index=0,
        )

    def _settings_post_data(self, routes_num):
        return {
            'routes_num': routes_num,
            'is_published': True,
            'is_registration_open': True,
            'registration_close_datetime': '',
            'is_results_allowed': True,
            'is_enter_result_allowed': True,
            'is_count_only_entered_results': True,
            'is_view_full_results': True,
            'is_view_route_color': False,
            'is_view_route_grade': False,
            'is_view_route_score': True,
            'is_separate_score_by_groups': True,
            'is_without_registration': False,
            'is_view_pin_after_registration': True,
            'is_check_result_before_enter': False,
            'is_update_result_allowed': True,
            'score_type': Event.SCORE_SIMPLE_SUM,
            'redpoint_points': 80,
            'flash_points_pc': 25,
            'count_routes_num': 0,
            'group_num': 1,
            'group_list': 'Общая группа',
            'set_num': 1,
            'set_list': 'Общий сет',
            'set_max_participants': 0,
            'registration_fields': [],
            'required_fields': [],
            'participant_min_age': 0,
            'reg_type_list': '',
        }

    def _save_routes_num_via_settings_page(self, routes_num, **overrides):
        data = self._settings_post_data(routes_num)
        data.update(overrides)
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('admin_settings', args=[self.event.id]), data=data)
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()

    def test_routes_created_after_routes_num_increased_via_settings_page(self):
        self._save_routes_num_via_settings_page(self.ROUTES_NUM)
        self.assertEqual(self.event.routes_num, self.ROUTES_NUM)
        self.assertEqual(Route.objects.filter(event=self.event).count(), self.ROUTES_NUM)

    def test_routes_recreated_after_routes_num_decreased_via_settings_page(self):
        self._save_routes_num_via_settings_page(5)
        self.assertEqual(self.event.routes_num, 5)
        self.assertEqual(Route.objects.filter(event=self.event).count(), 5)
        self.assertEqual(
            list(Route.objects.filter(event=self.event).order_by('number').values_list('number', flat=True)),
            [1, 2, 3, 4, 5])

    def test_entry_config_reports_all_routes(self):
        self._save_routes_num_via_settings_page(self.ROUTES_NUM)
        self.client.logout()
        response = self.client.get(reverse('api_events-entry-config', args=[self.event.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['routes_num'], self.ROUTES_NUM)

    def test_entry_results_cover_all_routes(self):
        self._save_routes_num_via_settings_page(self.ROUTES_NUM)
        self.client.logout()
        response = self.client.post(reverse('api_events-entry-identify', args=[self.event.id]),
                                    data={'pin': 1234}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), self.ROUTES_NUM)

    def test_score_type_change_via_settings_page_updates_results(self):
        # флэш на всех трассах: SUM даёт 1.0 * 1.25 * 80 = 100 за трассу, NUM даёт 100 + 1 = 101
        services.enter_results(event=self.event, participant=self.participant,
                               accents={str(i): {'top': 1, 'zone': 1} for i in range(self.event.routes_num)})
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.score, 100 * self.event.routes_num)

        data = self._settings_post_data(self.event.routes_num)
        data['score_type'] = Event.SCORE_NUM_ACCENTS
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('admin_settings', args=[self.event.id]), data=data)
        self.assertEqual(response.status_code, 302)
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.score, 101 * self.event.routes_num)


def _make_image_bytes(size, fmt='JPEG', mode='RGB', color='red', **save_kwargs) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


class PosterTests(ClimbingEventsBaseTestCase):
    def setUp(self):
        super().setUp()
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        media_override = self.settings(MEDIA_ROOT=media.name)
        media_override.enable()
        self.addCleanup(media_override.disable)
        self.event = services.create_event(owner=self.superuser, title='Poster Event', date=datetime(2026, 10, 1))

    def _post_description(self, poster):
        self.client.force_login(self.superuser)
        return self.client.post(reverse('admin_description', args=[self.event.id]), data={
            'title': 'Poster Event',
            'gym': 'Скалодром',
            'date': '10/01/2026',
            'description': 'Регламент',
            'short_description': 'Кратко',
            'poster': poster,
        })

    def test_compress_poster_resizes_to_webp(self):
        f = ContentFile(_make_image_bytes((4000, 3000)), name='афиша.jpg')
        result = img_tools.compress_poster(f)
        self.assertEqual(result.name, 'афиша.webp')
        with Image.open(result) as img:
            self.assertEqual(img.format, 'WEBP')
            self.assertEqual(img.size, (img_tools.POSTER_MAX_SIDE, 1200))

    def test_compress_poster_applies_exif_orientation(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation: повернуть на 90°
        f = ContentFile(_make_image_bytes((4000, 3000), exif=exif.tobytes()), name='photo.jpg')
        with Image.open(img_tools.compress_poster(f)) as img:
            self.assertEqual(img.size, (1200, img_tools.POSTER_MAX_SIDE))

    def test_compress_poster_keeps_transparency(self):
        f = ContentFile(_make_image_bytes((800, 600), fmt='PNG', mode='RGBA', color=(255, 0, 0, 128)), name='logo.png')
        with Image.open(img_tools.compress_poster(f)) as img:
            self.assertEqual(img.mode, 'RGBA')
            self.assertEqual(img.size, (800, 600))

    def test_description_view_saves_compressed_poster(self):
        poster = SimpleUploadedFile('poster.png', _make_image_bytes((2000, 3000), fmt='PNG'), 'image/png')
        response = self._post_description(poster)
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertTrue(self.event.poster.name.startswith('posters/'))
        self.assertTrue(self.event.poster.name.endswith('.webp'))
        self.assertEqual((self.event.poster.width, self.event.poster.height), (1067, img_tools.POSTER_MAX_SIDE))

    def test_description_view_rejects_too_many_pixels(self):
        poster = SimpleUploadedFile('poster.jpg', _make_image_bytes((200, 200)), 'image/jpeg')
        with mock.patch.object(img_tools, 'POSTER_MAX_PIXELS', 100 * 100):
            response = self._post_description(poster)
        self.assertEqual(response.status_code, 200)
        self.assertIn('poster', response.context['form'].errors)
        self.event.refresh_from_db()
        self.assertFalse(self.event.poster.name.startswith('posters/'))

    def test_description_view_keeps_poster_without_upload(self):
        self.event.poster.save('old.webp', ContentFile(_make_image_bytes((100, 100), fmt='WEBP')))
        old_name = self.event.poster.name
        response = self._post_description('')
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.poster.name, old_name)

    def test_compress_posters_command(self):
        self.event.poster.save('big.jpg', ContentFile(_make_image_bytes((3000, 4000))))
        old_name = self.event.poster.name
        storage = self.event.poster.storage
        default_event = services.create_event(owner=self.superuser, title='Default', date=datetime(2026, 10, 1))
        default_poster = default_event.poster.name

        call_command('compress_posters', '--dry-run', stdout=io.StringIO())
        self.event.refresh_from_db()
        self.assertEqual(self.event.poster.name, old_name)

        call_command('compress_posters', stdout=io.StringIO())
        self.event.refresh_from_db()
        self.assertTrue(self.event.poster.name.endswith('.webp'))
        self.assertEqual((self.event.poster.width, self.event.poster.height), (1200, img_tools.POSTER_MAX_SIDE))
        self.assertFalse(storage.exists(old_name))
        default_event.refresh_from_db()
        self.assertEqual(default_event.poster.name, default_poster)

        compressed_name = self.event.poster.name
        call_command('compress_posters', stdout=io.StringIO())
        self.event.refresh_from_db()
        self.assertEqual(self.event.poster.name, compressed_name)
