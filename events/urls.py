from django.contrib.auth.views import LogoutView
from django.urls import path

from events import views
from events.views import CustomLoginView, RegisterView

urlpatterns = [
    path('', views.MainView.as_view(), name='main'),
    path('e/<int:event_id>/', views.EventView.as_view(), name='event'),
    path('e/<int:event_id>/admin_actions/', views.AdminActionsView.as_view(), name='admin_actions'),
    path('e/<int:event_id>/admin_description/', views.AdminDescriptionView.as_view(),
         name='admin_description'),
    path('e/<int:event_id>/admin_settings/', views.EventAdminSettingsView.as_view(), name='admin_settings'),
    path('e/<int:event_id>/admin_actions_clear', views.AdminActionsClearView.as_view(), name='admin_actions_clear'),
    path('e/<int:event_id>/admin_protocols', views.AdminProtocolsView.as_view(), name='admin_protocols'),
    path('e/<int:event_id>/admin_protocols/<str:file>', views.ProtocolDownload.as_view(), name='protocol_download'),
    path('async_get_results/<int:event_id>/', views.async_get_results, name='async_get_results'),
    path('e/<int:event_id>/enter/', views.EnterResultsView.as_view(), name='event_enter'),
    path('e/<int:event_id>/enter_wo_reg/', views.EnterWithoutReg.as_view(), name='enter_wo_reg'),
    path('e/<int:event_id>/results/', views.ResultsView.as_view(), name='event_results'),
    path('e/<int:event_id>/participants/', views.EventParticipantsView.as_view(), name='event_participants'),
    path('e/<int:event_id>/registration/', views.EventRegistrationView.as_view(), name='event_registration'),
    path('e/<int:event_id>/registration_ok/<int:participant_id>', views.EventRegistrationOkView.as_view(),
         name='event_registration_ok'),
    path('e/<int:event_id>/route_editor/', views.RouteEditor.as_view(), name='route_editor'),
    path('e/<int:event_id>/participants/export', views.ExportParticipantToCsv.as_view(), name='export_participants_to_csv'),
    path('e/<int:event_id>/p/<int:p_id>/', views.ParticipantView.as_view(), name='participant'),
    path('e/<int:event_id>/p/<int:p_id>/routes', views.ParticipantRoutesView.as_view(), name='participant_routes'),

    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),

    path('ajax/check_pin_code/', views.check_pin_code, name='check_pin_code'),

    path('test/', views.async_get_results, name='test'),
]
