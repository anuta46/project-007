# project007/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static

# ใช้ LoginView ที่กำหนดปลายทางตามบทบาท
from users.views import RoleAwareLoginView

urlpatterns = [
    path('admin/', admin.site.urls),

    # หน้าแรก: เด้งเข้าหน้ารวมบทบาท (จะส่งต่อไปตามบทบาทเอง)
    path('', RedirectView.as_view(url='/post-login/', permanent=False), name='home'),

    # ใช้ RoleAwareLoginView แทน LoginView เดิม
    path('accounts/login/', RoleAwareLoginView.as_view(template_name='users/login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),

    # แยกเส้นทาง borrowing
    path('borrowing/', include('borrowing.urls')),

    # เส้นทางของ users
    path('', include('users.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
