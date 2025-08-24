# project007/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView
from django.views.generic.base import RedirectView

# Import settings and static for media files
from django.conf import settings
from django.conf.urls.static import static # ตรวจสอบว่าบรรทัดนี้มีอยู่

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/user-dashboard/', permanent=False), name='home'),
    path('accounts/login/', LoginView.as_view(template_name='users/login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('borrowing/', include('borrowing.urls')),
    path('', include('users.urls')),
]

# เพิ่ม URL สำหรับ Media Files (เฉพาะตอน DEBUG เท่านั้น)
if settings.DEBUG: # ตรวจสอบว่ามี if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) # ตรวจสอบบรรทัดนี้
