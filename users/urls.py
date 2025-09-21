# users/urls.py (ตัวอย่างรวม)
from django.urls import path
from . import views

urlpatterns = [
    path('post-login/', views.post_login_redirect, name='post_login'),

    path('dashboard/', views.dashboard, name='dashboard'),
    path('super-dashboard/', views.superuser_dashboard, name='superuser_dashboard'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),

    path('pick-organization/', views.pick_organization, name='pick_organization'),

    path('register-organization/', views.register_organization, name='register_organization'),
    path('register/user/', views.register_user_public, name='register_user_public'),

    path('generate-registration-link/', views.generate_registration_link, name='generate_registration_link'),
    path('register/user-via-link/<int:organization_id>/', views.register_user_via_link, name='register_user_via_link'),

    path('org/users/', views.manage_organization_users, name='manage_organization_users'),
    path('org/users/<int:user_id>/activate/', views.activate_user, name='activate_user'),
    path('org/users/<int:user_id>/deactivate/', views.deactivate_user, name='deactivate_user'),

    path('my-borrowed-items/history/', views.my_borrowed_items_history, name='my_borrowed_items_history'),
    path('notifications/', views.user_notifications, name='user_notifications'),
    path('notifications/read/<int:notification_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),

    path('organizations/', views.organizations_list, name='organizations_list'),
]
