import asyncio
import datetime
import logging

from asgiref.sync import sync_to_async
from django import views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import formset_factory, modelformset_factory, ModelChoiceField
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

from config import settings
from events.forms import EventPremiumSettingsForm, AdminDescriptionForm, \
    EventSettingsForm, RouteEditForm, ParticipantForm, CreateEventForm, EventPaySettingsForm, \
    PromoCodeAddForm, WalletForm, ScoreTableForm
from events.models import GRADES, Event, Participant, PayDetail, Route, PromoCode, Wallet
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


def _site_context(request) -> dict:
    """ Что Vue-страницам главной и кабинета нужно знать про того, кто смотрит, и куда вести ссылки """
    return {
        'authenticated': request.user.is_authenticated,
        'isSuperuser': request.user.is_superuser,
        'links': {
            'home': reverse('main'),
            'create': reverse('create'),
            'mine': reverse('my_events'),
            'login': reverse('account_login'),
            'help': reverse('help', kwargs={'type': 'workflow'}),
            'stat': reverse('stat'),
            'about': reverse('about'),
        },
    }


class MainView(views.View):
    """ Главная: каталог событий целиком на Vue (frontend/src/screens/home). Первую страницу кладём в HTML,
    остальное экран берёт из /api/site/events/ """
    @staticmethod
    def get(request):
        if int(settings.DEFAULT_EVENT_ID) != 0:
            return redirect('event', event_id=settings.DEFAULT_EVENT_ID)
        return render(
            request=request,
            template_name='events/index.html',
            context={
                'home_initial': services.get_site_events(user=request.user),
                'site_context': _site_context(request),
            }
        )


class EventPageView(views.View):
    """ Страница события для участника: шапка с вкладками и все её экраны («Инфо», «Ввод», «Участники», «Результаты»,
    регистрация, оплата) — один Vue-экран, он сам разбирает адрес и берёт данные из API.
    HTML отдаёт Django, чтобы работали превью ссылок в чатах """
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(
            request=request,
            template_name='events/event/page.html',
            context={
                'event': event,
                'can_view': event.is_published or request.user == event.owner or request.user.is_superuser,
                'poster_url': request.build_absolute_uri(event.poster.url) if event.poster else '',
            }
        )


def event_page_redirect(request, event_id, **kwargs):
    """ Старые адреса (письма с ссылкой на оплату, страница «регистрация завершена»): ведут на страницу события """
    return redirect('event', event_id=event_id)


class AdminActionsView(IsOwnerMixin, views.View):
    """ «Обзор» панели события: целиком на Vue (frontend/src/screens/panel), данные из /api/events/<id>/panel/.
    Старые формы действий заменены API: переключатели и служебные действия живут там """
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(request=request, template_name='events/event/admin-actions.html', context={'event': event})


class PanelParticipantsView(IsOwnerMixin, views.View):
    """ «Участники» панели: таблица организатора на Vue, данные из /api/events/<id>/participants/ """
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(request=request, template_name='events/event/panel-people.html', context={'event': event})


def export_results_thread(event_id: int):
    from django.db import close_old_connections
    try:
        event = get_object_or_404(Event, id=event_id)
        xl_tools.export_result(event=event)
    except Exception as e:
        logger.error(f"Error exporting results for event {event_id}: {e}", exc_info=True)
    finally:
        close_old_connections()


def async_get_results(request, event_id):
    import threading
    thread = threading.Thread(
        target=export_results_thread,
        args=(event_id,),
        name=f"export_results_{event_id}",
        daemon=True
    )
    thread.start()
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
                event.poster = cd['poster']
            event.gym = cd['gym']
            event.title = cd['title']
            event.date = cd['date']
            event.date_end = cd.get('date_end')
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
                    'form': form,
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
        form = EventSettingsForm(request.POST, instance=event)
        if form.is_valid():
            services.update_event_settings(event=event, cd=form.cleaned_data)
            return redirect('admin_settings', event_id)
        else:
            return render(
                request=request,
                template_name='events/event/admin-settings.html',
                context={
                    'event': event,
                    'form': form,
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


class MatrixView(IsOwnerMixin, views.View):
    """ Массовый ввод результатов организатором. Экран целиком на Vue, данные он берёт из API """
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(request=request, template_name='events/event/matrix.html', context={'event': event})


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
            return redirect('panel_participants', event_id)
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
    """ Старая страница правки результатов участника: теперь это матрица, открытая на нём """
    @staticmethod
    def get(request, event_id, p_id):
        return redirect(f"{reverse('matrix', args=(event_id,))}#p={p_id}")


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
            return redirect('panel_participants', event_id=event_id)
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
    """ Кабинет организатора: его события с числами, на Vue (frontend/src/screens/mine) """
    @staticmethod
    def get(request):
        return render(request=request,
                      template_name='events/profile/my-events.html',
                      context={
                          'mine_initial': services.get_my_events(user=request.user,
                                                                 scope=request.GET.get('scope', 'mine')),
                          'site_context': _site_context(request),
                      })


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
            date = form.cleaned_data['date']
            date_end = form.cleaned_data.get('date_end')
            event = services.create_event(owner=request.user, title=form.cleaned_data['title'], date=date, date_end=date_end)
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


class StatView(views.View):
    @staticmethod
    def get(request):
        stats = services.get_platform_stats()
        return render(
            request=request,
            template_name='events/stat.html',
            context={'stats': stats}
        )
