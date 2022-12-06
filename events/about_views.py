from django import views
from django.shortcuts import render

from events.pay_views import get_notify_link


class AboutView(views.View):
    @staticmethod
    def get(request):
        return render(request=request,
                      template_name='events/about/about.html')


class HelpView(views.View):
    @staticmethod
    def get(request, type):
        return render(request=request,
                      template_name=f"events/about/{type}.html",
                      context={
                        'notify_link': get_notify_link(request=request) if type == "payment" else None,
                      })
