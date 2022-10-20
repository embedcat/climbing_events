from django import views
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from events.models import Event, Participant


class NotifyView(views.View):
    @staticmethod
    def get(request):
        return HttpResponse(status=200)

    @staticmethod
    def post(request):
        print(request)
        return HttpResponse(status=200)


class CreatePay(views.View):
    @staticmethod
    def get(request, event_id, p_id):
        event = Event.objects.get(id=event_id)
        participant = Participant.objects.get(id=p_id)
        if participant.paid:
            return redirect('pay_ok', event_id)
        amount = event.price
        order_id = f"e{event_id}_p{p_id}_{participant.last_name}_{participant.first_name}"
        success_uri = request.build_absolute_uri(reverse('pay_ok', args=(event_id,)))
        return render(
            request=request,
            template_name='events/event/pay.html',
            context={
                'title': f'{participant.last_name} {participant.first_name}',
                'event': event,
                'participant': participant,
                'order_id': order_id,
                'amount': amount,
                'success_uri': success_uri,
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
