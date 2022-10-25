import logging
import hashlib

from django import views
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from config import settings
from events.models import Event, Participant, PromoCode

logger = logging.getLogger(settings.LOGGER)


def check_notify_hash(notify: dict, secret: str) -> bool:
    string = f"{notify['notification_type']}&{notify['operation_id']}&{notify['amount']}&{notify['currency']}&" \
             f"{notify['datetime']}&{notify['sender']}&{notify['codepro']}&{secret}&{notify['label']}"
    sha1_hash = hashlib.sha1(bytes(string, "UTF-8")).hexdigest()
    return sha1_hash == notify['sha1_hash']


def is_pay_available(event: Event) -> bool:
    return event.wallet and event.is_pay_allowed


class NotifyView(views.View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(NotifyView, self).dispatch(*args, **kwargs)

    @staticmethod
    def get(request):
        return HttpResponse(status=200)

    @staticmethod
    def post(request):
        if True or 'label' in request.POST:
            label = request.POST['label']
            label = label.split('_')
            event_id, participant_id, promocode_id = 0, 0, 0
            for part in label:
                if part.startswith('e'):
                    event_id = int(part[1:])
                if part.startswith('p'):
                    participant_id = int(part[1:])
                if part.startswith('c'):
                    promocode_id = int(part[1:])
            try:
                event = Event.objects.get(id=event_id)
                participant = Participant.objects.get(id=participant_id, event=event)
                promo_code = PromoCode.objects.get(id=promocode_id)
                if check_notify_hash(request.POST, event.wallet.notify_secret_key):
                    participant.paid = True
                    participant.save()
                    promo_code.applied_num = promo_code.applied_num + 1
                    promo_code.save()
                    logger.info(f"Pay Notify Success: Event: {event}, Participant: {participant}{', PromoCode: ' + promo_code if promocode_id else ''}")
                else:
                    logger.error(f"Pay Notify Error: Notify hash not valid. {request.POST}")
            except (Event.DoesNotExist, Participant.DoesNotExist, PromoCode.DoesNotExist) as e:
                logger.error(f"Exception: {e}. {label=}")
        return redirect('pay_notify')


class CreatePay(views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
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
        event = Event.objects.get(id=event_id)
        return render(
            request=request,
            template_name='events/event/pay-ok.html',
            context={
                'event': event,
            }
        )
