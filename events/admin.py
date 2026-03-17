from django.contrib import admin
from django.db.models import Count
from events.models import Event, Participant, Route, CustomUser, PromoCode, Wallet


class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'id')
    list_filter = ('owner', )
    search_fields = ('title', )


class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'pin', 'gender', 'city', 'set_index', 'group_index', 'event', )
    list_filter = ('event', )
    search_fields = ('last_name', 'first_name', 'city', )


class RouteAdmin(admin.ModelAdmin):
    list_display = ('number', 'grade', 'color', 'event',)
    list_filter = ('event',)


class CustomUserAdmin(admin.ModelAdmin):
    model = CustomUser
    list_display = ('email', 'date_joined', 'last_login', 'get_events_count',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(events_count=Count('owner'))

    @admin.display(description='Events count')
    def get_events_count(self, obj):
        return obj.events_count


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Participant, ParticipantAdmin)
admin.site.register(Route, RouteAdmin)
admin.site.register(PromoCode)
admin.site.register(Wallet)
