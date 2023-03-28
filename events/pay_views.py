import logging
import hashlib

from django import views
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from config import settings
from events.models import CustomUser, Event, Participant, PromoCode, Wallet
from events import services

logger = logging.getLogger(settings.LOGGER)


def get_notify_link(request) -> str:
    return request.build_absolute_uri(reverse('pay_notify'))


def check_notify_hash(notify: dict, secret: str) -> bool:
    string = f"{notify['notification_type']}&{notify['operation_id']}&{notify['amount']}&{notify['currency']}&" \
             f"{notify['datetime']}&{notify['sender']}&{notify['codepro']}&{secret}&{notify['label']}"
    sha1_hash = hashlib.sha1(bytes(string, "UTF-8")).hexdigest()
    return sha1_hash == notify['sha1_hash']


def is_pay_available(event: Event) -> bool:
    return event.wallet and event.is_pay_allowed


def is_premium_pay_available(event: Event) -> bool:
    return not event.is_premium


def parse_pay_notification(post: dict) -> dict:
    parsed = {}
    try:
        parsed.update({'operation_id': post['operation_id']})
        parsed.update({'amount': float(post['amount'])})
        label = post['label']
        label = label.split('_')
        event_id, participant_id, promocode_id, wallet_id = 0, 0, 0, 0
        for part in label:
            if part.startswith('e'):
                event_id = int(part[1:])
            if part.startswith('p'):
                participant_id = int(part[1:])
            if part.startswith('c'):
                promocode_id = int(part[1:])
            if part.startswith('w'):
                wallet_id = int(part[1:])
        parsed.update({'event_id': event_id})
        parsed.update({'participant_id': participant_id})
        parsed.update({'promocode_id': promocode_id})
        parsed.update({'wallet_id': wallet_id})
    except KeyError as e:
        return {}

    return parsed


class NotifyView(views.View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(NotifyView, self).dispatch(*args, **kwargs)

    @staticmethod
    def get(request):
        return HttpResponse(status=200)

    @staticmethod
    def post(request):
        parsed = parse_pay_notification(request.POST)
        if parsed:
            event_id = parsed['event_id']
            wallet_id = parsed['wallet_id']
            participant_id = parsed['participant_id']
            promocode_id = parsed['promocode_id']
            operation_id = parsed['operation_id']
            amount = parsed['amount']

            event = Event.objects.get(id=event_id)
            wallet = Wallet.objects.get(id=wallet_id) if wallet_id else event.wallet

            if check_notify_hash(request.POST, wallet.notify_secret_key):
                if wallet_id:
                        event.is_premium = True
                        event.is_expired = False
                        event.save()
                        logger.info(f"Pay Premium Notify Success: Event: {event}, Wallet: {wallet}")
                else:
                    participant = Participant.objects.get(id=participant_id, event=event)
                    participant.paid = True
                    participant.save()
                    promo_code = None
                    if promocode_id:
                        promo_code = PromoCode.objects.get(id=promocode_id)
                        promo_code.applied_num = promo_code.applied_num + 1
                        promo_code.save()
                    logger.error(f"Pay Notify Success: Event: {event}, Participant: {participant}{', PromoCode: ' + promo_code.title if promocode_id else ''}")
                    services.save_pay_detail(event=event, participant=participant, promo_code=promo_code,
                        wallet=wallet, amount=amount, operation_id=operation_id)
                return redirect('pay_notify')
            else:
                logger.error(f"Pay Notify Error: Notify hash not valid. {request.POST}")
        else:
            logger.error(f"Could not parse notification {request.POST}")
        return HttpResponse(status=400)


class CreatePay(views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Participant, id=p_id)
        if participant.paid:
            return redirect('pay_ok', event_id)
        amount = event.price
        label = f"e{event_id}_p{p_id}"
        success_uri = request.build_absolute_uri(reverse('pay_ok', args=(event_id,)))
        return render(
            request=request,
            template_name='events/event/pay.html',
            context={
                'title': f'{participant.last_name} {participant.first_name}',
                'event': event,
                'participant': participant,
                'label': label,
                'amount': amount,
                'success_uri': success_uri,
                'receiver': event.wallet.wallet_id,
                'pay_available': is_pay_available(event=event),
            }
        )


class PayOk(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(
            request=request,
            template_name='events/event/pay-ok.html',
            context={
                'event': event,
            }
        )


class PremiumCreatePayView(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        if event.is_premium:
            return redirect('admin_actions', event_id)
        superuser = CustomUser.objects.get(id=1)
        wallet = Wallet.objects.filter(owner=superuser).first()
        label = f"e{event_id}_w{int(wallet.id)}"
        success_uri = request.build_absolute_uri(reverse('pay_premium_ok', args=(event_id,)))
        return render(
            request=request,
            template_name='events/event/pay-premium.html',
            context={
                'event': event,
                'label': label,
                'amount': event.premium_price,
                'success_uri': success_uri,
                'receiver': wallet.wallet_id,
                'pay_available': is_premium_pay_available(event=event),
            }
        )


class PayPremiumOk(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(
            request=request,
            template_name='events/event/pay-premium-ok.html',
            context={
                'event': event,
            }
        )
