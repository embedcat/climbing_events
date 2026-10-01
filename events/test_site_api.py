from datetime import date

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from events import services
from events.models import Participant
from events.tests import ClimbingEventsBaseTestCase


def ref(*ids):
    """ Запись браузера для /api/site/participations/: «событие:участник» """
    return ':'.join(str(i) for i in ids)


class SiteApiBase(ClimbingEventsBaseTestCase):
    def make_event(self, title='Событие', day=date(2026, 10, 4), owner=None, published=True, **fields):
        event = services.create_event(owner=owner or self.user, title=title, date=day)
        event.is_published = published
        for name, value in fields.items():
            setattr(event, name, value)
        event.save()
        return event

    def events(self, **query):
        response = self.client.get(reverse('api_site_events'), query)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def titles(self, **query):
        return [card['title'] for card in self.events(**query)['results']]


class CatalogTests(SiteApiBase):
    def test_guest_sees_only_published_events(self):
        self.make_event('Видно')
        self.make_event('Черновик', published=False)
        self.assertEqual(self.titles(), ['Видно'])

    def test_upcoming_are_nearest_first_and_past_are_freshest_first(self):
        self.make_event('Позже', day=date(2026, 12, 1))
        self.make_event('Раньше', day=date(2026, 10, 4))
        self.make_event('Старое', day=date(2026, 5, 1), is_expired=True)
        self.make_event('Недавнее', day=date(2026, 9, 1), is_expired=True)
        self.assertEqual(self.titles(), ['Раньше', 'Позже'])
        self.assertEqual(self.titles(when='past'), ['Недавнее', 'Старое'])

    def test_live_event_comes_first_even_if_it_is_not_the_nearest(self):
        self.make_event('Скоро', day=date(2026, 10, 4))
        self.make_event('Идёт', day=date(2026, 12, 1), is_enter_result_allowed=True)
        self.assertEqual(self.titles(), ['Идёт', 'Скоро'])

    def test_counts_follow_the_search(self):
        self.make_event('Осенний фестиваль')
        self.make_event('Зимний кубок')
        self.make_event('Осенний прошлый', is_expired=True)
        self.assertEqual(self.events()['counts'], {'upcoming': 2, 'past': 1})
        self.assertEqual(self.events(q='осенний')['counts'], {'upcoming': 1, 'past': 1})

    def test_search_looks_in_title_and_gym(self):
        self.make_event('Фестиваль', gym='Скалодром «Сходня»')
        self.make_event('Кубок', gym='Вертикаль')
        self.assertEqual(self.titles(q='сходня'), ['Фестиваль'])
        self.assertEqual(self.titles(q='куб'), ['Кубок'])
        self.assertEqual(self.titles(q='нет такого'), [])

    def test_pages_by_offset(self):
        for i in range(14):
            self.make_event('Событие %02d' % i, day=date(2026, 11, 1 + i))
        first = self.events()
        self.assertEqual(len(first['results']), services.SITE_PAGE_SIZE)
        self.assertTrue(first['has_more'])
        rest = self.events(offset=services.SITE_PAGE_SIZE)
        self.assertEqual([c['title'] for c in rest['results']], ['Событие 12', 'Событие 13'])
        self.assertFalse(rest['has_more'])

    def test_bad_offset_is_treated_as_zero(self):
        self.make_event('Событие')
        self.assertEqual(self.titles(offset='abc'), ['Событие'])
        self.assertEqual(self.titles(offset=-5), ['Событие'])

    def test_card_fields_and_stages(self):
        reg = self.make_event('Регистрация', is_registration_open=True)
        live = self.make_event('Идёт', day=date(2026, 10, 5), is_enter_result_allowed=True)
        closed = self.make_event('Закрыта', day=date(2026, 10, 6))
        done = self.make_event('Завершено', day=date(2026, 10, 7), is_expired=True)
        stages = {c['id']: c['stage'] for c in self.events()['results'] + self.events(when='past')['results']}
        self.assertEqual(stages, {reg.id: 'reg', live.id: 'live', closed.id: 'reg_closed', done.id: 'done'})
        card = self.events()['results'][0]
        for key in ('id', 'title', 'date', 'gym', 'short_description', 'poster', 'stage', 'is_results_allowed',
                    'is_without_registration', 'mine'):
            self.assertIn(key, card)
        self.assertNotIn('owner', card)

    def test_stage_over_when_entry_is_closed_but_someone_entered(self):
        event = self.make_event('Ввод закрыт')
        Participant.objects.create(first_name='Иван', last_name='Иванов', gender=Participant.GENDER_MALE, event=event,
                                   pin=1111, is_entered_result=True)
        self.assertEqual(self.events()['results'][0]['stage'], 'over')

    def test_full_event_shows_registration_closed(self):
        event = self.make_event('Мест нет', is_registration_open=True, set_max_participants=1, set_num=1)
        Participant.objects.create(first_name='Иван', last_name='Иванов', gender=Participant.GENDER_MALE, event=event,
                                   pin=1111)
        self.assertEqual(self.events()['results'][0]['stage'], 'reg_closed')

    def test_organizer_sees_own_draft_marked_but_not_someone_elses(self):
        self.make_event('Мой черновик', owner=self.user, published=False)
        self.make_event('Чужой черновик', owner=self.superuser, published=False)
        self.client.force_login(self.user)
        cards = self.events()['results']
        self.assertEqual([(c['title'], c['stage'], c['mine']) for c in cards], [('Мой черновик', 'draft', True)])

    def test_superuser_sees_everything(self):
        self.make_event('Первое', published=False)
        self.make_event('Второе')
        self.client.force_login(self.superuser)
        self.assertEqual(sorted(self.titles()), ['Второе', 'Первое'])

    def test_query_count_does_not_grow_with_the_page(self):
        for i in range(10):
            self.make_event(f'Событие {i}', day=date(2026, 11, 1 + i))
        with CaptureQueriesContext(connection) as queries:
            self.events()
        self.assertLessEqual(len(queries), 6, [q['sql'] for q in queries])


