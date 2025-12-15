import asyncio
import datetime
import json
import logging
import operator

from asgiref.sync import sync_to_async
from django import views
from django.core.paginator import Paginator
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db.models import Count
from django.forms import formset_factory, modelformset_factory, ModelChoiceField
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

from config import settings
from events.exceptions import DuplicateParticipantError, ParticipantTooYoungError
from events.forms import AccentFrenchForm, EventPremiumSettingsForm, ParticipantRegistrationForm, AdminDescriptionForm, AccentForm, AccentParticipantForm, \
    EventSettingsForm, RouteEditForm, ParticipantForm, CreateEventForm, EventPaySettingsForm, \
    PromoCodeAddForm, WalletForm, ScoreTableForm
from events.models import GRADES, Event, Participant, PayDetail, Route, ACCENT_NO, PromoCode, Wallet
from events import services, xl_tools
from braces import views as braces

from events.pay_views import get_notify_link

logger = logging.getLogger(settings.LOGGER)


class IsOwnerMixin(braces.UserPassesTestMixin):
    redirect_field_name = ''

    def test_func(self, user):
        event_id = self.kwargs.get('event_id')
        return user.is_superuser or user.id is Event.objects.get(id=event_id).owner.id


class IsSuperuserMixin(braces.UserPassesTestMixin):
    redirect_field_name = ''

    def test_func(self, user):
        event_id = self.kwargs.get('event_id')
        return user.is_superuser


class MainView(ListView):
    model = Event
    paginate_by = 5
    template_name = 'events/index.html'
    context_object_name = 'events'
    # ordering = ['-date']

    def get_queryset(self):
        events = Event.objects.filter(is_published=True).order_by('-date')
        return events
    
    def get_paginator(self, queryset: services.QuerySet[asyncio.Any], per_page: int, orphans: int = ..., allow_empty_first_page: bool = ..., **kwargs: asyncio.Any) -> Paginator:
        return super().get_paginator(queryset, per_page, orphans, allow_empty_first_page, **kwargs)
    

    @staticmethod
    def get(request):
        if int(settings.DEFAULT_EVENT_ID) != 0:
            return redirect('event', event_id=settings.DEFAULT_EVENT_ID)
        events = Event.objects.filter(is_published=True).order_by('-date')
        return render(
            request=request,
            template_name='events/index.html',
            context={
                'events': events,
            }
        )


