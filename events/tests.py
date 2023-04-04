from django.test import TestCase, SimpleTestCase
import events.services as services
from events.models import Event, Participant, Route

TEST_RESULT_FORM_DATA = [{'top': 2, 'zone': 0}, {'top': 0, 'zone': 2}]


class Test(SimpleTestCase):
    def test_form_data_to_results(self):
        self.assertDictEqual(services.form_data_to_results(form_cleaned_data=TEST_RESULT_FORM_DATA), {
                             0: {'top': 2, 'zone': 0}, 1: {'top': 0, 'zone': 2}})
