from django import views
from django.http import HttpResponse
from django.shortcuts import render

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
        return render(
            request=request,
            template_name='events/event/pay.html',
            context={
                'title': f'{participant.last_name} {participant.first_name}',
                'event': event,
                'participant': participant,
            }
        )