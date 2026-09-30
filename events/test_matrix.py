from datetime import date

from django.test import override_settings
from django.urls import reverse

from events import services
from events.models import Event, Participant
from events.tests import ClimbingEventsBaseTestCase


class MatrixTestBase(ClimbingEventsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.user, title='Matrix Event', date=date(2026, 10, 1))
        self.event.is_published = True
        self.event.score_type = Event.SCORE_PROPORTIONAL
        self.event.save()
        self.client.force_login(self.user)

    def set_event(self, **fields):
        for name, value in fields.items():
            setattr(self.event, name, value)
        self.event.save()

    def make(self, last, first='Имя', gender=Participant.GENDER_MALE, group=0, result=None, **extra):
        participant = Participant.objects.create(
            event=self.event, last_name=last, first_name=first, gender=gender, group_index=group,
            pin=extra.pop('pin', 1000 + Participant.objects.count()), **extra)
        if result is not None:
            services.enter_results(event=self.event, participant=participant, accents=result)
            participant.refresh_from_db()
        return participant

    @property
    def url(self):
        return reverse('api_events-matrix', args=[self.event.id])

    @property
    def save_url(self):
        return reverse('api_events-matrix-save', args=[self.event.id])

    def save(self, changes):
        return self.client.post(self.save_url, data={'changes': changes}, content_type='application/json')


def cell(top, zone=None):
    return {'top': top} if zone is None else {'top': top, 'zone': zone}


