# users/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
    path('register-organization/', views.register_organization, name='register_organization'),
    path('generate-registration-link/', views.generate_registration_link, name='generate_registration_link'), 
    path('register/user-via-link/<int:organization_id>/', views.register_user_via_link, name='register_user_via_link'),
    # URL สำหรับจัดการผู้ใช้ในองค์กร
    path('manage-users/', views.manage_organization_users, name='manage_organization_users'),
    # URL สำหรับเปิดใช้งาน/ปิดใช้งานผู้ใช้
    path('manage-users/activate/<int:user_id>/', views.activate_user, name='activate_user'),
    path('manage-users/deactivate/<int:user_id>/', views.deactivate_user, name='deactivate_user'),
]
