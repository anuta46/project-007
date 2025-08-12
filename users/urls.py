# users/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
]