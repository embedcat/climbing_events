import asyncio
import json
import logging
import operator

from asgiref.sync import sync_to_async
from django import views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.forms import formset_factory, modelformset_factory
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from config import settings
from events.forms import ParticipantRegistrationForm, AdminDescriptionForm, AccentForm, AccentParticipantForm, \
    EventAdminSettingsForm, RouteEditForm, ParticipantForm, CreateEventForm
from events.models import Event, Participant, Route, ACCENT_NO
from events import services, xl_tools
from braces import views as braces

logger = logging.getLogger(settings.LOGGER)


class IsOwnerMixin(braces.UserPassesTestMixin):
    redirect_field_name = ''

    def test_func(self, user):
        event_id = self.kwargs.get('event_id')
        return user.is_superuser or user.id is Event.objects.get(id=event_id).owner.id


class MainView(views.View):
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
        event = Event.objects.get(id=event_id)
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
        if 'update_score' in request.POST:
            services.update_results(event=event)
        if 'create_results' in request.POST:
            services.clear_results(event=event)
        if 'remove_participants' in request.POST:
            services.remove_participants(event=event)
        if 'clear_event' in request.POST:
            services.clear_event(event=event)
        if 'remove_event' in request.POST:
            services.remove_event(event=event)
            return redirect('my_events')
        return redirect('admin_actions', event_id)


@sync_to_async
def export_results(event_id: int):
    event = Event.objects.get(id=event_id)
    xl_tools.export_result(event=event)


async def async_get_results(request, event_id):
    loop = asyncio.get_event_loop()
    loop.create_task(export_results(event_id=event_id))
    return redirect('admin_protocols', event_id)


class AdminProtocolsView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
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
        event = Event.objects.get(id=event_id)
        logger.info('Admin.Protocols [POST]')
        if 'export_startlist' in request.POST:
            return services.get_startlist_response(event=event)
        if 'export_result' in request.POST:
            return redirect('async_get_results', event_id)
        if 'qr_description' in request.POST:
            url = request.build_absolute_uri(reverse('event', args=(event_id, )))
            return services.qr_create(text=url, title='qr_event')
        if 'qr_register' in request.POST:
            url = request.build_absolute_uri(reverse('registration', args=(event_id, )))
            return services.qr_create(text=url, title='qr_registration')
        if 'qr_enter' in request.POST:
            url = request.build_absolute_uri(reverse('enter_results', args=(event_id, )))
            return services.qr_create(text=url, title='qr_enter_results')
        return redirect('admin_protocols', event_id)


class ProtocolDownload(views.View):
    @staticmethod
    def get(request, event_id, file):
        return services.download_xlsx_response(f'{event_id}/{file}')


class ProtocolRemove(views.View):
    @staticmethod
    def get(request, event_id, file):
        services.remove_file(f'{event_id}/{file}')
        return redirect('admin_protocols', event_id=event_id)


class AdminDescriptionView(IsOwnerMixin, views.View):
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
        event = Event.objects.get(id=event_id)
        form = AdminDescriptionForm(request.POST, request.FILES)
        logger.info('Admin.Description [POST] ->')
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
            logger.info(f'-> Event [{event}] update OK')
            return redirect('admin_description', event_id)
        else:
            logger.warning(f'-> Event [{event}] not updated. Form [{form}] is not valid')
            return render(
                request=request,
                template_name='events/event/admin-description.html',
                context={
                    'event': event,
                    'form': AdminDescriptionForm(request.POST, request.FILES),
                }
            )


class AdminSettingsView(IsOwnerMixin, views.View):
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
        event = Event.objects.get(id=event_id)
        form = EventAdminSettingsForm(request.POST)
        logger.info('Admin.Settings [POST] ->')
        if form.is_valid():
            services.update_event_settings(event=event, cd=form.cleaned_data)
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
                return redirect('enter_results', event_id=event_id)
            logger.info(f'-> participant found: [{participant}] ->')

            services.enter_results(event=event,
                                   participant=participant,
                                   accents_cleaned_data=accent_formset.cleaned_data)

            logger.info('-> update participant accents')
            return redirect('enter_results', event_id=event_id)
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
            return redirect('results', event_id=event_id)
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


class ParticipantsView(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
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
                'fields': event.registration_fields,
            }
        )


class RegistrationView(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        if event.is_without_registration:
            return redirect('enter_results', event_id=event_id)
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
                return redirect('participants', event_id=event_id)
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


class RouteEditor(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        RouteEditFormSet = modelformset_factory(Route, form=RouteEditForm, extra=0)
        formset = RouteEditFormSet(queryset=event.route.all().order_by('number'), prefix='routes')
        return render(
            request=request,
            template_name='events/event/route-editor.html',
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
            template_name='events/event/route-editor.html',
            context={
                'event': event,
                'formset': formset,
            }
        )


class ParticipantView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
        group_list = services.get_group_list(event=event) if event.group_num > 1 else ""
        group_list_value = group_list[participant.group_index] if event.group_num > 1 else ""
        set_list = services.get_set_list_for_change_available(event=event, participant=participant)
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
                                                 'set_index': set_index_value}
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
            return redirect('participants', event_id)
        else:
            return render(
                request=request,
                template_name='events/event/participant.html',
                context={
                    'title': f'{participant.last_name} {participant.first_name}',
                    'event': event,
                    'form': ParticipantForm(request.POST,
                                            group_list=services.get_group_list(event=event),
                                            set_list=services.get_set_list_for_registration_available(event=event),
                                            ),
                }
            )


class ParticipantRoutesView(IsOwnerMixin, views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
        initial = [{'label': i, 'accent': participant.accents.get(str(i), ACCENT_NO)} for i in range(event.routes_num)]
        AccentFormSet = formset_factory(form=AccentForm, extra=0)
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
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
        AccentFormSet = formset_factory(form=AccentForm, extra=0)
        accent_formset = AccentFormSet(request.POST, request.FILES, prefix='accents')
        if accent_formset.is_valid():
            services.enter_results(event=event,
                                   participant=participant,
                                   accents_cleaned_data=accent_formset.cleaned_data)
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
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
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
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
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


class ProfileView(IsOwnerMixin, views.View):
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
