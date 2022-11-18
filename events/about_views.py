from django import views
from django.shortcuts import render


class AboutView(views.View):
    @staticmethod
    def get(request):
        return render(request=request,
                      template_name='events/about/about.html')


class HelpView(views.View):
    @staticmethod
    def get(request, type):
        return render(request=request,
                      template_name=f"events/about/{type}.html")
