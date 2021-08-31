from django.test import TestCase
import events.services as services
from events.models import Event, Participant, Route, Accent

SET_NUM = 5
SET_LIST_STR = 'set1,2set2,      s.et3  ,    сет № 4         ,#set5'
SET_LIST = ['set1', '2set2', 's.et3', 'сет № 4', '#set5']
GROUP_NUM = 3
GROUP_LIST_STR = 'gr1,gr    2   ,      gr3'
GROUP_LIST = ['gr1', 'gr    2', 'gr3']


class Test(TestCase):
    def setUp(self) -> None:
        self.event = Event.objects.create(
            title='test_event',
            date='2022-01-01',
            poster='',
            description='description',
            routes_num=10,
            is_published=True,
            is_registration_open=True,
            is_results_allowed=True,
            is_enter_result_allowed=True,
            is_count_only_entered_results=True,
            is_view_full_results=True,
            score_type=Event.SCORE_SIMPLE_SUM,
            flash_points=100,
            redpoint_points=80,
            group_num=GROUP_NUM,
            group_list=GROUP_LIST_STR,
            set_num=SET_NUM,
            set_list=SET_LIST_STR,
            set_max_participants=5,
        )

    def test_create_event_routes(self):
        services.create_event_routes(self.event)
        self.assertEqual(self.event.route.count(), self.event.routes_num)

    def test_event_create(self):
        self.assertEqual(Event.objects.count(), 1)

    def test_create_participant(self):
        services.debug_create_random_participant(event=self.event)
        self.assertEqual(self.event.participant.count(), 1)

    def test_create_default_accents(self):
        p = services.debug_create_random_participant(self.event)
        services.create_event_routes(self.event)
        services.create_default_accents(self.event, p)
        self.assertEqual(p.accent.count(), self.event.routes_num)

    def test_clear_participants(self):
        p = services.debug_create_random_participant(self.event)
        services.create_event_routes(self.event)
        services.create_default_accents(self.event, p)
        services.clear_participants(self.event)
        self.assertEqual(self.event.participant.count(), 0)
        self.assertEqual(self.event.accent.count(), 0)

    def test_get_set_list(self):
        self.assertListEqual(SET_LIST, services.get_set_list(self.event))

    def test_get_group_list(self):
        self.assertListEqual(GROUP_LIST, services.get_group_list(self.event))

    def test_get_set_list_for_registration_available(self):
        self.event.set_max_participants = 0
        self.assertListEqual(SET_LIST, services.get_set_list_for_registration_available(self.event))
        self.event.set_max_participants = 1
        services.create_participant(event=self.event, first_name='test', last_name='test', set_index=0)
        self.assertListEqual(SET_LIST[1:], services.get_set_list_for_registration_available(self.event))
        for i in range(self.event.set_num):
            services.create_participant(event=self.event, first_name='test', last_name='test', set_index=i)
        self.assertListEqual([], services.get_set_list_for_registration_available(self.event))

    def test_check_participants_number_to_close_registration(self):
        self.event.is_registration_open = True
        self.event.set_max_participants = 0
        services.check_participants_number_to_close_registration(self.event)
        self.assertTrue(self.event.is_registration_open)

        self.event.set_max_participants = 1
        self.event.set_num = 1
        self.event.is_registration_open = True
        services.debug_create_random_participant(self.event)
        services.check_participants_number_to_close_registration(self.event)
        self.assertFalse(self.event.is_registration_open)

        services.clear_participants(self.event)
        self.event.set_max_participants = 1
        self.event.set_num = 2
        self.event.is_registration_open = True
        services.create_participant(event=self.event, first_name='test', last_name='test', set_index=0)
        services.check_participants_number_to_close_registration(self.event)
        self.assertTrue(self.event.is_registration_open)

        services.clear_participants(self.event)
        self.event.set_max_participants = 1
        self.event.set_num = 2
        self.event.is_registration_open = True
        services.create_participant(event=self.event, first_name='test', last_name='test', set_index=0)
        services.create_participant(event=self.event, first_name='test', last_name='test', set_index=1)
        services.check_participants_number_to_close_registration(self.event)
        self.assertFalse(self.event.is_registration_open)

    def test_get_route_points(self):
        services.create_event_routes(self.event)
        route = self.event.route.get(number=1)
        # no participants:
        self.assertDictEqual(services.get_route_point(self.event, route), {'male': 1, 'female': 1})

        # simple score:
        self.event.score_type = Event.SCORE_SIMPLE_SUM
        self.assertDictEqual(services.get_route_point(self.event, route), {'male': 1, 'female': 1})
        self.event.score_type = Event.SCORE_PROPORTIONAL

        # no accents:
        pm = services.create_participant(event=self.event, first_name='test', last_name='test', gender=Participant.GENDER_MALE)
        pf = services.create_participant(event=self.event, first_name='test', last_name='test', gender=Participant.GENDER_FEMALE)
        self.assertDictEqual(services.get_route_point(self.event, route), {'male': 1, 'female': 1})

        # no results
        services.create_default_accents(self.event, pm)
        services.create_default_accents(self.event, pf)
        self.assertDictEqual(services.get_route_point(self.event, route), {'male': 1, 'female': 1})

        # 1 accent:
        pma = Accent.objects.filter(participant=pm, event=self.event)[0]
        services.save_accent(pma, Accent.ACCENT_FLASH, route)
        pfa = Accent.objects.filter(participant=pf, event=self.event)[0]
        services.save_accent(pfa, Accent.ACCENT_REDPOINT, route)
        self.assertDictEqual(services.get_route_point(self.event, route), {'male': 1, 'female': 1})

        # 2 accents:
        pm2 = services.create_participant(event=self.event, first_name='test', last_name='test', gender=Participant.GENDER_MALE)
        pf2 = services.create_participant(event=self.event, first_name='test', last_name='test', gender=Participant.GENDER_FEMALE)
        services.create_default_accents(self.event, pm2)
        services.create_default_accents(self.event, pf2)
        pm2a = Accent.objects.filter(participant=pm2, event=self.event)[0]
        services.save_accent(pm2a, Accent.ACCENT_REDPOINT, route)
        pf2a = Accent.objects.filter(participant=pf2, event=self.event)[0]
        services.save_accent(pf2a, Accent.ACCENT_FLASH, route)
        self.assertDictEqual(services.get_route_point(self.event, route), {'male': 0.5, 'female': 0.5})

    def test_get_participant_score(self):
        self.event.score_type = Event.SCORE_PROPORTIONAL
        services.create_event_routes(self.event)
        pm = services.create_participant(event=self.event, first_name='test', last_name='test', gender=Participant.GENDER_MALE)
        pf = services.create_participant(event=self.event, first_name='test', last_name='test', gender=Participant.GENDER_FEMALE)

        # no accents:
        self.assertEqual(services.get_participant_score(self.event, pm), 0)
        self.assertEqual(services.get_participant_score(self.event, pf), 0)

        # all accents:
        services.create_default_accents(self.event, pm)
        services.create_default_accents(self.event, pf)
        for index, accent in enumerate(Accent.objects.filter(participant=pm, event=self.event)):
            services.save_accent(accent, Accent.ACCENT_FLASH, Route.objects.get(event=self.event, number=index + 1))
        for index, accent in enumerate(Accent.objects.filter(participant=pf, event=self.event)):
            services.save_accent(accent, Accent.ACCENT_REDPOINT, Route.objects.get(event=self.event, number=index + 1))
        self.assertEqual(services.get_participant_score(self.event, pm), self.event.routes_num * self.event.flash_points)
        self.assertEqual(services.get_participant_score(self.event, pf), self.event.routes_num * self.event.redpoint_points)

        # 2 participants, all accents:
        pm2 = services.create_participant(event=self.event, first_name='test', last_name='test', gender=Participant.GENDER_MALE)
        pf2 = services.create_participant(event=self.event, first_name='test', last_name='test', gender=Participant.GENDER_FEMALE)
        services.create_default_accents(self.event, pm2)
        services.create_default_accents(self.event, pf2)
        for index, accent in enumerate(Accent.objects.filter(participant=pm2, event=self.event)):
            services.save_accent(accent, Accent.ACCENT_FLASH, Route.objects.get(event=self.event, number=index + 1))
        for index, accent in enumerate(Accent.objects.filter(participant=pf2, event=self.event)):
            services.save_accent(accent, Accent.ACCENT_REDPOINT, Route.objects.get(event=self.event, number=index + 1))
        self.event.score_type = Event.SCORE_SIMPLE_SUM
        self.assertEqual(services.get_participant_score(self.event, pm), self.event.routes_num * self.event.flash_points)
        self.assertEqual(services.get_participant_score(self.event, pf), self.event.routes_num * self.event.redpoint_points)
        self.event.score_type = Event.SCORE_PROPORTIONAL
        self.assertEqual(services.get_participant_score(self.event, pm), self.event.routes_num * self.event.flash_points / 2)
        self.assertEqual(services.get_participant_score(self.event, pf), self.event.routes_num * self.event.redpoint_points / 2)
