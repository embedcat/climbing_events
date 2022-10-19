from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from events.models import Event, Participant, Route, CustomUser


class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'pin', 'gender', 'city', 'set_index', 'group_index', )
    search_fields = ('last_name', 'first_name', 'city', )


class RouteAdmin(admin.ModelAdmin):
    list_display = ('number', 'grade', 'color', 'event',)
    list_filter = ('event',)


class CustomUserAdmin(UserAdmin):
    fieldsets = (
        *UserAdmin.fieldsets,  # original form fieldsets, expanded
        (                      # new fieldset added on to the bottom
            'Custom Field Heading',  # group heading of your choice; set to None for a blank space instead of a header
            {
                'fields': (
                    'yoomoney_wallet_id',
                ),
            },
        ),
    )


admin.site.register(CustomUser, CustomUserAdmin)

admin.site.register(Event)
admin.site.register(Participant, ParticipantAdmin)
admin.site.register(Route, RouteAdmin)
