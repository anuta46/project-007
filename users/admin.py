from django.contrib import admin # นำเข้าโมดูล admin ของ Django
from .models import Organization, CustomUser #นำเข้าโมเดล

# ใช้ @admin.register decorator เพื่อลงทะเบียนโมเดลกับ Admin
#
# 1. การตั้งค่าสำหรับโมเดล Organization
@admin.register(Organization) 
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'business_type')
    search_fields = ('name', 'address')

#
# 2. การตั้งค่าสำหรับโมเดล CustomUser
@admin.register(CustomUser)  # ใช้ @admin.register decorator เพื่อลงทะเบียนโมเดลกับ Admin
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'organization', 'is_org_admin', 'is_platform_admin', 'is_staff', 'is_active')
    #list_filter = ('is_org_admin', 'is_platform_admin', 'is_staff', 'is_active', 'organization')
    search_fields = ('username', 'email', 'phone_number', 'organization__name')
    ordering = ('username',)