from django import views
from django.forms import formset_factory
from django.http import JsonResponse
from django.shortcuts import render, redirect

from events.forms import ParticipantRegistrationForm, EventAdminDescriptionForm, AccentForm, AccentParticipantForm, \
    EventAdminServiceForm, EventAdminSettingsForm
from events.models import Event, Participant, Route, Accent
from events import services


class MainView(views.View):
    @staticmethod
    def get(request):
        #return redirect('event', event_id=1)
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


class EventAdminView(views.View):
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
        # service_form = EventAdminServiceForm(request.POST, prefix='service_form')
        if 'clear_event' in request.POST:
            services.clear_event(event=event)
        elif 'create_participant' in request.POST:
            services.create_participant_with_default_accents(
                event=event,
                first_name=services.get_random_string(4),
                last_name=services.get_random_string(6)
            )
        elif 'create_routes' in request.POST:
            services.create_event_routes(event=event)
        elif 'update_score' in request.POST:
            services.update_routes_points(event=event)
            services.update_participants_score(event=event)
        else:
            pass
        return redirect('event_admin', event_id)


class EventAdminDescriptionView(views.View):
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
        if form.is_valid():
            cd = form.cleaned_data
            event.update(
                title=cd['title'],
                date=cd['date'],
                poster=cd['poster'],
                description=cd['description'],
            )
            return redirect('event_admin_description', event_id)
        else:
            return render(
                request=request,
                template_name='events/event-admin-description.html',
                context={
                    'event': event,
                    'form': EventAdminDescriptionForm(request.POST),
                }
            )


class EventAdminSettingsView(views.View):
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
                score_type=cd['score_type'],
                flash_points=cd['flash_points'],
                redpoint_points=cd['redpoint_points'],
                group_num=cd['group_num'],
                group_list=cd['group_list'],
                set_num=cd['set_num'],
                set_list=cd['set_list'],
            )
            return redirect('event_admin_settings', event_id)
        else:
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
            }
        )

    @staticmethod
    def post(request, event_id):
        event = Event.objects.get(id=event_id)
        participant_form = AccentParticipantForm(request.POST, prefix='participant')
        AccentFormSet = formset_factory(AccentForm)
        accent_formset = AccentFormSet(request.POST, prefix='accents')
        if participant_form.is_valid() and accent_formset.is_valid():
            pin = participant_form.cleaned_data['pin']
            try:
                participant = Participant.objects.get(pin=int(pin))
            except (Participant.DoesNotExist, TypeError):
                return redirect('event_enter', event_id=event_id)   # TODO: msg for user
            participant_accents = Accent.objects.filter(participant=participant, event=event)
            for index, accent in enumerate(participant_accents):
                accent.accent = accent_formset.cleaned_data[index]['accent']
                accent.route = Route.objects.get(event=event, number=index + 1)
                accent.save()
            services.update_routes_points(event=event)
            services.update_participants_score(event=event)

            return redirect('event_results', event_id=event_id)
        return render(
            request=request,
            template_name='events/event-enter.html',
            context={
                'event': event,
                'formset': accent_formset,
                'participant_form': participant_form,
            }
        )


class EventResultsView(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        data_male = services.get_sorted_participants_scores_by_gender(event=event, gender=Participant.GENDER_MALE)
        data_female = services.get_sorted_participants_scores_by_gender(event=event, gender=Participant.GENDER_FEMALE)
        return render(
            request=request,
            template_name='events/event-results.html',
            context={
                'event': event,
                'participants': event.participant.order_by('-score'),
                'routes': range(1, event.routes_num + 1),
                'sorted_male': data_male,
                'sorted_female': data_female,
            }
        )


class EventParticipantsView(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        participants_male = Participant.objects.filter(event__id=event_id, gender='MALE')
        participants_female = Participant.objects.filter(event__id=event_id, gender='FEMALE')
        return render(
            request=request,
            template_name='events/event-participants.html',
            context={
                'event': event,
                'participants_male': participants_male,
                'participants_female': participants_female,
            }
        )


class EventRegistrationView(views.View):
    @staticmethod
    def get(request, event_id):
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event-registration.html',
            context={
                'event': event,
                'form': ParticipantRegistrationForm(['12', '23']),
            }
        )

    @staticmethod
    def post(request, event_id):
        form = ParticipantRegistrationForm(request.POST, request.FILES)
        event = Event.objects.get(id=event_id)
        if form.is_valid():
            participant = services.create_participant_with_default_accents(
                event=event,
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                gender=form.cleaned_data['gender'],
                birth_year=form.cleaned_data['birth_year'],
                city=form.cleaned_data['city'],
                team=form.cleaned_data['team'],
                grade=form.cleaned_data['grade'],
            )
            return redirect('event_registration_ok', event_id=event_id, participant_id=participant.id)
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


def check_pin_code(request):
    pin = request.GET.get('pin')
    event_id = request.GET.get('event_id')
    try:
        participant = Participant.objects.get(pin=pin, event__id=event_id)
        response = {'Find': True, 'participant': f'{participant.first_name} {participant.last_name}'}
    except Participant.DoesNotExist:
        response = {'Find': False}
    return JsonResponse(response)
