# project007/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView
from django.views.generic.base import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    # เปลี่ยนเส้นทางจาก URL หลัก ('') ไปยังหน้าล็อกอิน ('accounts/login/')
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    # กำหนด LoginView ให้ใช้ template ของเรา
    path('accounts/login/', LoginView.as_view(template_name='users/login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')), # ยังคงจำเป็นสำหรับ logout และ reset password
    path('borrowing/', include('borrowing.urls')),
    path('', include('users.urls')), # สำหรับ dashboard และ user_dashboard
]