class MatrixPayloadTests(MatrixTestBase):
    def test_participants_with_pin_and_results(self):
        self.set_event(group_num=2, group_list='Новички, Спорт', set_num=2, set_list='Утро, Вечер')
        self.make('Яковлев', pin=4321, group=1, set_index=1, result={'0': {'top': 2, 'zone': 2}})
        self.make('Андреев', pin=1234)
        data = self.client.get(self.url).json()
        self.assertEqual([p['last_name'] for p in data['participants']], ['Андреев', 'Яковлев'])
        first, second = data['participants']
        self.assertEqual((first['pin'], first['is_entered_result'], first['place']), (1234, False, None))
        self.assertEqual(first['results'], [{'top': 0, 'zone': 0}] * 10)
        self.assertEqual((second['pin'], second['group_index'], second['set_index'], second['place']), (4321, 1, 1, 1))
        self.assertEqual(second['results'][0], {'top': 2, 'zone': 0})
        self.assertEqual(data['event']['groups'], ['Новички', 'Спорт'])
        self.assertEqual(data['event']['sets'], [{'index': 0, 'name': 'Утро'}, {'index': 1, 'name': 'Вечер'}])
        self.assertEqual((data['event']['routes_num'], data['event']['score_type']), (10, 'PROP'))

    def test_only_the_organizer_sees_it(self):
        self.make('Андреев')
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(self.url).status_code, 200)

        other = services.create_event(owner=self.superuser, title='Other', date=date(2026, 10, 2))
        self.client.force_login(self.user)
        other.is_published = True
        other.save()
        response = self.client.get(reverse('api_events-matrix', args=[other.id]))
        self.assertEqual(response.status_code, 403)

        self.client.logout()
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_pin_never_leaks_to_other_users(self):
        self.make('Андреев', pin=7777)
        outsider = self.superuser.__class__.objects.create_user(id=3, username='outsider', password='password123')
        self.client.force_login(outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('7777', response.content.decode())


class MatrixSaveTests(MatrixTestBase):
    def test_only_changed_routes_are_written(self):
        p = self.make('Андреев', result={'0': {'top': 1, 'zone': 1}, '1': {'top': 2, 'zone': 2}})
        response = self.save([{'participant': p.id, 'results': {'2': cell(2)}}])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['saved'], {'cells': 1, 'participants': 1})
        p.refresh_from_db()
        self.assertEqual(p.french_accents['0'], {'top': 1, 'zone': 1})
        self.assertEqual(p.french_accents['1'], {'top': 2, 'zone': 2})
        self.assertEqual(p.french_accents['2'], {'top': 2, 'zone': 2})
        self.assertEqual(p.french_accents['3'], {'top': 0, 'zone': 0})

    def test_does_not_overwrite_what_participant_entered_meanwhile(self):
        """Матрица загружена, когда у участника ничего не было; потом он сам ввёл трассу 1 с телефона."""
        p = self.make('Андреев')
        data = self.client.get(self.url).json()
        self.assertFalse(data['participants'][0]['is_entered_result'])
        services.enter_results(event=self.event, participant=p, accents={'0': {'top': 1, 'zone': 1}})
        self.save([{'participant': p.id, 'results': {'4': cell(2)}}])
        p.refresh_from_db()
        self.assertEqual(p.french_accents['0'], {'top': 1, 'zone': 1})
        self.assertEqual(p.french_accents['4'], {'top': 2, 'zone': 2})

    def test_participant_without_result_becomes_entered_even_with_only_zeros(self):
        p = self.make('Андреев')
        self.assertFalse(p.is_entered_result)
        data = self.save([{'participant': p.id, 'results': {'0': cell(0), '1': cell(0)}}]).json()
        p.refresh_from_db()
        self.assertTrue(p.is_entered_result)
        row = data['participants'][0]
        self.assertTrue(row['is_entered_result'])
        self.assertEqual(row['place'], 1)

    def test_scores_and_places_are_recalculated_for_affected_groups(self):
        self.set_event(group_num=2, group_list='Новички, Спорт')
        a = self.make('Андреев', result={'0': {'top': 2, 'zone': 2}})
        b = self.make('Борисов', result={'1': {'top': 2, 'zone': 2}})
        untouched = self.make('Власов', group=1, result={'0': {'top': 2, 'zone': 2}})
        before = Participant.objects.get(id=untouched.id).score
        data = self.save([{'participant': b.id, 'results': {'0': cell(2), '2': cell(2)}}]).json()
        rows = {row['last_name']: row for row in data['participants']}
        self.assertEqual(rows['Борисов']['place'], 1)
        self.assertEqual(rows['Андреев']['place'], 2)
        self.assertGreater(rows['Борисов']['score'], rows['Андреев']['score'])
        self.assertEqual(Participant.objects.get(id=untouched.id).score, before)
        a.refresh_from_db()
        self.assertEqual(a.place, 2)

    def test_many_participants_in_one_request(self):
        people = [self.make(f'Фамилия{i}') for i in range(3)]
        response = self.save([{'participant': p.id, 'results': {'0': cell(1), '1': cell(2)}} for p in people])
        self.assertEqual(response.json()['saved'], {'cells': 6, 'participants': 3})
        self.assertEqual(Participant.objects.filter(event=self.event, is_entered_result=True).count(), 3)

    def test_same_participant_twice_merges_cells(self):
        p = self.make('Андреев')
        self.save([{'participant': p.id, 'results': {'0': cell(1)}}, {'participant': p.id, 'results': {'1': cell(2)}}])
        p.refresh_from_db()
        self.assertEqual((p.french_accents['0']['top'], p.french_accents['1']['top']), (1, 2))

    def test_french_attempts(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        p = self.make('Андреев')
        self.save([{'participant': p.id, 'results': {'0': cell(3), '1': cell(0, 4), '2': cell(2, 1)}}])
        p.refresh_from_db()
        self.assertEqual(p.french_accents['0'], {'top': 3, 'zone': 3})  # топ без зоны: зона на той же попытке
        self.assertEqual(p.french_accents['1'], {'top': 0, 'zone': 4})
        self.assertEqual(p.french_accents['2'], {'top': 2, 'zone': 1})
        self.assertEqual(p.french_score, '2T5 3z8')

    def test_french_zone_later_than_top_rejects_everything(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        good = self.make('Андреев')
        bad = self.make('Борисов', first='Пётр')
        response = self.save([
            {'participant': good.id, 'results': {'0': cell(1, 1)}},
            {'participant': bad.id, 'results': {'2': cell(1, 3), '4': cell(2, 5)}},
        ])
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual((body['code'], body['routes'], body['participant']), ('invalid_results', [3, 5], bad.id))
        self.assertIn('Борисов Пётр', body['error'])
        self.assertIn('трассы 3, 5', body['error'])
        good.refresh_from_db()
        bad.refresh_from_db()
        self.assertFalse(good.is_entered_result)
        self.assertFalse(bad.is_entered_result)

    def test_old_invalid_cells_do_not_block_editing_other_routes(self):
        self.set_event(score_type=Event.SCORE_FRENCH)
        p = self.make('Андреев')
        p.french_accents = {'0': {'top': 1, 'zone': 5}}
        p.is_entered_result = True
        p.save()
        self.assertEqual(self.save([{'participant': p.id, 'results': {'1': cell(2, 2)}}]).status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.french_accents['0'], {'top': 1, 'zone': 5})

    def test_rejects_bad_values(self):
        p = self.make('Андреев')
        for results in ({'0': cell(3)}, {'0': cell(-1)}, {'0': {'top': 'x'}}, {'0': 'text'}, {'10': cell(1)},
                        {'-1': cell(1)}, {'abc': cell(1)}):
            response = self.save([{'participant': p.id, 'results': results}])
            self.assertEqual(response.status_code, 400, results)
            self.assertEqual(response.json()['code'], 'invalid_results', results)
        p.refresh_from_db()
        self.assertFalse(p.is_entered_result)

    def test_rejects_malformed_requests(self):
        p = self.make('Андреев')
        for changes in (None, 'x', {}, [5], [{'participant': p.id}], [{'participant': 'abc', 'results': {}}],
                        [{'results': {'0': cell(1)}}], [{'participant': p.id, 'results': [1]}]):
            response = self.save(changes)
            self.assertEqual(response.status_code, 400, changes)

    def test_empty_changes_are_a_noop(self):
        self.make('Андреев')
        response = self.save([])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['saved'], {'cells': 0, 'participants': 0})

    def test_unknown_participant_and_participant_of_another_event(self):
        other_event = services.create_event(owner=self.user, title='Other', date=date(2026, 10, 2))
        stranger = Participant.objects.create(event=other_event, first_name='Чужой', last_name='Участник', pin=1111)
        for participant_id in (999999, stranger.id):
            response = self.save([{'participant': participant_id, 'results': {'0': cell(1)}}])
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()['code'], 'participant_not_found')
        stranger.refresh_from_db()
        self.assertFalse(stranger.is_entered_result)

    def test_only_the_organizer_can_save(self):
        p = self.make('Андреев')
        outsider = self.user.__class__.objects.create_user(id=3, username='outsider', password='password123')
        self.client.force_login(outsider)
        response = self.save([{'participant': p.id, 'results': {'0': cell(1)}}])
        self.assertEqual(response.status_code, 403)
        self.client.logout()
        self.assertIn(self.save([{'participant': p.id, 'results': {'0': cell(1)}}]).status_code, (401, 403))
        p.refresh_from_db()
        self.assertFalse(p.is_entered_result)

    def test_superuser_can_save_for_any_event(self):
        p = self.make('Андреев')
        self.client.force_login(self.superuser)
        self.assertEqual(self.save([{'participant': p.id, 'results': {'0': cell(1)}}]).status_code, 200)

    def test_works_when_participants_update_is_not_allowed(self):
        """Повторный ввод самими участниками запрещён, но организатор правит всегда."""
        self.set_event(is_update_result_allowed=False, is_enter_result_allowed=False)
        p = self.make('Андреев', result={'0': {'top': 1, 'zone': 1}})
        self.assertEqual(self.save([{'participant': p.id, 'results': {'0': cell(2)}}]).status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.french_accents['0'], {'top': 2, 'zone': 2})


