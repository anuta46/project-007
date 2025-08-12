from django.contrib import admin
from .models import Organization, CustomUser

admin.site.register(Organization)
admin.site.register(CustomUser)