from datetime import datetime, date
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db.utils import IntegrityError
from events.models import CustomUser, Event, Participant, Route, Wallet, PromoCode, PayDetail
from events import services
from events.forms import ParticipantRegistrationForm, CreateEventForm
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


class FormsTestCase(ClimbingEventsBaseTestCase):
    def test_participant_registration_form_fields(self):
        event = services.create_event(owner=self.superuser, title="Form Event", date=datetime(2026, 10, 1))
        # Explicitly configure fields for form rendering
        event.registration_fields = [Event.FIELD_GENDER, Event.FIELD_BIRTH_YEAR, Event.FIELD_EMAIL]
        event.required_fields = [Event.FIELD_BIRTH_YEAR]
        event.save()
        
        form = ParticipantRegistrationForm(
            group_list=services.get_group_list(event),
            set_list=services.get_set_list(event),
            registration_fields=services.get_registration_fields(event),
            required_fields=services.get_registration_required_fields(event),
            is_enter_form=False,
            reg_type_list=event.reg_type_list
        )
        self.assertIn('first_name', form.fields)
        self.assertIn('last_name', form.fields)
        self.assertIn('gender', form.fields)
        self.assertIn('birth_year', form.fields)
        self.assertIn('email', form.fields)
        self.assertTrue(form.fields['birth_year'].required)
        self.assertFalse(form.fields['gender'].required)


class ViewsTestCase(ClimbingEventsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.superuser, title="View Event", date=datetime(2026, 10, 1))
        self.event.is_published = True
        self.event.is_registration_open = True
        self.event.save()

    def test_main_view_pagination(self):
        # We need multiple events to test pagination. 
        # By default, views.py has `Paginator(events, 9)`
        # Let's create 11 published events
        for i in range(11):
            e = services.create_event(owner=self.superuser, title=f"Event {i}", date=datetime(2026, 10, 1))
            e.is_published = True
            e.save()

        # Request first page
        response = self.client.get(reverse('main'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('events', response.context)
        # Should display 9 events on page 1
        self.assertEqual(len(response.context['events']), 9)
        self.assertTrue(response.context['events'].has_other_pages())

        # Request second page
        response_page2 = self.client.get(reverse('main') + '?page=2')
        self.assertEqual(response_page2.status_code, 200)
        # Should display 3 events on page 2 (12 total events)
        self.assertEqual(len(response_page2.context['events']), 3)

    def test_registration_view_get_post(self):
        url = reverse('registration', kwargs={'event_id': self.event.id})
        
        # GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'events/event/registration.html')

        # POST request (successful registration)
        post_data = {
            'first_name': 'Алексей',
            'last_name': 'Алексеев',
            'gender': Participant.GENDER_MALE,
            'birth_year': 1990,
            'city': 'Москва',
            'team': 'Скала',
            'grade': Participant.GRADE_BR,
            'email': 'alex@example.com',
            'phone_number': '+79998887766'
        }
        response_post = self.client.post(url, data=post_data)
        # Redirect to event_registration_ok view
        self.assertEqual(response_post.status_code, 302)
        
        # Check participant is registered
        self.assertEqual(Participant.objects.filter(event=self.event, last_name='Алексеев').count(), 1)

    def test_enter_results_view_successful_post(self):
        p = Participant.objects.create(
            first_name='Николай',
            last_name='Николаев',
            gender=Participant.GENDER_MALE,
            event=self.event,
            pin=5555
        )
        url = reverse('enter_results', kwargs={'event_id': self.event.id})
        
        # Prepare formset POST data for 10 routes.
        # Django formset requires management form data:
        post_data = {
            'participant-pin': '5555',
            'accents-TOTAL_FORMS': '10',
            'accents-INITIAL_FORMS': '10',
            'accents-MIN_NUM_FORMS': '0',
            'accents-MAX_NUM_FORMS': '1000',
        }
        for i in range(10):
            post_data[f'accents-{i}-label'] = str(i)
            # Route 0: Top = 1 (Flash)
            # Others: Top = 0 (No Accent)
            post_data[f'accents-{i}-top'] = '1' if i == 0 else '0'
            post_data[f'accents-{i}-zone'] = '1' if i == 0 else '0'

        response = self.client.post(url, data=post_data)
        # Should redirect to enter_results_ok view
        self.assertEqual(response.status_code, 302)

        # Check participant has results entered
        p.refresh_from_db()
        self.assertTrue(p.is_entered_result)
        self.assertEqual(p.french_accents.get("0"), {"top": 1, "zone": 1})


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

