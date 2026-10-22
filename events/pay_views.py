import base64
import hmac
import logging
import hashlib
from urllib.parse import quote

from django import views
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from config import settings
from events.models import CustomUser, Event, Participant, PayDetail, PromoCode, Wallet
from events import services

logger = logging.getLogger(settings.LOGGER)


def get_notify_link(request) -> str:
    return request.build_absolute_uri(reverse('pay_notify'))


def check_notify_sign(notify: dict, secret: str) -> bool:
    # ЮMoney: HMAC-SHA256 от всех параметров, кроме sign, по алфавиту, значения URL-кодированы по RFC 3986.
    # sha1_hash больше не присылается (с 18.05.2026).
    string = '&'.join(f"{key}={quote(value, safe='')}" for key, value in sorted(notify.items()) if key != 'sign')
    sign = hmac.new(bytes(secret, "UTF-8"), bytes(string, "UTF-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(bytes(sign, "UTF-8"), bytes(notify.get('sign', ''), "UTF-8"))


def is_pay_available(event: Event) -> bool:
    if event.pay_type == Event.PAY_TYPE_YOOMONEY:
        return event.wallet and event.is_pay_allowed
    if event.pay_type == Event.PAY_TYPE_SBP:
        return event.is_pay_allowed
    return False


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
    except (KeyError, ValueError):
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
        # ЮMoney считает уведомление принятым только при ответе 200, иначе повторяет его через 10 минут и через час
        parsed = parse_pay_notification(request.POST)
        if not parsed:
            logger.error(f"Could not parse notification {request.POST}")
            return HttpResponse(status=400)

        event_id = parsed['event_id']
        wallet_id = parsed['wallet_id']
        participant_id = parsed['participant_id']
        promocode_id = parsed['promocode_id']
        operation_id = parsed['operation_id']
        amount = parsed['amount']

        if not event_id:
            # кнопка «Протестировать» в настройках ЮMoney шлёт уведомление с пустым label:
            # подтверждаем его, если подпись сходится с секретом одного из кошельков
            wallet = next((w for w in Wallet.objects.all() if check_notify_sign(request.POST, w.notify_secret_key)),
                          None)
            if wallet:
                logger.info(f"Pay Notify Test: Wallet: {wallet}")
                return HttpResponse(status=200)
            logger.error(f"Pay Notify Error: no event in label, sign matches no wallet. {request.POST}")
            return HttpResponse(status=400)

        event = Event.objects.filter(id=event_id).first()
        wallet = Wallet.objects.filter(id=wallet_id).first() if wallet_id else event and event.wallet
        if not event or not wallet:
            logger.error(f"Pay Notify Error: event or wallet not found. {request.POST}")
            return HttpResponse(status=400)

        if not check_notify_sign(request.POST, wallet.notify_secret_key):
            logger.error(f"Pay Notify Error: Notify sign not valid. {request.POST}")
            return HttpResponse(status=400)

        if wallet_id:
            event.is_premium = True
            event.is_expired = False
            event.save()
            logger.info(f"Pay Premium Notify Success: Event: {event}, Wallet: {wallet}")
            return HttpResponse(status=200)

        if PayDetail.objects.filter(operation_id=operation_id).exists():
            logger.info(f"Pay Notify Duplicate: Event: {event}, operation_id: {operation_id}")
            return HttpResponse(status=200)

        participant = Participant.objects.filter(id=participant_id, event=event).first()
        if not participant:
            logger.error(f"Pay Notify Error: participant not found. {request.POST}")
            return HttpResponse(status=400)
        participant.paid = True
        participant.save()
        promo_code = PromoCode.objects.filter(id=promocode_id).first() if promocode_id else None
        if promo_code:
            promo_code.applied_num = promo_code.applied_num + 1
            promo_code.save()
        logger.info(f"Pay Notify Success: Event: {event}, Participant: {participant}"
                    f"{', PromoCode: ' + promo_code.title if promo_code else ''}")
        services.save_pay_detail(event=event, participant=participant, promo_code=promo_code,
                                 wallet=wallet, amount=amount, operation_id=operation_id)
        return HttpResponse(status=200)


class CreatePay(views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = get_object_or_404(Event, id=event_id)
        participant = get_object_or_404(Participant, id=p_id)
        if participant.paid:
            return redirect('pay_ok', event_id)
        if not is_pay_available(event=event):
            return redirect('pay_unavailable', event_id)

        if event.pay_type == Event.PAY_TYPE_YOOMONEY:
            try:
                amount = int(event.price_list.get(str(participant.reg_type_index), 0)) if event.reg_type_num > 1 else int(event.price)
            except:
                return redirect('pay_unavailable', event_id)

            label = f"e{event_id}_p{p_id}"
            success_uri = request.build_absolute_uri(reverse('pay_ok', args=(event_id,)))
            return render(
                request=request,
                template_name='events/event/pay-yoomoney.html',
                context={
                    'title': f'{participant.last_name} {participant.first_name}',
                    'event': event,
                    'participant': participant,
                    'label': label,
                    'amount': amount,
                    'success_uri': success_uri,
                    'receiver': event.wallet.wallet_id,
                }
            )
        if event.pay_type == Event.PAY_TYPE_SBP:
            qr_uri = event.price_list.get(str(participant.reg_type_index), 0) if event.reg_type_num > 1 else str(event.price)
            qr_code = services.qr_create(text=qr_uri, version=10).getvalue()
            img_str = base64.b64encode(qr_code).decode("utf-8")  # convert to str and cut b'' chars
            parts = qr_uri.split('&')
            amount = 0
            for part in parts:
                if part.startswith('sum='):
                    amount = int(int(part[4:]) / 100)
                    break
            return render(
                request=request,
                template_name='events/event/pay-sbp.html',
                context={
                    'title': f'{participant.last_name} {participant.first_name}',
                    'event': event,
                    'participant': participant,
                    'amount': amount,
                    'qr_uri': qr_uri,
                    'img_str': img_str,
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


class PayUnavailable(views.View):
    @staticmethod
    def get(request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return render(
            request=request,
            template_name='events/event/pay-unavailable.html',
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
