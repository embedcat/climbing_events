from datetime import date

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from events import services
from events.models import Participant
from events.templatetags.events_tags import event_stage_pill, section_of
from events.tests import ClimbingEventsBaseTestCase


class SectionOfTests(SimpleTestCase):
    def test_sections_of_the_site(self):
        self.assertEqual(section_of('main'), 'events')
        self.assertEqual(section_of('results'), 'events')
        self.assertEqual(section_of('help'), 'help')
        self.assertEqual(section_of('my_events'), 'mine')
        self.assertEqual(section_of('admin_actions'), 'mine')
        self.assertEqual(section_of('wallets'), 'mine')

    def test_account_pages_and_unknown_belong_to_no_section(self):
        self.assertEqual(section_of('account_login'), '')
        self.assertEqual(section_of('account_signup'), '')
        self.assertEqual(section_of('stat'), '')
        self.assertEqual(section_of(''), '')


@override_settings(VITE_DEV_SERVER='http://localhost:5173')
class SiteBarTests(ClimbingEventsBaseTestCase):
    """Полоса сайта стоит над каждой страницей: гостю одно меню, организатору другое"""

    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.user, title='Осенний фестиваль', date=date(2026, 10, 4))
        self.event.is_published = True
        self.event.save()

    def test_guest_sees_login_and_public_sections(self):
        html = self.client.get(reverse('main')).content.decode()
        self.assertIn('data-site-bar', html)
        self.assertIn(reverse('account_login'), html)
        self.assertIn(reverse('help', kwargs={'type': 'workflow'}), html)
        # ссылка на кабинет есть в данных для Vue, но не в полосе сайта
        self.assertNotIn(f'href="{reverse("my_events")}"', html)
        self.assertNotIn(reverse('wallets'), html)
        self.assertNotIn('site-sidebar', html)

    def test_organizer_sees_cabinet_links_but_not_admin_ones(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('main')).content.decode()
        self.assertIn(reverse('my_events'), html)
        self.assertIn(reverse('create'), html)
        self.assertIn(reverse('wallets'), html)
        self.assertIn(reverse('account_logout'), html)
        self.assertNotIn('/dja/', html)
        self.assertNotIn('?scope=all', html)

    def test_superuser_menu_has_all_events_stat_and_admin(self):
        self.client.force_login(self.superuser)
        html = self.client.get(reverse('main')).content.decode()
        self.assertIn('/dja/', html)
        self.assertIn('?scope=all', html)
        self.assertIn(reverse('stat'), html)
        self.assertIn('суперадмин', html)

    def test_nav_marks_the_current_section(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('my_events')).content.decode()
        self.assertIn(f'<a href="{reverse("my_events")}" aria-current="page">Мои события</a>', html)
        self.assertNotIn(f'<a href="{reverse("main")}" aria-current="page">', html)

    def test_theme_is_applied_before_first_paint(self):
        html = self.client.get(reverse('main')).content.decode()
        self.assertIn("localStorage.getItem('rockevents-theme')", html)
        self.assertLess(html.index("rockevents-theme"), html.index('</head>'))

    def test_event_page_lives_in_the_site_frame(self):
        html = self.client.get(reverse('event', args=[self.event.id])).content.decode()
        self.assertIn('data-site-bar', html)
        self.assertIn('class="re-body"', html)
        self.assertIn('rockevents-theme', html)
        self.assertIn('src/entries/event.ts', html)

    def test_unpublished_event_page_still_has_the_bar_to_leave(self):
        self.event.is_published = False
        self.event.save()
        html = self.client.get(reverse('event', args=[self.event.id])).content.decode()
        self.assertIn('data-site-bar', html)
        self.assertIn('Событие не опубликовано', html)
        self.assertIn('src/entries/site.ts', html)

    def test_matrix_brings_its_own_frame_and_uses_the_full_width(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('matrix', args=[self.event.id])).content.decode()
        self.assertIn('data-site-bar', html)
        self.assertIn('site-page is-full', html)
        self.assertIn('src/entries/matrix.ts', html)
        self.assertNotIn('src/entries/site.ts', html)


