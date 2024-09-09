from datetime import datetime
from django.test import TestCase, SimpleTestCase
import events.services as services
from events.models import CustomUser, Event, Participant, Route

class IsRegistrationOpenTestCase(TestCase):
    def setUp(self) -> None:
        superuser = CustomUser.objects.create(id=1)
        self.event = services.create_event(owner=superuser, title="test event", date=datetime.now())
        return super().setUp()
    
    def test_not_published(self):
        self.assertFalse(services.is_registration_open(self.event))

    def test_not_opened_registration(self):
        self.event.is_published = True
        self.assertFalse(services.is_registration_open(self.event))

    def test_too_many_participants_in_sets(self):
        services.debug_create_participants(self.event, 10)
        self.event.is_published = True
        self.event.is_registration_open = True
        self.event.set_num = 1
        self.event.set_max_participants = 10
        self.assertFalse(services.is_registration_open(self.event))
        self.event.set_num = 2
        self.event.set_max_participants = 5
        self.assertFalse(services.is_registration_open(self.event))
        self.event.set_max_participants = 11
        self.assertTrue(services.is_registration_open(self.event))

    def test_too_many_participants_no_premium(self):
        services.debug_create_participants(self.event, 10)
        self.event.is_published = True
        self.event.is_registration_open = True
        self.event.set_num = 1
        self.event.max_participants = 10
        self.assertFalse(services.is_registration_open(self.event))

    def test_too_many_participants_premium(self):
        services.debug_create_participants(self.event, 10)
        self.event.is_published = True
        self.event.is_registration_open = True
        self.event.set_num = 1
        self.event.max_participants = 10
        self.event.is_premium = True
        self.assertTrue(services.is_registration_open(self.event))
        self.event.set_num = 1
        self.event.set_max_participants = 10
        self.assertFalse(services.is_registration_open(self.event))

