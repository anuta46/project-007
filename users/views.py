# users/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.conf import settings # จำเป็นสำหรับ MEDIA_URL
from django.http import JsonResponse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.core.mail import EmailMessage

from .models import CustomUser, Organization, Notification # นำเข้า Notification ด้วย
from borrowing.models import Item, Asset, Loan # นำเข้า Asset ด้วย
from .forms import OrganizationRegistrationForm, UserRegistrationForm, LinkBasedUserRegistrationForm
from .tokens import account_activation_token


def register_organization(request):
    if request.method == 'POST':
        org_form = OrganizationRegistrationForm(request.POST)
        user_form = UserRegistrationForm(request.POST)

        if org_form.is_valid() and user_form.is_valid():
            try:
                with transaction.atomic():
                    organization = org_form.save() 
                    user = user_form.save(commit=False)
                    user.organization = organization 
                    user.is_org_admin = True 
                    user.is_active = True 
                    user.save()

                    messages.success(request, 'การลงทะเบียนองค์กรและผู้ดูแลสำเร็จแล้ว! กรุณาล็อกอิน')
                    return redirect('login') 
            except Exception as e:
                messages.error(request, f'เกิดข้อผิดพลาดในการลงทะเบียน: {e}')
    else:
        org_form = OrganizationRegistrationForm()
        user_form = UserRegistrationForm()
    
    context = {
        'org_form': org_form,
        'user_form': user_form
    }
    return render(request, 'users/register_organization.html', context)


@login_required
def dashboard(request):
    # ตรวจสอบว่าเป็น Platform Admin (Superuser) หรือไม่
    if request.user.is_superuser:
        messages.info(request, "ในฐานะ Platform Admin คุณจะถูกนำไปยังหน้า Django Administration Site เพื่อจัดการข้อมูลทั้งหมด")
        return redirect('/admin/') 
    
    # สำหรับ Organization Admin (ผู้ใช้ที่มี is_org_admin = True)
    elif request.user.is_org_admin:
        organization = request.user.organization
        items = Item.objects.filter(organization=organization).order_by('name')
        pending_loans = Loan.objects.filter(asset__item__organization=organization, status='pending').order_by('-borrow_date')
        active_loans = Loan.objects.filter(asset__item__organization=organization, status='approved').order_by('due_date')
        loan_history = Loan.objects.filter(asset__item__organization=organization).exclude(status__in=['pending', 'approved']).order_by('-borrow_date')

        context = {
            'is_superuser_dashboard': False, 
            'organization': organization,
            'items': items,
            'pending_loans': pending_loans,
            'active_loans': active_loans,
            'loan_history': loan_history,
        }
        return render(request, 'users/dashboard.html', context)
    
    # สำหรับผู้ใช้ทั่วไป (ไม่ใช่ทั้ง Superuser และ Organization Admin)
    else:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงแดชบอร์ดนี้")
        return redirect('user_dashboard')


@login_required
def user_dashboard(request):
    """
    View สำหรับผู้ใช้ทั่วไปเพื่อดูรายการอุปกรณ์แต่ละชิ้น (Assets) ที่พร้อมให้ยืมในองค์กรของตน
    """
    # ดึง Asset ทั้งหมดในองค์กรของผู้ใช้ที่มีสถานะ 'available'
    available_assets = Asset.objects.filter(
        item__organization=request.user.organization, 
        status='available'
    ).order_by('item__name', 'serial_number', 'device_id') # เรียงตามชื่อประเภท, SN, ID

    context = {
        'available_assets': available_assets, # เปลี่ยนชื่อ context variable
        'MEDIA_URL': settings.MEDIA_URL, 
    }
    return render(request, 'users/user_dashboard.html', context)


@login_required
def generate_registration_link(request):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์สร้างลิงก์ลงทะเบียน")
        return redirect('dashboard')
    
    if request.method == 'POST':
        organization_id = request.user.organization.id
        registration_link = request.build_absolute_uri(
            f'/register/user-via-link/{organization_id}/'
        )
        messages.success(request, f'ลิงก์ลงทะเบียนผู้ใช้สำหรับองค์กรของคุณถูกสร้างแล้ว: <a href="{registration_link}" target="_blank" class="text-blue-500 hover:underline">{registration_link}</a>')
    
    return redirect('dashboard')


def register_user_via_link(request, organization_id):
    organization = get_object_or_404(Organization, id=organization_id)

    if request.method == 'POST':
        form = LinkBasedUserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.organization = organization
                    user.is_org_admin = False 
                    user.is_active = True 
                    user.save()

                    messages.success(request, f'การลงทะเบียนผู้ใช้สำหรับองค์กร {organization.name} สำเร็จแล้ว! กรุณาเข้าสู่ระบบ')
                    return redirect('login')
            except Exception as e:
                messages.error(request, f'เกิดข้อผิดพลาดในการลงทะเบียน: {e}')
    else:
        form = LinkBasedUserRegistrationForm()
    
    context = {
        'form': form,
        'organization_name': organization.name,
    }
    return render(request, 'users/register_user_from_link.html', context)


@login_required
def manage_organization_users(request):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์จัดการผู้ใช้")
        return redirect('dashboard')
    
    organization = request.user.organization
    organization_users = CustomUser.objects.filter(organization=organization).exclude(id=request.user.id).order_by('username')

    context = {
        'organization_name': organization.name,
        'organization_users': organization_users
    }
    return render(request, 'users/manage_organization_users.html', context)


@login_required
def activate_user(request, user_id):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ดำเนินการนี้")
        return redirect('dashboard')
    
    user_to_activate = get_object_or_404(CustomUser, id=user_id, organization=request.user.organization)
    
    if not user_to_activate.is_active:
        user_to_activate.is_active = True
        user_to_activate.save()
        messages.success(request, f'ผู้ใช้ "{user_to_activate.username}" ถูกเปิดใช้งานแล้ว')
    else:
        messages.info(request, f'ผู้ใช้ "{user_to_activate.username}" ใช้งานอยู่แล้ว')
    
    return redirect('manage_organization_users')


@login_required
def deactivate_user(request, user_id):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ดำเนินการนี้")
        return redirect('dashboard')
    
    user_to_deactivate = get_object_or_404(CustomUser, id=user_id, organization=request.user.organization)
    
    if user_to_deactivate.is_org_admin:
        messages.error(request, "ไม่สามารถปิดใช้งานผู้ดูแลองค์กรได้")
        return redirect('manage_organization_users')

    if user_to_deactivate.is_active:
        user_to_deactivate.is_active = False
        user_to_deactivate.save()
        messages.success(request, f'ผู้ใช้ "{user_to_deactivate.username}" ถูกปิดใช้งานแล้ว')
    else:
        messages.info(request, f'ผู้ใช้ "{user_to_deactivate.username}" ถูกปิดใช้งานอยู่แล้ว')
    
    return redirect('manage_organization_users')


@login_required
def my_borrowed_items_history(request):
    my_loans = Loan.objects.filter(borrower=request.user).order_by('-borrow_date')

    context = {
        'my_loans': my_loans,
    }
    return render(request, 'users/my_borrowed_items_history.html', context)


@login_required
def user_notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    unread_notifications = notifications.filter(is_read=False)
    if unread_notifications.exists():
        unread_notifications.update(is_read=True)

    context = {
        'notifications': notifications
    }
    return render(request, 'users/notifications.html', context)


@login_required
def mark_notification_as_read(request, notification_id):
    if request.method == 'POST':
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'failed', 'message': 'Invalid request method'}, status=405)
