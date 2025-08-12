# users/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ... (URL อื่นๆ ที่มีอยู่เดิม เช่น dashboard, user_dashboard) ...
    path('dashboard/', views.dashboard, name='dashboard'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
    path('register-organization/', views.register_organization, name='register_organization'), # เพิ่มบรรทัดนี้
]
