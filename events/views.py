import asyncio
import json
import logging

from asgiref.sync import sync_to_async
from django import views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.forms import formset_factory, modelformset_factory
from django.http import JsonResponse
from django.shortcuts import render, redirect
from djqscsv import render_to_csv_response

from config import settings
from events.forms import ParticipantRegistrationForm, AdminDescriptionForm, AccentForm, AccentParticipantForm, \
    EventAdminSettingsForm, RouteEditForm, ParticipantForm, CreateEventForm
from events.models import Event, Participant, Route
from events.models import ACCENT_NO
from events import services, xl_tools

logger = logging.getLogger(settings.LOGGER)


class MainView(views.View):
    @staticmethod
    def get(request):
        if int(settings.DEFAULT_EVENT_ID) != 0:
            return redirect('event', event_id=settings.DEFAULT_EVENT_ID)
        events = Event.objects.all()        # TODO: pagination
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
            template_name='events/event/description.html',
            context={
                'event': event,
            }
        )


class AdminActionsView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event/admin-actions.html',
            context={
                'event': event,
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.get(id=event_id)
        logger.info('Admin.Services [POST]')
        if 'create_participant' in request.POST:
            services.debug_create_participants(event=event, num=5)
        elif 'create_routes' in request.POST:
            services.create_event_routes(event=event)
        elif 'update_score' in request.POST:
            services.update_results(event=event)
        elif 'export_startlist' in request.POST:
            return services.get_startlist_response(event=event)
        elif 'export_result' in request.POST:
            return services.get_result_response(event=event)
        else:
            pass
        return redirect('admin_actions', event_id)


class AdminActionsClearView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event/admin-actions-clear.html',
            context={
                'event': event,
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.get(id=event_id)
        logger.info('Admin.Settings.Deletions [POST]')
        if 'clear_event' in request.POST:
            services.clear_event(event=event)
        elif 'clear_participants' in request.POST:
            services.clear_participants(event=event)
        elif 'clear_routes' in request.POST:
            services.clear_routes(event=event)
        else:
            pass
        return redirect('admin_actions_clear', event_id)


@sync_to_async
def export_results(event_id: int):
    event = Event.objects.get(id=event_id)
    xl_tools.export_result(event=event)


async def async_get_results(request, event_id):
    loop = asyncio.get_event_loop()
    loop.create_task(export_results(event_id=event_id))
    return redirect('admin_protocols', event_id)


class AdminProtocolsView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event/admin-protocols.html',
            context={
                'event': event,
                'items': services.get_list_of_protocols()
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.get(id=event_id)
        logger.info('Admin.Protocols [POST]')
        if 'export_startlist' in request.POST:
            return services.get_startlist_response(event=event)
        elif 'export_result' in request.POST:
            return redirect('async_get_results', event_id)
        else:
            pass
        return redirect('admin_protocols', event_id)


class ProtocolDownload(views.View):
    @staticmethod
    def get(request, event_id, file):
        return services.download_xlsx_response(file)


class AdminDescriptionView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event/admin-description.html',
            context={
                'event': event,
                'form': AdminDescriptionForm(instance=event),
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.filter(id=event_id)
        form = AdminDescriptionForm(request.POST)
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
            return redirect('admin_description', event_id)
        else:
            logger.warning(f'-> Event [{event}] not updated. Form [{form}] is not valid')
            return render(
                request=request,
                template_name='events/event/admin-description.html',
                context={
                    'event': event,
                    'form': AdminDescriptionForm(request.POST),
                }
            )


class EventAdminSettingsView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event/admin-settings.html',
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
                is_separate_score_by_groups=cd['is_separate_score_by_groups'],
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
                is_view_pin_after_registration=cd['is_view_pin_after_registration'],
            )
            logger.info(f'-> Event [{event}] update OK')
            return redirect('admin_settings', event_id)
        else:
            logger.warning(f'-> Event [{event}] not updated. Form [{form}] is not valid')
            return render(
                request=request,
                template_name='events/event/admin-settings.html',
                context={
                    'event': event,
                    'form': EventAdminSettingsForm(request.POST),
                }
            )


class EnterResultsView(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        if event.is_without_registration:
            return redirect('enter_wo_reg', event_id=event_id)
        initial = [{'label': i, 'accent': ACCENT_NO} for i in range(event.routes_num)]
        AccentFormSet = formset_factory(AccentForm, extra=0)
        formset = AccentFormSet(initial=initial, prefix='accents')
        return render(
            request=request,
            template_name='events/event/enter.html',
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
                return redirect('event_enter', event_id=event_id)
            logger.info(f'-> participant found: [{participant}] ->')

            services.enter_results(event=event,
                                   participant=participant,
                                   accents_cleaned_data=accent_formset.cleaned_data)

            logger.info('-> update participant accents')
            return redirect('event_enter', event_id=event_id)
        logger.warning(f'-> {participant_form} or {accent_formset} are not valid')
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


class EnterWithoutReg(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        initial = [{'label': i, 'accent': ACCENT_NO} for i in range(event.routes_num)]
        AccentFormSet = formset_factory(AccentForm, extra=0)
        formset = AccentFormSet(initial=initial, prefix='accents')
        routes = event.route.all().order_by('number')
        group_list = services.get_group_list(event=event)
        set_list = services.get_set_list_for_registration_available(event=event)
        return render(
            request=request,
            template_name='events/event/enter-wo-reg.html',
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
            services.enter_results(event=event,
                                   participant=participant,
                                   accents_cleaned_data=accent_formset.cleaned_data)
            return redirect('event_results', event_id=event_id)
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
        event = Event.objects.get(id=event_id)
        results = services.get_results(event=event, full_results=True)
        return render(
            request=request,
            template_name='events/event/results.html',
            context={
                'event': event,
                'routes': range(1, event.routes_num + 1),
                'male': results[Participant.GENDER_MALE],
                'female': results[Participant.GENDER_FEMALE],
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
            template_name='events/event/participants.html',
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
            template_name='events/event/registration.html',
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
            if event.is_view_pin_after_registration:
                return redirect('event_registration_ok', event_id=event_id, participant_id=participant.id)
            else:
                return redirect('event_participants', event_id=event_id)
        logger.warning(f'-> registration failed, [{form}] is not valid')
        return render(
            request=request,
            template_name='events/event/registration.html',
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
            template_name='events/event/registration-ok.html',
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
        formset = RouteEditFormSet(queryset=event.route.all().order_by('number'), prefix='routes')
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
            routes = event.route.all().order_by('number')
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


class ParticipantView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
        return render(
            request=request,
            template_name='events/participant.html',
            context={
                'title': f'{participant.last_name} {participant.first_name}',
                'event': event,
                'participant': participant,
                'form': ParticipantForm(instance=participant,
                                        group_list=services.get_group_list(event=event),
                                        set_list=services.get_set_list_for_registration_available(event=event),
                                        ),
            }
        )

    @staticmethod
    def post(request, event_id, p_id):
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
        form = ParticipantForm(request.POST,
                               request.FILES,
                               group_list=services.get_group_list(event=event),
                               set_list=services.get_set_list_for_registration_available(event=event),
                               )
        if form.is_valid():
            services.update_participant(event=event, participant=participant, cd=form.cleaned_data)
            return redirect('participant', event_id, p_id)
        else:
            return render(
                request=request,
                template_name='events/participant.html',
                context={
                    'title': f'{participant.last_name} {participant.first_name}',
                    'event': event,
                    'form': ParticipantForm(request.POST,
                                            group_list=services.get_group_list(event=event),
                                            set_list=services.get_set_list_for_registration_available(event=event),
                                            ),
                }
            )


class ParticipantRoutesView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
        initial = [{'label': i, 'accent': participant.accents.get(str(i), ACCENT_NO)} for i in range(event.routes_num)]
        AccentFormSet = formset_factory(form=AccentForm, extra=0)
        formset = AccentFormSet(initial=initial, prefix='accents')
        return render(
            request=request,
            template_name='events/participant-routes.html',
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
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
        AccentFormSet = formset_factory(form=AccentForm, extra=0)
        accent_formset = AccentFormSet(request.POST, request.FILES, prefix='accents')
        if accent_formset.is_valid():
            services.enter_results(event=event,
                                   participant=participant,
                                   accents_cleaned_data=accent_formset.cleaned_data)
            return redirect('participant_routes', event_id=event_id, p_id=p_id)
        return render(
            request=request,
            template_name='events/participant-routes.html',
            context={
                'title': f'{participant.last_name} {participant.first_name}',
                'event': event,
                'participant': participant,
                'formset': accent_formset,
                'routes': event.route.all().order_by('number'),
            }
        )


class ProfileView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request):
        return render(request=request,
                      template_name='events/my-events.html')


class MyEventsView(LoginRequiredMixin, views.View):
    @staticmethod
    def get(request):
        events = Event.objects.filter(owner=request.user.id)
        return render(request=request,
                      template_name='events/profile/my-events.html',
                      context={
                          'events': events,
                      })


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


class TestView(views.View):
    @staticmethod
    def get(request):
        event = Event.objects.get(id=1)
        data = services.get_results(event=event, full_results=True)
        return render(
            request=request,
            template_name='events/test.html',
            context={
                'data': data,
            }
        )


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
            cd = form.cleaned_data
            event = services.create_event(owner=request.user, title=cd['title'], date=cd['date'])
            return redirect('admin_description', event.id)
        else:
            return render(
                request=request,
                template_name='events/profile/create.html',
                context={
                    'form': CreateEventForm(request.POST),
                }
            )
