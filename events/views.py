import json
import logging

from django import views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.forms import formset_factory, modelformset_factory
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from djqscsv import render_to_csv_response

from config import settings
from events.forms import ParticipantRegistrationForm, EventAdminDescriptionForm, AccentForm, AccentParticipantForm, \
    EventAdminServiceForm, EventAdminSettingsForm, RouteEditForm
from events.models import Event, Participant, Route, Accent
from events import services


logger = logging.getLogger(settings.LOGGER)


class MainView(views.View):
    @staticmethod
    def get(request):
        return redirect('event', event_id=1)
        events = Event.objects.all()
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
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event.html',
            context={
                'event': event,
            }
        )


class EventAdminView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event-admin.html',
            context={
                'event': event,
                'form': EventAdminServiceForm(prefix='service_form'),
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.get(id=event_id)
        logger.info('Admin.Services [POST]')
        if 'clear_event' in request.POST:
            services.clear_event(event=event)
        elif 'create_participant' in request.POST:
            services.debug_create_participants(event=event, num=5)
        elif 'create_routes' in request.POST:
            services.create_event_routes(event=event)
            services.create_default_accents_for_all(event=event)
        elif 'update_score' in request.POST:
            services.update_routes_points(event=event)
            services.update_participants_score(event=event)
        elif 'clear_participants' in request.POST:
            services.clear_participants(event=event)
        elif 'clear_routes' in request.POST:
            services.clear_routes(event=event)
        elif 'export_startlist' in request.POST:
            return services.get_startlist_response(event=event)
        else:
            pass
        return redirect('event_admin', event_id)


class EventAdminDescriptionView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event-admin-description.html',
            context={
                'event': event,
                'form': EventAdminDescriptionForm(instance=event),
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.filter(id=event_id)
        form = EventAdminDescriptionForm(request.POST)
        logger.info('Admin.Description [POST] ->')
        if form.is_valid():
            cd = form.cleaned_data
            event.update(
                title=cd['title'],
                date=cd['date'],
                poster=cd['poster'],
                description=cd['description'],
            )
            logger.info(f'-> Event [{event}] update OK')
            return redirect('event_admin_description', event_id)
        else:
            logger.warning(f'-> Event [{event}] not updated. Form [{form}] is not valid')
            return render(
                request=request,
                template_name='events/event-admin-description.html',
                context={
                    'event': event,
                    'form': EventAdminDescriptionForm(request.POST),
                }
            )


class EventAdminSettingsView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event-admin-settings.html',
            context={
                'event': event,
                'form': EventAdminSettingsForm(instance=event),
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.filter(id=event_id)
        form = EventAdminSettingsForm(request.POST)
        logger.info('Admin.Settings [POST] ->')
        if form.is_valid():
            cd = form.cleaned_data
            event.update(
                routes_num=cd['routes_num'],
                is_published=cd['is_published'],
                is_registration_open=cd['is_registration_open'],
                is_enter_result_allowed=cd['is_enter_result_allowed'],
                is_results_allowed=cd['is_results_allowed'],
                is_count_only_entered_results=cd['is_count_only_entered_results'],
                is_view_full_results=cd['is_view_full_results'],
                is_view_route_color=cd['is_view_route_color'],
                is_view_route_grade=cd['is_view_route_grade'],
                is_view_route_score=cd['is_view_route_score'],
                score_type=cd['score_type'],
                flash_points=cd['flash_points'],
                redpoint_points=cd['redpoint_points'],
                group_num=cd['group_num'],
                group_list=cd['group_list'],
                set_num=cd['set_num'],
                set_list=cd['set_list'],
                set_max_participants=cd['set_max_participants'],
                registration_fields=cd['registration_fields'],
                required_fields=cd['required_fields'],
                is_without_registration=cd['is_without_registration'],
            )
            logger.info(f'-> Event [{event}] update OK')
            return redirect('event_admin_settings', event_id)
        else:
            logger.warning(f'-> Event [{event}] not updated. Form [{form}] is not valid')
            return render(
                request=request,
                template_name='events/event-admin-settings.html',
                context={
                    'event': event,
                    'form': EventAdminSettingsForm(request.POST),
                }
            )


class EventEnterView(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        if event.is_without_registration:
            return redirect('event_enter_wo_reg', event_id=event_id)
        initial = [{'label': i} for i in range(event.routes_num)]
        AccentFormSet = formset_factory(AccentForm, extra=0)
        formset = AccentFormSet(initial=initial, prefix='accents')
        return render(
            request=request,
            template_name='events/event-enter.html',
            context={
                'event': event,
                'formset': formset,
                'participant_form': AccentParticipantForm(prefix='participant'),
                'routes': event.route.all().order_by('number'),
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.get(id=event_id)
        participant_form = AccentParticipantForm(request.POST, prefix='participant')
        AccentFormSet = formset_factory(AccentForm)
        accent_formset = AccentFormSet(request.POST, prefix='accents')
        logger.info('Enter Result [POST] ->')
        if participant_form.is_valid() and accent_formset.is_valid():
            pin = participant_form.cleaned_data['pin']
            logger.info(f'-> pin={pin} ->')
            try:
                participant = event.participant.get(pin=int(pin))
            except (Participant.DoesNotExist, TypeError):
                logger.warning('-> Participant not found')
                return redirect('event_enter', event_id=event_id)   # TODO: msg for user
            logger.info(f'-> participant found: [{participant}] ->')
            participant_accents = event.accent.filter(participant=participant).order_by('route__number')
            for index, accent in enumerate(participant_accents):
                services.save_accent(accent=accent,
                                     result=accent_formset.cleaned_data[index]['accent'],
                                     route=Route.objects.get(event=event, number=index + 1))
            participant.is_entered_result = True
            participant.save()
            logger.info('-> update participant accents')
            return redirect('event_results', event_id=event_id)
        logger.warning(f'-> {participant_form} or {accent_formset} are not valid')
        return render(
            request=request,
            template_name='events/event-enter.html',
            context={
                'event': event,
                'formset': accent_formset,
                'participant_form': participant_form,
                'routes': event.route.all().order_by('number'),
            }
        )


class EventEnterWithoutReg(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        initial = [{'label': i} for i in range(event.routes_num)]
        AccentFormSet = formset_factory(AccentForm, extra=0)
        formset = AccentFormSet(initial=initial, prefix='accents')
        routes = event.route.all().order_by('number')
        group_list = services.get_group_list(event=event)
        set_list = services.get_set_list_for_registration_available(event=event)
        return render(
            request=request,
            template_name='events/event-enter-wo-reg.html',
            context={
                'event': event,
                'formset': formset,
                'routes': routes,
                'form': ParticipantRegistrationForm(group_list=group_list,
                                                    set_list=set_list,
                                                    registration_fields=event.registration_fields,
                                                    required_fields=event.required_fields,
                                                    is_enter_form=True)

            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.get(id=event_id)
        group_list = services.get_group_list(event=event)
        set_list = services.get_set_list(event=event)
        form = ParticipantRegistrationForm(request.POST,
                                           request.FILES,
                                           group_list=group_list,
                                           set_list=set_list,
                                           registration_fields=event.registration_fields,
                                           required_fields=event.required_fields,
                                           is_enter_form=True)
        AccentFormSet = formset_factory(AccentForm)
        accent_formset = AccentFormSet(request.POST, prefix='accents')
        if form.is_valid() and accent_formset.is_valid():
            participant = services.register_participant(event=event, cd=form.cleaned_data)
            participant_accents = event.accent.filter(participant=participant).order_by('route__number')
            for index, accent in enumerate(participant_accents):
                services.save_accent(accent=accent,
                                     result=accent_formset.cleaned_data[index]['accent'],
                                     route=Route.objects.get(event=event, number=index + 1))
            participant.is_entered_result = True
            participant.save()
            return redirect('event_results', event_id=event_id)
        return render(
            request=request,
            template_name='events/event-enter-wo-reg.html',
            context={
                'event': event,
                'formset': accent_formset,
                'participant_form': form,
            }
        )


class EventResultsView(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        male, female = [], []
        for group in services.get_group_list(event=event):
            male.append(dict(name=group,
                             data=services.get_sorted_participants_results(
                                 event=event,
                                 participants=event.participant.filter(gender=Participant.GENDER_MALE,
                                                                       group_index=services.get_group_list(
                                                                           event=event).index(group)))))
        for group in services.get_group_list(event=event):
            female.append(dict(name=group,
                               data=services.get_sorted_participants_results(
                                   event=event,
                                   participants=event.participant.filter(gender=Participant.GENDER_FEMALE,
                                                                         group_index=services.get_group_list(
                                                                             event=event).index(group)))))

        routes_score_male = [f"{round(services.get_route_point(event=event, route=r)['male'] * event.flash_points, 2)}/"
                             f"{round(services.get_route_point(event=event, route=r)['male'] * event.redpoint_points, 2)}"
                             for r in event.route.all()]
        routes_score_female = [f"{round(services.get_route_point(event=event, route=r)['female'] * event.flash_points, 2)}/"
                               f"{round(services.get_route_point(event=event, route=r)['female'] * event.redpoint_points, 2)}"
                               for r in event.route.all()]
        return render(
            request=request,
            template_name='events/event-results.html',
            context={
                'event': event,
                'routes': range(1, event.routes_num + 1),
                'routes_score_male': routes_score_male,
                'routes_score_female': routes_score_female,
                'male': male,
                'female': female,
            }
        )


class EventParticipantsView(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        participants = Participant.objects.filter(event__id=event_id)
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
        chart_city_data = {
            'labels': [str(city['city']) for city in cities],
            'data': [city['num'] for city in cities],
        }
        return render(
            request=request,
            template_name='events/event-participants.html',
            context={
                'event': event,
                'participants': participants,
                'chart_set_data': json.dumps(chart_set_data),
                'chart_group_data': json.dumps(chart_group_data),
                'chart_city_data': json.dumps(chart_city_data),
            }
        )


class EventRegistrationView(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        if event.is_without_registration:
            return redirect('event_enter', event_id=event_id)
        group_list = services.get_group_list(event=event)
        set_list = services.get_set_list_for_registration_available(event=event)
        return render(
            request=request,
            template_name='events/event-registration.html',
            context={
                'event': event,
                'form': ParticipantRegistrationForm(group_list=group_list,
                                                    set_list=set_list,
                                                    registration_fields=event.registration_fields,
                                                    required_fields=event.required_fields,
                                                    is_enter_form=False)
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.get(id=event_id)
        group_list = services.get_group_list(event=event)
        set_list = services.get_set_list(event=event)
        form = ParticipantRegistrationForm(request.POST,
                                           request.FILES,
                                           group_list=group_list,
                                           set_list=set_list,
                                           registration_fields=event.registration_fields,
                                           required_fields=event.required_fields,
                                           is_enter_form=False)
        logger.info('Registration [POST] ->')
        if form.is_valid():
            participant = services.register_participant(event=event, cd=form.cleaned_data)
            return redirect('event_registration_ok', event_id=event_id, participant_id=participant.id)
        logger.warning(f'-> registration failed, [{form}] is not valid')
        return render(
            request=request,
            template_name='events/event-registration.html',
            context={
                'event': event,
                'form': form,
            }
        )


class EventRegistrationOkView(views.View):
    @staticmethod
    def get(request, event_id, participant_id):
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=participant_id)
        return render(
            request=request,
            template_name='events/event-registration-ok.html',
            context={
                'event': event,
                'participant': participant,
            }
        )


class RouteEditor(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        RouteEditFormSet = modelformset_factory(Route, form=RouteEditForm, extra=0)
        formset = RouteEditFormSet(queryset=event.route.all(), prefix='routes')
        return render(
            request=request,
            template_name='events/route_editor.html',
            context={
                'event': event,
                'formset': formset,
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.get(id=event_id)
        RouteEditFormSet = modelformset_factory(Route, form=RouteEditForm, extra=0)
        formset = RouteEditFormSet(request.POST, prefix='routes')
        logger.info('Route Editor [POST] ->')
        if formset.is_valid():
            routes = event.route.all()
            for index, route in enumerate(routes):
                route.grade = formset.cleaned_data[index]['grade']
                route.color = formset.cleaned_data[index]['color']
                route.save()
            logger.info(f'-> updated {len(routes)} routes')
            return redirect('route_editor', event_id=event_id)
        logger.warning(f'-> update failed, [{formset}] is not valid')
        return render(
                request=request,
                template_name='events/route_editor.html',
                context={
                    'event': event,
                    'formset': formset,
                }
            )


class ExportParticipantToCsv(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        participants = event.participant.all()
        return render_to_csv_response(participants, delimiter=';')


def check_pin_code(request):
    pin = request.GET.get('pin')
    event_id = request.GET.get('event_id')
    try:
        participant = Participant.objects.get(pin=pin, event__id=event_id)
        response = {'Find': True, 'participant': f'{participant.first_name} {participant.last_name}'}
    except Participant.DoesNotExist:
        response = {'Find': False}
    return JsonResponse(response)


def page_not_found_view(request, exception):
    return render(request=request, template_name='events/error.html', status=404,
                  context={'code': '', 'msg': 'Страница не найдена!'})


def error_view(request):
    return render(request=request, template_name='events/error.html', status=500,
                  context={'code': '', 'msg': 'Ошибка сервера!'})