class EventView(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(
            request=request,
            template_name='events/event/description.html',
            context={
                'event': event,
            }
        )


class AdminActionsView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        entered_num = event.participant.filter(is_entered_result=True).count()
        paid_num = event.participant.filter(paid=True).count()
        return render(
            request=request,
            template_name='events/event/admin-actions.html',
            context={
                'event': event,
                'entered_num': entered_num,
                'paid_num': paid_num,
                'male_link': str(request.build_absolute_uri(reverse('results', args=(event_id,)))) + '?autorefresh&m',
                'female_link': str(request.build_absolute_uri(reverse('results', args=(event_id,)))) + '?autorefresh&f',
            }
        )

    @staticmethod
    def post(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        if 'update_score' in request.POST:
            services.update_results(event=event)
        if 'clear_results' in request.POST:
            services.clear_results(event=event)
        if 'clear_event' in request.POST:
            services.clear_event(event=event)
        if 'remove_event' in request.POST:
            services.remove_event(event=event)
            return redirect('my_events')
        if 'mock_data' in request.POST:
            services.clear_event(event=event)
            services.debug_create_participants(event=event, num=50)
            services.debug_apply_random_results(event=event)
        return redirect('admin_actions', event_id)


@sync_to_async
def export_results(event_id: int):
    event = get_object_or_404(Event, id=event_id)
    xl_tools.export_result(event=event)


async def async_get_results(request, event_id):
    loop = asyncio.get_event_loop()
    loop.create_task(export_results(event_id=event_id))
    return redirect('admin_protocols', event_id)


class AdminProtocolsView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(
            request=request,
            template_name='events/event/admin-protocols.html',
            context={
                'event': event,
                'protocols': services.get_list_of_protocols(event=event)
            }
        )

    @staticmethod
    def post(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        if 'export_startlist' in request.POST:
            return services.get_startlist_response(event=event)
        if 'export_result' in request.POST:
            if event.is_premium:
                return redirect('async_get_results', event_id)
            else:
                return services.get_result_example_response(event=event)
        if 'qr_description' in request.POST:
            url = request.build_absolute_uri(reverse('event', args=(event_id,)))
            return services.qr_create_response(text=url, title='qr_event')
        if 'qr_register' in request.POST:
            url = request.build_absolute_uri(reverse('registration', args=(event_id,)))
            return services.qr_create_response(text=url, title='qr_registration')
        if 'qr_enter' in request.POST:
            url = request.build_absolute_uri(reverse('enter_results', args=(event_id,)))
            return services.qr_create_response(text=url, title='qr_enter_results')
        return redirect('admin_protocols', event_id)


class ProtocolDownload(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id, file):
        return services.download_xlsx_response(f'{event_id}/{file}')


class ProtocolRemove(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id, file):
        services.remove_file(f'{event_id}/{file}')
        return redirect('admin_protocols', event_id=event_id)


class AdminDescriptionView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(
            request=request,
            template_name='events/event/admin-description.html',
            context={
                'event': event,
                'form': AdminDescriptionForm(instance=event, is_expired=event.is_expired),
            }
        )

    @staticmethod
    def post(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        form = AdminDescriptionForm(request.POST, request.FILES, is_expired=event.is_expired)
        if form.is_valid():
            cd = form.cleaned_data
            if 'poster' in request.FILES:
                event.poster = request.FILES['poster']
            event.gym = cd['gym']
            event.title = cd['title']
            event.date = cd['date']
            event.description = cd['description']
            event.short_description = cd['short_description']
            event.save()
            return redirect('admin_description', event_id)
        else:
            return render(
                request=request,
                template_name='events/event/admin-description.html',
                context={
                    'event': event,
                    'form': AdminDescriptionForm(request.POST, request.FILES, is_expired=event.is_expired),
                }
            )


class AdminSettingsView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(
            request=request,
            template_name='events/event/admin-settings.html',
            context={
                'event': event,
                'form': EventSettingsForm(instance=event),
            }
        )

    @staticmethod
    def post(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        form = EventSettingsForm(request.POST)
        if form.is_valid():
            services.update_event_settings(event=event, cd=form.cleaned_data)
            return redirect('admin_settings', event_id)
        else:
            return render(
                request=request,
                template_name='events/event/admin-settings.html',
                context={
                    'event': event,
                    'form': EventSettingsForm(request.POST),
                }
            )


class PremiumSettingsView(IsSuperuserMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(
            request=request,
            template_name='events/event/premium-settings.html',
            context={
                'event': event,
                'form': EventPremiumSettingsForm(instance=event),
            }
        )

    @staticmethod
    def post(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        form = EventPremiumSettingsForm(request.POST)
        if form.is_valid():
            services.update_event_premium_settings(event=event, cd=form.cleaned_data)
            return redirect('premium_settings', event_id)
        else:
            return render(
                request=request,
                template_name='events/event/premium-settings.html',
                context={
                    'event': event,
                    'form': EventPremiumSettingsForm(request.POST),
                }
            )


class PaySettingsView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        wallets = Wallet.objects.all() if request.user.is_superuser else Wallet.objects.filter(owner=request.user)
        EventPaySettingsForm.base_fields['wallet'] = ModelChoiceField(queryset=wallets, label='Кошелек Yoomoney', required=False)
        reg_type_list = event.reg_type_list.split(',') if event.reg_type_list else []
        initial = {f'price_{key}': value for key, value in event.price_list.items()} if event.price_list else {}
        form = EventPaySettingsForm(instance=event,
                                    initial=initial,
                                    reg_type_list=[(i, t.strip()) for i, t in enumerate(reg_type_list)])
        return render(
            request=request,
            template_name='events/event/pay-settings.html',
            context={
                'event': event,
                'form': form,
                'promocode_form': PromoCodeAddForm(),
                'promocodes': PromoCode.objects.filter(event__id=event_id),
            }
        )

    @staticmethod
    def post(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        reg_type_list = event.reg_type_list.split(',') if event.reg_type_list else []
        form = EventPaySettingsForm(request.POST,
                                    reg_type_list=[(i, t.strip()) for i, t in enumerate(reg_type_list)])
        promocode_form = PromoCodeAddForm(request.POST)
        if 'pay_settings' in request.POST and form.is_valid() and services.update_event_pay_settings(event=event, cd=form.cleaned_data):
            return redirect('pay_settings', event_id)
        if 'add_promocode' in request.POST and promocode_form.is_valid():
            PromoCode.objects.create(event=event,
                                     title=promocode_form.cleaned_data['title'],
                                     price=promocode_form.cleaned_data['price'],
                                     max_applied_num=promocode_form.cleaned_data['max_applied_num'])
            return redirect('pay_settings', event_id)
        return render(
            request=request,
            template_name='events/event/pay-settings.html',
            context={
                'event': event,
                'form': form,
                'promocode_form': promocode_form,
                'promocodes': PromoCode.objects.filter(event__id=event_id),
            }
        )


class EnterResultsView(views.View):
    @staticmethod
    def get(request, event_id):
        saved_accents = request.session.pop("accents", None)
        pin = request.session.pop("pin", None)
        event = get_object_or_404(Event, id=event_id)
        if event.is_without_registration:
            return redirect('enter_wo_reg', event_id=event_id)
        if pin and len(saved_accents) == event.routes_num:
            # возврат со страницы подтверждения
            initial = [{'label': i, 'accent': accent} for i, accent in saved_accents.items()]
        else:
            initial = [{'label': i, 'top': '0', 'zone': '0'} for i in range(event.routes_num)]
        AccentFormSet = formset_factory(AccentFrenchForm if event.score_type ==
                                        Event.SCORE_FRENCH else AccentForm, extra=0)
        formset = AccentFormSet(initial=initial, prefix='accents')
        return render(
            request=request,
            template_name='events/event/enter.html',
            context={
                'event': event,
                'formset': formset,
                'participant_form': AccentParticipantForm(prefix='participant'),
                'routes': event.route.all().order_by('number'),
                'pin': pin
            }
        )

    @staticmethod
    def post(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        participant_form = AccentParticipantForm(request.POST, prefix='participant')
        AccentFormSet = formset_factory(AccentFrenchForm if event.score_type == Event.SCORE_FRENCH else AccentForm)
        accent_formset = AccentFormSet(request.POST, prefix='accents')
        if participant_form.is_valid() and accent_formset.is_valid():
            entered_results = services.form_data_to_results(form_cleaned_data=accent_formset.cleaned_data)
            pin = participant_form.cleaned_data['pin']
            try:
                participant = event.participant.get(pin=int(pin))
            except (Participant.DoesNotExist, TypeError):
                return redirect('enter_results', event_id=event_id)

            if event.is_check_result_before_enter:
                request.session['pin'] = pin
                request.session['accents'] = entered_results
                return redirect('enter_check', event_id=event_id)

            services.enter_results(event=event,
                                   participant=participant,
                                   accents=entered_results)

            return redirect('enter_results_ok', event_id=event_id)
        return render(
            request=request,
            template_name='events/event/enter.html',
            context={
                'event': event,
                'formset': accent_formset,
                'participant_form': participant_form,
                'routes': event.route.all().order_by('number'),
            }
        )


class EnterCheckView(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        routes = event.route.all().order_by('number')
        result = request.session.get("accents")
        temp, items = [], []
        for i, route in enumerate(routes):
            temp.append({
                'num': route.number,
                'grade': route.grade,
                'result': result.get(str(i), ACCENT_NO),
            })
        for i in range(0, event.routes_num, 5):
            items.append(temp[i:i + 5])
        return render(
            request=request,
            template_name='events/event/enter-check.html',
            context={
                'event': event,
                'items': items,
            }
        )

    @staticmethod
    def post(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        if 'cancel' in request.POST:
            return redirect('enter_results', event_id=event_id)
        if 'submit' in request.POST:
            result = request.session.pop("accents", None)
            pin = request.session.pop("pin", None)
            try:
                participant = event.participant.get(pin=int(pin))
            except (Participant.DoesNotExist, TypeError):
                return redirect('enter_results', event_id=event_id)

            services.enter_results(event=event,
                                   participant=participant,
                                   accents=result)

            return redirect('enter_results_ok', event_id=event_id)


class EnterResultsOKView(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(
            request=request,
            template_name='events/event/enter-ok.html',
            context={
                'event': event,
            }
        )


class EnterWithoutReg(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        if not services.is_registration_open(event=event):
            return redirect('event', event_id=event_id)
        initial = [{'label': i, 'top': '0', 'zone': '0'} for i in range(event.routes_num)]
        AccentFormSet = formset_factory(AccentFrenchForm if event.score_type ==
                                        Event.SCORE_FRENCH else AccentForm, extra=0)
        formset = AccentFormSet(initial=initial, prefix='accents')
        routes = event.route.all().order_by('number')
        group_list = services.get_group_list(event=event)
        set_list = services.get_set_list_available(event=event)
        return render(
            request=request,
            template_name='events/event/enter-wo-reg.html',
            context={
                'event': event,
                'formset': formset,
                'routes': routes,
                'form': ParticipantRegistrationForm(group_list=group_list,
                                                    set_list=set_list,
                                                    registration_fields=services.get_registration_fields(event=event),
                                                    required_fields=services.get_registration_required_fields(
                                                        event=event),
                                                    is_enter_form=True,
                                                    reg_type_list=None)

            }
        )

    @staticmethod
    def post(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        group_list = services.get_group_list(event=event)
        set_list = services.get_set_list(event=event)
        form = ParticipantRegistrationForm(request.POST,
                                           request.FILES,
                                           group_list=group_list,
                                           set_list=set_list,
                                           registration_fields=services.get_registration_fields(event=event),
                                           required_fields=services.get_registration_required_fields(event=event),
                                           is_enter_form=True,
                                           reg_type_list=None)
        AccentFormSet = formset_factory(AccentFrenchForm if event.score_type == Event.SCORE_FRENCH else AccentForm)
        accent_formset = AccentFormSet(request.POST, prefix='accents')
        if form.is_valid() and accent_formset.is_valid():
            try:
                participant = event.participant.get(first_name=form.cleaned_data['first_name'],
                                                    last_name=form.cleaned_data['last_name'])
                if not event.is_update_result_allowed:
                    return redirect('results', event_id=event_id)
            except Participant.DoesNotExist:
                participant = services.register_participant(event=event, cd=form.cleaned_data)
            services.enter_results(event=event,
                                   participant=participant,
                                   accents=services.form_data_to_results(form_cleaned_data=accent_formset.cleaned_data))
            return redirect('enter_results_ok', event_id=event_id)
        return render(
            request=request,
            template_name='events/event/enter-wo-reg.html',
            context={
                'event': event,
                'formset': accent_formset,
                'participant_form': form,
            }
        )


class ResultsView(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        results = services.get_results(event=event, full_results=True)
        return render(
            request=request,
            template_name='events/event/results.html',
            context={
                'event': event,
                'routes': event.route.all().order_by('number'),
                'male': results[Participant.GENDER_MALE],
                'female': results[Participant.GENDER_FEMALE],
                'view_scores': event.is_view_full_results and event.is_view_route_score and event.score_type != Event.SCORE_NUM_ACCENTS and event.score_type != Event.SCORE_FRENCH,
                'autorefresh': 'autorefresh' in request.GET,
                'active_male': 'm' in request.GET or 'f' not in request.GET,
                'active_female': 'f' in request.GET,
            }
        )


class ParticipantsView(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        queryset = Participant.objects.filter(event__id=event_id)
        participants = sorted(queryset, key=operator.attrgetter('last_name'))
        set_list = services.get_set_list(event=event)
        chart_set_data = {
            'labels': set_list,
            'data': [event.participant.filter(set_index=index).count() for index in range(len(set_list))],
        }
        group_list = services.get_group_list(event=event)
        chart_group_data = {
            'labels': group_list,
            'data': [event.participant.filter(group_index=index).count() for index in range(len(group_list))],
        }
        cities = Participant.objects.filter(event__id=event_id).values('city').order_by('-city').annotate(
            num=Count('city'))
        cities = sorted(cities, key=operator.itemgetter('num'), reverse=True)
        chart_city_data = {
            'labels': [str(city['city']) for city in cities],
            'data': [city['num'] for city in cities],
        }
        return render(
            request=request,
            template_name='events/event/participants.html',
            context={
                'event': event,
                'participants': participants,
                'chart_set_data': json.dumps(chart_set_data),
                'chart_group_data': json.dumps(chart_group_data),
                'chart_city_data': json.dumps(chart_city_data),
                'fields': services.get_registration_fields(event=event),
            }
        )


class RegistrationView(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        if event.is_without_registration:
            return redirect('enter_results', event_id=event_id)
        group_list = services.get_group_list(event=event)
        set_list = services.get_set_list_available(event=event)
        registration_fields = services.get_registration_fields(event=event)
        required_fields = services.get_registration_required_fields(event=event)
        return render(
            request=request,
            template_name='events/event/registration.html',
            context={
                'event': event,
                'is_registration_open': services.is_registration_open(event=event),
                'form': ParticipantRegistrationForm(group_list=group_list,
                                                    set_list=set_list,
                                                    registration_fields=registration_fields,
                                                    required_fields=required_fields,
                                                    is_enter_form=False,
                                                    reg_type_list=event.reg_type_list)
            }
        )

    @staticmethod
    def post(request, event_id):
        error = None
        event = get_object_or_404(Event, id=event_id)
        group_list = services.get_group_list(event=event)
        set_list = services.get_set_list(event=event)
        registration_fields = services.get_registration_fields(event=event)
        required_fields = services.get_registration_required_fields(event=event)
        form = ParticipantRegistrationForm(request.POST,
                                           request.FILES,
                                           group_list=group_list,
                                           set_list=set_list,
                                           registration_fields=registration_fields,
                                           required_fields=required_fields,
                                           is_enter_form=False,
                                           reg_type_list=event.reg_type_list)
        if form.is_valid():
            try:
                participant = services.register_participant(event=event, cd=form.cleaned_data)
                if event.is_view_pin_after_registration or event.is_pay_allowed:
                    return redirect('event_registration_ok', event_id=event_id, participant_id=participant.id)
                else:
                    return redirect('participants', event_id=event_id)
            except (DuplicateParticipantError, ParticipantTooYoungError) as e:
                error = e
        return render(
            request=request,
            template_name='events/event/registration.html',
            context={
                'event': event,
                'is_registration_open': True,
                'form': form,
                'error': error,
            }
        )


class EventRegistrationOkView(views.View):
    @staticmethod
    def get(request, event_id, participant_id):
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Participant, id=participant_id)
        pay_url = request.build_absolute_uri(reverse('pay_create', args=(event_id, participant_id,)))
        msg = services.get_registration_msg_html(event=event,
                                                 participant=participant,
                                                 pay_url=pay_url)
        email = services.get_registration_email_msg_html(event=event,
                                                 participant=participant,
                                                 pay_url=pay_url)
        if participant.email and event.is_pay_allowed:
            send_mail(subject='Регистрация завершена',
                      message=msg,
                      from_email=None,
                      recipient_list=[participant.email],
                      fail_silently=True,
                      html_message=email)
        return render(
            request=request,
            template_name='events/event/registration-ok.html',
            context={
                'event': event,
                'msg': msg,
            }
        )


class RouteEditor(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        RouteEditFormSet = modelformset_factory(Route, form=RouteEditForm, extra=0)
        formset = RouteEditFormSet(queryset=event.route.all().order_by('number'), prefix='routes')
        ScoreTableFormset = formset_factory(form=ScoreTableForm, extra=0)
        initial = [{'id': i, 'score': event.score_table.get(GRADES[i][0], 0)} for i in range(len(GRADES))]
        score_table_formset = ScoreTableFormset(initial=initial, prefix='score')
        return render(
            request=request,
            template_name='events/event/route-editor.html',
            context={
                'event': event,
                'formset': formset,
                'score_table_formset': score_table_formset if event.score_type == Event.SCORE_GRADE else None,
                'score_table_grades': GRADES,
            }
        )

    @staticmethod
    def post(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        RouteEditFormSet = modelformset_factory(Route, form=RouteEditForm, extra=0)
        formset = RouteEditFormSet(request.POST, prefix='routes')
        ScoreTableFormset = formset_factory(form=ScoreTableForm, extra=0)
        score_table_formset = ScoreTableFormset(request.POST, prefix='score')
        if formset.is_valid():
            routes = event.route.all().order_by('number')
            for index, route in enumerate(routes):
                route.grade = formset.cleaned_data[index]['grade']
                route.color = formset.cleaned_data[index]['color']
                route.save()
        if score_table_formset.is_valid():
            score_table = {GRADES[i][0]: score_table_formset.cleaned_data[i]['score'] for i in range(len(GRADES))}
            if score_table != event.score_table:
                services.update_results(event=event)
            event.score_table = score_table
            event.save()
        return redirect('route_editor', event_id=event_id)


class ParticipantView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Participant, id=p_id)
        group_list = services.get_group_list(event=event) if event.group_num > 1 else ""
        group_list_value = group_list[participant.group_index] if event.group_num > 1 else ""
        set_list = services.get_set_list_available(event=event, participant=participant)
        set_index_value = ""
        if event.set_num > 1:
            current_set_value = services.get_set_list(event=event)[participant.set_index]
            current_set_index = set_list.index(current_set_value)
            set_index_value = set_list[current_set_index]
        return render(
            request=request,
            template_name='events/event/participant.html',
            context={
                'title': f'{participant.last_name} {participant.first_name}',
                'event': event,
                'participant': participant,
                'form': ParticipantForm(instance=participant,
                                        group_list=group_list,
                                        set_list=set_list,
                                        initial={'group_index': group_list_value,
                                                 'set_index': set_index_value,
                                                 'reg_type_index': participant.reg_type_index},
                                        is_pay_allowed=event.is_pay_allowed,
                                        registration_fields=services.get_registration_fields(event=event),
                                        reg_type_list=event.reg_type_list,
                                        ),
            }
        )

    @staticmethod
    def post(request, event_id, p_id):
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Participant, id=p_id)
        form = ParticipantForm(request.POST,
                               request.FILES,
                               group_list=services.get_group_list(event=event),
                               set_list=services.get_set_list_available(event=event, participant=participant),
                               is_pay_allowed=event.is_pay_allowed,
                               registration_fields=services.get_registration_fields(event=event),
                               reg_type_list=event.reg_type_list,
                               )
        if form.is_valid():
            services.update_participant(event=event, participant=participant, cd=form.cleaned_data)
            return redirect('participants', event_id)
        else:
            return render(
                request=request,
                template_name='events/event/participant.html',
                context={
                    'title': f'{participant.last_name} {participant.first_name}',
                    'event': event,
                    'participant': participant,
                    'form': ParticipantForm(request.POST,
                                            group_list=services.get_group_list(event=event),
                                            set_list=services.get_set_list_available(event=event, participant=participant),
                                            is_pay_allowed=event.is_pay_allowed,
                                            registration_fields=services.get_registration_fields(event=event),
                                            reg_type_list=event.reg_type_list,
                                            ),
                }
            )


class ParticipantRoutesView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Participant, id=p_id)
        initial = services.get_form_initial_results(event=event, participant=participant)
        AccentFormSet = formset_factory(form=AccentFrenchForm if event.score_type ==
                                        Event.SCORE_FRENCH else AccentForm, extra=0)
        formset = AccentFormSet(initial=initial, prefix='accents')
        return render(
            request=request,
            template_name='events/event/participant-routes.html',
            context={
                'title': f'{participant.last_name} {participant.first_name}',
                'event': event,
                'participant': participant,
                'formset': formset,
                'routes': event.route.all().order_by('number'),
            }
        )

    @staticmethod
    def post(request, event_id, p_id):
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Participant, id=p_id)
        AccentFormSet = formset_factory(form=AccentFrenchForm if event.score_type ==
                                        Event.SCORE_FRENCH else AccentForm, extra=0)
        accent_formset = AccentFormSet(request.POST, request.FILES, prefix='accents')
        if accent_formset.is_valid():
            services.enter_results(event=event,
                                   participant=participant,
                                   accents=services.form_data_to_results(form_cleaned_data=accent_formset.cleaned_data))
            return redirect('results', event_id=event_id)
        return render(
            request=request,
            template_name='events/event/participant-routes.html',
            context={
                'title': f'{participant.last_name} {participant.first_name}',
                'event': event,
                'participant': participant,
                'formset': accent_formset,
                'routes': event.route.all().order_by('number'),
            }
        )


class ParticipantRemoveView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Participant, id=p_id)
        return render(
            request=request,
            template_name='events/event/participant-remove.html',
            context={
                'title': f'{participant.last_name} {participant.first_name}',
                'event': event,
                'participant': participant,
            }
        )

    @staticmethod
    def post(request, event_id, p_id):
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Participant, id=p_id)
        if 'participant_remove' in request.POST:
            participant.delete()
            services.update_results(event=event)
            return redirect('participants', event_id=event_id)
        return render(
            request=request,
            template_name='events/event/participant-remove.html',
            context={
                'title': f'{participant.last_name} {participant.first_name}',
                'event': event,
                'participant': participant,
            }
        )


class MyEventsView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request):
        events = Event.objects.filter(owner=request.user.id)
        return render(request=request,
                      template_name='events/profile/my-events.html',
                      context={
                          'events': events,
                          'all_events': Event.objects.exclude(owner=request.user.id) if request.user.is_superuser else None,
                      })


def check_pin_code(request):
    pin = request.GET.get('pin')
    event_id = request.GET.get('event_id')
    event = Event.objects.get(id=event_id)
    try:
        participant = Participant.objects.get(pin=pin, event__id=event_id)
        if participant.is_entered_result and not event.is_update_result_allowed:
            response = {'result': False,
                        'reason': f'Найден участник: {participant.last_name} {participant.first_name}, но повторный ввод результатов запрещён.'}
        else:
            response = {'result': True, 'participant': f'{participant.last_name} {participant.first_name}'}
            if event.score_type == Event.SCORE_FRENCH:
                response.update({'french_accents': participant.french_accents})
            else:
                response.update({'accents': participant.french_accents})

    except Participant.DoesNotExist:
        response = {'result': False,
                    'reason': 'Участник не найден. Проверьте PIN-код, или <a href="{% url \'registration\' event.id %}">зарегистрируйтесь</a>!'}
    return JsonResponse(response)


def check_promo_code(request):
    promo_code_title = request.GET.get('promocode')
    event_id = request.GET.get('event_id')
    response = {'result': False,
                'price': 0}
    try:
        promo_code = PromoCode.objects.get(title=promo_code_title, event__id=event_id)
        if promo_code.max_applied_num == 0 or promo_code.applied_num < promo_code.max_applied_num:
            response = {'result': True,
                        'price': promo_code.price,
                        'promocode_id': promo_code.id}
    except PromoCode.DoesNotExist:
        pass
    return JsonResponse(response)


def page_not_found_view(request, exception):
    return render(request=request,
                  template_name='events/profile/error.html',
                  status=404,
                  context={
                      'code': '404',
                      'error_title': 'Событие не найдено',
                      'msg': f"<p>Вернуться к списку <a href=\"{request.build_absolute_uri(reverse('main'))}\">всех событий</a> или <a href=\"{request.build_absolute_uri(reverse('create'))}\">создать новое</a>!</p>",
                  },
                  )


def error_view(request):
    logger.error(f"Server Error. Request: {request}")
    return render(request=request, template_name='events/profile/error.html', status=500,
                  context={'code': '500', 'error_title': 'Ошибка сервера', 'msg': 'Спокойно! Мы с этим разберёмся!'})


class CreateEventView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request):
        form = CreateEventForm()
        return render(request=request,
                      template_name='events/profile/create.html',
                      context={
                          'form': form,
                      })

    @staticmethod
    def post(request):
        form = CreateEventForm(request.POST)
        if form.is_valid():
            date = datetime.datetime.strptime(request.POST['date'], "%m/%d/%Y").date()
            event = services.create_event(owner=request.user, title=form.cleaned_data['title'], date=date)
            return redirect('admin_description', event.id)
        else:
            return render(
                request=request,
                template_name='events/profile/create.html',
                context={
                    'form': CreateEventForm(request.POST),
                })


class ProfileView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request):
        return redirect('wallets')


class PromoCodeRemove(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id, promocode_id):
        try:
            PromoCode.objects.get(id=promocode_id).delete()
        except PromoCode.DoesNotExist as e:
            logger.error(f"PromoCode deleting error: {e}")
        return redirect('pay_settings', event_id=event_id)


class WalletsView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request):
        wallets = Wallet.objects.all() if request.user.is_superuser else Wallet.objects.filter(owner=request.user)
        return render(request=request,
                      template_name='events/profile/wallets.html',
                      context={
                          'form': WalletForm(),
                          'wallets': wallets,
                          'notify_link': get_notify_link(request=request),
                      })

    @staticmethod
    def post(request):
        form = WalletForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            Wallet.objects.create(owner=request.user,
                                  title=cd['title'],
                                  wallet_id=cd['wallet_id'],
                                  notify_secret_key=cd['notify_secret_key'])
            return redirect('wallets')
        else:
            return render(
                request=request,
                template_name='events/profile/wallets.html',
                context={
                    'form': WalletForm(request.POST),
                })


class WalletView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, wallet_id):
        try:
            wallet = Wallet.objects.get(id=wallet_id)
            if wallet.owner != request.user and not request.user.is_superuser:
                return redirect('profile')
            return render(request=request,
                          template_name='events/profile/wallet.html',
                          context={
                              'form': WalletForm(instance=wallet),
                          })
        except Wallet.DoesNotExist as e:
            logger.error(f"Wallet does not exist error: {e}")
        return redirect('profile')

    @staticmethod
    def post(request, wallet_id):
        wallet = Wallet.objects.get(id=wallet_id)
        form = WalletForm(request.POST)
        if form.is_valid() and (wallet.owner == request.user or request.user.is_superuser):
            wallet.title = form.cleaned_data['title']
            wallet.wallet_id = form.cleaned_data['wallet_id']
            wallet.notify_secret_key = form.cleaned_data['notify_secret_key']
            wallet.save()
            return redirect('wallet', wallet_id=wallet_id)
        return render(
            request=request,
            template_name='events/profile/wallet.html',
            context={
                'form': WalletForm(request.POST),
            })


class WalletRemoveView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, wallet_id):
        try:
            wallet = Wallet.objects.get(id=wallet_id)
            if wallet.owner == request.user or request.user.is_superuser:
                wallet.delete()
        except Wallet.DoesNotExist as e:
            logger.error(f"Wallet deleting error: {e}")
        return redirect('profile')


class CheckExpiredEventsView(views.View):
    @staticmethod
    def get(request):
        events = Event.objects.filter(is_expired=False, date__lt=datetime.datetime.today())
        services.check_expired_events(events=events)
        return HttpResponse(status=200)


class PayDetailsView(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        pay_details = PayDetail.objects.filter(event=event).order_by('-datetime')
        return render(request=request,
                      template_name='events/event/admin-paydetails.html',
                      context={
                          'event': event,
                          'pay_details': pay_details,
                      })
