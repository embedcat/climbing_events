from django.urls import path

from events import views

urlpatterns = [
    path('', views.MainView.as_view(), name='main'),
    path('e/<int:event_id>/', views.EventView.as_view(), name='event'),
    path('e/<int:event_id>/admin/', views.EventAdminView.as_view(), name='event_admin'),
    path('e/<int:event_id>/admin_description/', views.EventAdminDescriptionView.as_view(),
         name='event_admin_description'),
    path('e/<int:event_id>/admin_settings/', views.EventAdminSettingsView.as_view(), name='event_admin_settings'),
    path('e/<int:event_id>/enter/', views.EventEnterView.as_view(), name='event_enter'),
    path('e/<int:event_id>/enter_wo_reg/', views.EventEnterWithoutReg.as_view(), name='event_enter_wo_reg'),
    path('e/<int:event_id>/results/', views.EventResultsView.as_view(), name='event_results'),
    # path('e/<int:event_id>/results/', views.EventParticipantsView.as_view(), name='event_results'),
    path('e/<int:event_id>/participants/', views.EventParticipantsView.as_view(), name='event_participants'),
    path('e/<int:event_id>/registration/', views.EventRegistrationView.as_view(), name='event_registration'),
    path('e/<int:event_id>/registration_ok/<int:participant_id>', views.EventRegistrationOkView.as_view(),
         name='event_registration_ok'),
    path('e/<int:event_id>/route_editor/', views.RouteEditor.as_view(), name='route_editor'),
    path('e/<int:event_id>/participants/export', views.ExportParticipantToCsv.as_view(), name='export_participants_to_csv'),
    path('e/<int:event_id>/p/<int:p_id>/', views.ParticipantView.as_view(), name='participant'),
    path('e/<int:event_id>/p/<int:p_id>/routes', views.ParticipantRoutesView.as_view(), name='participant_routes'),

    path('ajax/check_pin_code/', views.check_pin_code, name='check_pin_code'),
]