class ParticipationsTests(SiteApiBase):
    def setUp(self):
        super().setUp()
        self.event = self.make_event('Фестиваль', is_registration_open=True, group_num=2, group_list='Новички, Спорт',
                                     set_num=2, set_list='10:00, 13:00')
        self.person = Participant.objects.create(
            first_name='Юлия', last_name='Зайцева', gender=Participant.GENDER_FEMALE, event=self.event, pin=2222,
            group_index=1, set_index=1)

    def get(self, refs):
        response = self.client.get(reverse('api_site_participations'), {'refs': refs})
        self.assertEqual(response.status_code, 200)
        return response.json()['results']

    def test_event_without_participant_has_no_me(self):
        items = self.get(str(self.event.id))
        self.assertEqual(items[0]['event']['id'], self.event.id)
        self.assertIsNone(items[0]['me'])

    def test_participant_gets_payment_status_group_and_set(self):
        items = self.get(ref(self.event.id, self.person.id))
        self.assertEqual(items[0]['me'], {
            'paid': False, 'pay_required': False, 'standing': None, 'group': 'Спорт', 'set': '13:00',
            'set_index': 1})

    def test_standing_appears_only_when_results_are_open_and_entered(self):
        self.person.is_entered_result = True
        self.person.place = 1
        self.person.save()
        self.assertIsNone(self.get(ref(self.event.id, self.person.id))[0]['me']['standing'])
        self.event.is_results_allowed = True
        self.event.save()
        self.assertEqual(self.get(ref(self.event.id, self.person.id))[0]['me']['standing'], {'place': 1, 'of': 1})

    def test_participant_of_another_event_is_ignored(self):
        other = self.make_event('Другое')
        items = self.get(ref(other.id, self.person.id))
        self.assertIsNone(items[0]['me'])

    def test_unpublished_and_missing_events_are_skipped(self):
        draft = self.make_event('Черновик', published=False)
        self.assertEqual(self.get(ref(draft.id) + ',999999'), [])

    def test_garbage_refs_are_ignored_and_the_list_is_capped(self):
        self.assertEqual(self.get('abc,1:x,:5,,'), [])
        refs = ','.join(str(self.event.id) for _ in range(services.SITE_MAX_REFS + 10))
        self.assertEqual(len(self.get(refs)), services.SITE_MAX_REFS)


class MyEventsTests(SiteApiBase):
    def get(self, **query):
        return self.client.get(reverse('api_site_my_events'), query)

    def test_requires_login(self):
        self.assertIn(self.get().status_code, (401, 403))

    def test_organizer_gets_own_events_with_counts(self):
        mine = self.make_event('Моё', is_pay_allowed=True)
        self.make_event('Чужое', owner=self.superuser)
        Participant.objects.create(first_name='Иван', last_name='Иванов', gender=Participant.GENDER_MALE, event=mine,
                                   pin=1111, is_entered_result=True, paid=True)
        Participant.objects.create(first_name='Пётр', last_name='Петров', gender=Participant.GENDER_MALE, event=mine,
                                   pin=2222)
        self.client.force_login(self.user)
        data = self.get().json()
        self.assertEqual(data['scope'], 'mine')
        self.assertFalse(data['is_superuser'])
        self.assertEqual(len(data['results']), 1)
        card = data['results'][0]
        self.assertEqual((card['title'], card['participants_count'], card['entered_count'], card['paid_count']),
                         ('Моё', 2, 1, 1))
        self.assertTrue(card['is_pay_allowed'])
        self.assertIsNone(card['owner'])

    def test_drafts_are_listed_for_their_owner(self):
        self.make_event('Черновик', published=False)
        self.client.force_login(self.user)
        self.assertEqual(self.get().json()['results'][0]['stage'], 'draft')

    def test_superuser_can_switch_to_all_events_with_owners(self):
        self.make_event('Первое', owner=self.user)
        self.make_event('Второе', owner=self.superuser)
        self.client.force_login(self.superuser)
        self.assertEqual([c['title'] for c in self.get().json()['results']], ['Второе'])
        data = self.get(scope='all').json()
        self.assertEqual(data['scope'], 'all')
        self.assertEqual(sorted((c['title'], c['owner']) for c in data['results']),
                         [('Второе', 'admin@example.com'), ('Первое', 'user@example.com')])

    def test_scope_all_is_ignored_for_ordinary_organizer(self):
        self.make_event('Моё', owner=self.user)
        self.make_event('Чужое', owner=self.superuser)
        self.client.force_login(self.user)
        data = self.get(scope='all').json()
        self.assertEqual(data['scope'], 'mine')
        self.assertEqual([c['title'] for c in data['results']], ['Моё'])
