# users/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
    path('register-organization/', views.register_organization, name='register_organization'),
    # URL สำหรับสร้างลิงก์ลงทะเบียน (สำหรับแอดมินองค์กร)
    path('generate-registration-link/', views.generate_registration_link, name='generate_registration_link'), 
    # URL สำหรับผู้ใช้ลงทะเบียนผ่านลิงก์เฉพาะ
    path('register/user-via-link/<int:organization_id>/', views.register_user_via_link, name='register_user_via_link'),
]
