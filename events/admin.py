from django.contrib import admin
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


admin.site.register(CustomUser)
admin.site.register(Event, EventAdmin)
admin.site.register(Participant, ParticipantAdmin)
admin.site.register(Route, RouteAdmin)
admin.site.register(PromoCode)
admin.site.register(Wallet)
