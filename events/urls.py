from django.urls import path

from events import views, pay_views, about_views

urlpatterns = [
    path('', views.MainView.as_view(), name='main'),
    path('e/<int:event_id>/', views.EventView.as_view(), name='event'),
    path('e/<int:event_id>/admin_actions/', views.AdminActionsView.as_view(), name='admin_actions'),
    path('e/<int:event_id>/admin_description/', views.AdminDescriptionView.as_view(),
         name='admin_description'),
    path('e/<int:event_id>/admin_settings/', views.AdminSettingsView.as_view(), name='admin_settings'),
    path('e/<int:event_id>/pay_settings/', views.PaySettingsView.as_view(), name='pay_settings'),
    path('e/<int:event_id>/admin_protocols', views.AdminProtocolsView.as_view(), name='admin_protocols'),
    path('e/<int:event_id>/admin_protocols/<str:file>', views.ProtocolDownload.as_view(), name='protocol_download'),
    path('e/<int:event_id>/admin_protocols/<str:file>/remove', views.ProtocolRemove.as_view(), name='protocol_remove'),
    path('async_get_results/<int:event_id>/', views.async_get_results, name='async_get_results'),
    path('e/<int:event_id>/enter/', views.EnterResultsView.as_view(), name='enter_results'),
    path('e/<int:event_id>/enter_ok/', views.EnterResultsOKView.as_view(), name='enter_results_ok'),
    path('e/<int:event_id>/enter_check/', views.EnterCheckView.as_view(), name='enter_check'),
    path('e/<int:event_id>/enter_wo_reg/', views.EnterWithoutReg.as_view(), name='enter_wo_reg'),
    path('e/<int:event_id>/results/', views.ResultsView.as_view(), name='results'),
    path('e/<int:event_id>/participants/', views.ParticipantsView.as_view(), name='participants'),
    path('e/<int:event_id>/registration/', views.RegistrationView.as_view(), name='registration'),
    path('e/<int:event_id>/registration_ok/<int:participant_id>', views.EventRegistrationOkView.as_view(),
         name='event_registration_ok'),
    path('e/<int:event_id>/route_editor/', views.RouteEditor.as_view(), name='route_editor'),
    path('e/<int:event_id>/p/<int:p_id>/', views.ParticipantView.as_view(), name='participant'),
    path('e/<int:event_id>/p/<int:p_id>/routes', views.ParticipantRoutesView.as_view(), name='participant_routes'),
    path('e/<int:event_id>/p/<int:p_id>/remove', views.ParticipantRemoveView.as_view(), name='participant_remove'),
    path('e/<int:event_id>/premium/', views.PremiumSettingsView.as_view(), name='premium_settings'),

    path('create/', views.CreateEventView.as_view(), name='create'),
    path('my_events/', views.MyEventsView.as_view(), name='my_events'),
    path('profile/', views.ProfileView.as_view(), name='profile'),

    path('ajax/check_pin_code/', views.check_pin_code, name='check_pin_code'),
    path('ajax/check_promo_code/', views.check_promo_code, name='check_promo_code'),

    path('pay/notify/', pay_views.NotifyView.as_view(), name='pay_notify'),
    path('pay/<int:event_id>/<int:p_id>/', pay_views.CreatePay.as_view(), name='pay_create'),
    path('pay/ok/<int:event_id>/', pay_views.PayOk.as_view(), name='pay_ok'),

    path('pay_premium/notify/', pay_views.PremiumNotifyView.as_view(), name='pay_premium_notify'),
    path('pay_premium/<int:event_id>/', pay_views.PremiumCreatePayView.as_view(), name='pay_premium_create'),
    path('pay_premium/ok/<int:event_id>/', pay_views.PayPremiumOk.as_view(), name='pay_premium_ok'),

    path('e/<int:event_id>/promocode/<int:promocode_id>/remove/', views.PromoCodeRemove.as_view(),
         name='promocode_remove'),
    path('wallets/', views.WalletsView.as_view(), name='wallets'),
    path('wallet/<int:wallet_id>/', views.WalletView.as_view(), name='wallet'),
    path('wallet/<int:wallet_id>/remove/', views.WalletRemoveView.as_view(), name='wallet_remove'),

    path('about/', about_views.AboutView.as_view(), name='about'),
    path('help/<str:type>/', about_views.HelpView.as_view(), name='help'),

    # path('test/', views.async_get_results, name='test'),
]