class ClearResultsTests(MatrixTestBase):
    def test_clearing_results_resets_entered_flag_accents_and_place(self):
        p = self.make('Андреев', result={'0': {'top': 2, 'zone': 2}})
        self.assertEqual((p.is_entered_result, p.place), (True, 1))
        services.clear_results(self.event)
        p.refresh_from_db()
        self.assertEqual((p.french_accents, p.is_entered_result, p.place, p.score), ({}, False, 0, 0))
        data = self.client.get(self.url).json()
        self.assertEqual(data['participants'][0]['results'], [{'top': 0, 'zone': 0}] * 10)


@override_settings(VITE_DEV_SERVER='http://localhost:5173')
class MatrixPageTests(MatrixTestBase):
    def url_page(self):
        return reverse('matrix', args=[self.event.id])

    def test_organizer_gets_the_page(self):
        response = self.client.get(self.url_page())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="matrix-app" data-event-id="{self.event.id}"')
        self.assertContains(response, 'src/entries/matrix.ts')

    def test_anonymous_is_sent_away(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url_page()).status_code, 302)

    def test_other_users_are_sent_away(self):
        outsider = self.user.__class__.objects.create_user(id=3, username='outsider', password='password123')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.url_page()).status_code, 302)

    def test_menu_links_to_the_page(self):
        response = self.client.get(reverse('admin_actions', args=[self.event.id]))
        self.assertContains(response, self.url_page())