@override_settings(VITE_DEV_SERVER='http://localhost:5173')
class PanelFrameTests(ClimbingEventsBaseTestCase):
    """Панель события организатора: разделы слева, подсветка текущего"""

    def setUp(self):
        super().setUp()
        self.event = services.create_event(owner=self.user, title='Осенний фестиваль', date=date(2026, 10, 4))
        self.client.force_login(self.user)

    def get(self, name, *args):
        return self.client.get(reverse(name, args=[self.event.id, *args])).content.decode()

    def test_overview_lists_sections_and_marks_itself(self):
        html = self.get('admin_actions')
        self.assertIn('site-side', html)
        self.assertIn(f'href="{reverse("admin_actions", args=[self.event.id])}" aria-current="page"', html)
        for name in ('admin_description', 'admin_settings', 'route_editor', 'pay_settings', 'matrix',
                     'admin_protocols'):
            self.assertIn(f'href="{reverse(name, args=[self.event.id])}"', html)

    def test_full_access_section_is_for_superuser_only(self):
        premium = reverse('premium_settings', args=[self.event.id])
        self.assertNotIn(f'href="{premium}"', self.get('admin_actions'))
        self.client.force_login(self.superuser)
        self.assertIn(f'href="{premium}"', self.get('admin_actions'))

    def test_section_pages_mark_their_own_item_and_show_breadcrumbs(self):
        html = self.get('route_editor')
        self.assertIn(f'href="{reverse("route_editor", args=[self.event.id])}" aria-current="page"', html)
        self.assertIn('site-crumbs', html)
        self.assertIn('← Осенний фестиваль', html)

    def test_participant_card_belongs_to_the_participants_section(self):
        person = Participant.objects.create(
            first_name='Иван', last_name='Иванов', gender=Participant.GENDER_MALE, event=self.event, pin=1234)
        html = self.get('participant', person.id)
        self.assertIn(f'href="{reverse("panel_participants", args=[self.event.id])}" aria-current="page"', html)

    def test_overview_hands_the_sections_to_vue_for_the_phone_list(self):
        html = self.get('admin_actions')
        self.assertIn('id="panel-sections"', html)
        self.assertIn('id="panel-app" data-screen="overview"', html)
        self.assertIn('src/entries/panel.ts', html)

    def test_stage_pill_tells_draft_from_published(self):
        self.assertEqual(event_stage_pill(self.event), {'label': 'Черновик', 'kind': 'warn'})
        self.event.is_published = True
        self.event.is_registration_open = True
        self.event.save()
        self.assertEqual(event_stage_pill(self.event), {'label': 'Регистрация открыта', 'kind': 'ok'})

    def test_participants_page_mounts_the_panel_table(self):
        html = self.get('panel_participants')
        self.assertIn('id="panel-app" data-screen="people"', html)
        self.assertIn('src/entries/panel.ts', html)
        self.assertIn(f'href="{reverse("panel_participants", args=[self.event.id])}" aria-current="page"', html)

    def test_participants_page_is_closed_to_outsiders(self):
        outsider = self.user.__class__.objects.create_user(id=3, username='outsider', password='password123')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse('panel_participants', args=[self.event.id])).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('panel_participants', args=[self.event.id])).status_code, 302)

    def test_removing_a_participant_returns_to_the_panel_table(self):
        person = Participant.objects.create(
            first_name='Иван', last_name='Иванов', gender=Participant.GENDER_MALE, event=self.event, pin=1234)
        response = self.client.post(reverse('participant_remove', args=[self.event.id, person.id]),
                                    {'participant_remove': '1'})
        self.assertRedirects(response, reverse('panel_participants', args=[self.event.id]),
                             fetch_redirect_response=False)
        self.assertFalse(Participant.objects.filter(id=person.id).exists())


