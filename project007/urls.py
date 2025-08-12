# project007/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')),
    # เปลี่ยนไปใช้ LoginView ที่กำหนด template_name ของเราเอง
    path('accounts/login/', LoginView.as_view(template_name='users/login.html'), name='login'), # แก้ไขบรรทัดนี้
    path('accounts/', include('django.contrib.auth.urls')),
    path('borrowing/', include('borrowing.urls')),
]