class SettingsFormGroupsTests(ClimbingEventsBaseTestCase):
    """Настройки события разложены по темам, и ни одно поле не потерялось"""

    def test_every_form_field_sits_in_exactly_one_group(self):
        from events.forms import EventSettingsForm
        grouped = [name for _, fields in EventSettingsForm.GROUPS for name in fields]
        self.assertEqual(sorted(grouped), sorted(EventSettingsForm.Meta.fields))
        self.assertEqual(len(grouped), len(set(grouped)))

    @override_settings(VITE_DEV_SERVER='http://localhost:5173')
    def test_settings_page_renders_groups_and_saves(self):
        event = services.create_event(owner=self.user, title='Фестиваль', date=date(2026, 10, 4))
        self.client.force_login(self.user)
        response = self.client.get(reverse('admin_settings', args=[event.id]))
        html = response.content.decode()
        for title in ('Публикация и доступ', 'Регистрация', 'Группы и сеты', 'Подсчёт', 'Что видят участники',
                      'Ввод результатов участником'):
            self.assertIn(title, html)
        self.assertIn('novalidate', html)
        self.assertIn('name="group_list"', html)
        self.assertIn('name="is_published"', html)


class AccountPagesTests(ClimbingEventsBaseTestCase):
    """Вход и регистрация организатора в рамке сайта; ошибки теперь видно"""

    def test_login_page_is_in_the_frame_and_explains_who_it_is_for(self):
        response = self.client.get(reverse('account_login'))
        self.assertContains(response, 'data-site-bar')
        self.assertContains(response, 'Вход для организаторов')
        self.assertContains(response, 'Участникам вход не нужен')

    def test_wrong_password_is_reported(self):
        response = self.client.post(reverse('account_login'), {'login': 'user@example.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alert-danger')

    def test_login_works(self):
        response = self.client.post(reverse('account_login'), {'login': 'user@example.com', 'password': 'password123'})
        self.assertEqual(response.status_code, 302)

    def test_signup_shows_field_errors(self):
        response = self.client.post(reverse('account_signup'), {
            'email': 'new@example.com', 'password1': 'S3cretpass!x', 'password2': 'different'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'invalid-feedback')

    def test_create_event_page_explains_what_comes_next(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('create'))
        self.assertContains(response, 'Новое событие')
        self.assertContains(response, 'чек-лист подготовки')


class BrandTests(ClimbingEventsBaseTestCase):
    """Логотип, значки сайта и афиша по умолчанию"""

    def test_bar_carries_the_logo_inline_with_the_accent_dot(self):
        html = self.client.get(reverse('main')).content.decode()
        self.assertIn('class="site-logo"', html)
        self.assertIn('class="lg-dot"', html)
        self.assertIn('aria-label="RockEvents: на главную"', html)

    @override_settings(VITE_DEV_SERVER='http://localhost:5173')
    def test_every_head_declares_the_icons(self):
        event = services.create_event(owner=self.user, title='Фестиваль', date=date(2026, 10, 4))
        event.is_published = True
        event.save()
        for url in (reverse('main'), reverse('event', args=[event.id]), reverse('account_login')):
            html = self.client.get(url).content.decode()
            self.assertIn('/static/events/img/favicon.svg', html, url)
            self.assertIn('/static/events/img/favicon.ico', html, url)
            self.assertIn('rel="apple-touch-icon"', html, url)

    def test_bare_favicon_request_goes_to_the_static_icon(self):
        response = self.client.get('/favicon.ico')
        self.assertRedirects(response, '/static/events/img/favicon.ico', status_code=301, fetch_redirect_response=False)

    def test_icon_files_exist_and_are_square(self):
        from django.contrib.staticfiles import finders
        from PIL import Image
        for name, size in (('favicon-32.png', (32, 32)), ('apple-touch-icon.png', (180, 180))):
            path = finders.find(f'events/img/{name}')
            self.assertIsNotNone(path, name)
            with Image.open(path) as image:
                self.assertEqual(image.size, size, name)
        for name in ('favicon.svg', 'favicon.ico', 'logo.svg', 'logo-mark.svg'):
            self.assertIsNotNone(finders.find(f'events/img/{name}'), name)

    def test_default_poster_is_portrait_and_opaque(self):
        # афиши показываются в рамке 3:4: квадрат обрезался бы, прозрачная иконка пропадала бы на тёмной теме
        from django.contrib.staticfiles import finders
        from PIL import Image
        with Image.open(finders.find('events/img/default_poster.png')) as image:
            self.assertEqual(image.width * 4, image.height * 3)
            alpha = image.convert('RGBA').getchannel('A')
            self.assertEqual(alpha.getextrema(), (255, 255))
