# users/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.contrib.sites.shortcuts import get_current_site
from django.utils.html import format_html

# นำเข้าโมเดลจากแอปพลิเคชันที่ถูกต้อง
from .models import CustomUser, Organization, Notification # นำเข้า Notification 
from borrowing.models import Item, Loan 
from .forms import OrganizationRegistrationForm, UserRegistrationForm, LinkBasedUserRegistrationForm


@login_required
def dashboard(request):
    user = request.user
    
    if user.is_platform_admin:
        return redirect('/admin/')
    
    if user.is_org_admin:
        if not user.organization:
            messages.error(request, "บัญชีผู้ดูแลองค์กรของคุณยังไม่ได้ถูกผูกกับองค์กร กรุณาติดต่อผู้ดูแลระบบ.")
            return redirect('login') 

        organization = user.organization
        items = Item.objects.filter(organization=organization)
        pending_loans = Loan.objects.filter(item__organization=organization, status='pending')
        
        active_loans = Loan.objects.filter(item__organization=organization, status='approved')
        
        loan_history = Loan.objects.filter(
            item__organization=organization
        ).exclude(status='pending').order_by('-borrow_date') 

        context = {
            'organization': organization,
            'items': items,
            'pending_loans': pending_loans,
            'active_loans': active_loans, 
            'loan_history': loan_history, 
        }
        return render(request, 'users/dashboard.html', context)
    
    else:
        if not user.organization:
            messages.error(request, "บัญชีของคุณยังไม่ได้ถูกผูกกับองค์กร กรุณาติดต่อผู้ดูแลระบบ.")
            return redirect('login') 
        return redirect('user_dashboard')

@login_required
def user_dashboard(request):
    user = request.user
    if not user.organization:
        messages.error(request, "บัญชีของคุณยังไม่ได้ถูกผูกกับองค์กร กรุณาติดต่อผู้ดูแลระบบ.")
        return redirect('login') 

    organization = user.organization
    items = Item.objects.filter(organization=organization, available_quantity__gt=0)
    
    context = {
        'items': items,
    }
    return render(request, 'users/user_dashboard.html', context)

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
def generate_registration_link(request):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์สร้างลิงก์ลงทะเบียน")
        return redirect('dashboard')

    if not request.user.organization:
        messages.error(request, "บัญชีผู้ดูแลองค์กรของคุณยังไม่ได้ถูกผูกกับองค์กร ไม่สามารถสร้างลิงก์ได้")
        return redirect('dashboard')

    if request.method == 'POST':
        organization_id = request.user.organization.id
        
        current_site = get_current_site(request)
        domain = current_site.domain
        protocol = 'https' if request.is_secure() else 'http'

        registration_link_url = f'{protocol}://{domain}/register/user-via-link/{organization_id}/'
        
        link_html = format_html(
            "สร้างลิงก์ลงทะเบียนสำเร็จ! คัดลอกลิงก์นี้เพื่อแชร์: <br>"
            "<input type='text' value='{}' readonly style='width: 100%; max-width: 500px; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-family: monospace; background-color: #f9f9f9;'>",
            registration_link_url
        )
        messages.info(request, link_html)
    
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

                    messages.success(request, f'คุณได้ลงทะเบียนสำเร็จกับองค์กร "{organization.name}" แล้ว! กรุณาล็อกอิน')
                    return redirect('login')
            except Exception as e:
                messages.error(request, f'เกิดข้อผิดพลาดในการลงทะเบียน: {e}')
    else:
        form = LinkBasedUserRegistrationForm()

    context = {
        'form': form,
        'organization_name': organization.name 
    }
    return render(request, 'users/register_user_from_link.html', context)


@login_required
def manage_organization_users(request):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')
    
    if not request.user.organization:
        messages.error(request, "บัญชีผู้ดูแลองค์กรของคุณยังไม่ได้ถูกผูกกับองค์กร")
        return redirect('dashboard')

    organization = request.user.organization
    organization_users = CustomUser.objects.filter(organization=organization).exclude(id=request.user.id)
    
    context = {
        'organization_users': organization_users,
        'organization_name': organization.name
    }
    return render(request, 'users/manage_organization_users.html', context)


@login_required
def activate_user(request, user_id):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ดำเนินการนี้")
        return redirect('dashboard')

    target_user = get_object_or_404(CustomUser, id=user_id, organization=request.user.organization)

    if target_user == request.user:
        messages.error(request, "คุณไม่สามารถเปิดใช้งานบัญชีของคุณเองได้")
        return redirect('manage_organization_users')

    if target_user.is_platform_admin:
        messages.error(request, "คุณไม่สามารถเปิดใช้งานบัญชี Platform Admin ได้")
        return redirect('manage_organization_users')

    target_user.is_active = True
    target_user.save()
    messages.success(request, f"บัญชี '{target_user.username}' ถูกเปิดใช้งานแล้ว")
    return redirect('manage_organization_users')


@login_required
def deactivate_user(request, user_id):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ดำเนินการนี้")
        return redirect('dashboard')

    target_user = get_object_or_404(CustomUser, id=user_id, organization=request.user.organization)

    if target_user == request.user:
        messages.error(request, "คุณไม่สามารถปิดใช้งานบัญชีของคุณเองได้")
        return redirect('manage_organization_users')

    if target_user.is_org_admin:
        messages.error(request, "คุณไม่สามารถปิดใช้งานบัญชีผู้ดูแลองค์กรอื่นได้")
        return redirect('manage_organization_users')

    if target_user.is_platform_admin:
        messages.error(request, "คุณไม่สามารถปิดใช้งานบัญชี Platform Admin ได้")
        return redirect('manage_organization_users')

    target_user.is_active = False
    target_user.save()
    messages.success(request, f"บัญชี '{target_user.username}' ถูกปิดใช้งานแล้ว")
    return redirect('manage_organization_users')


@login_required
def my_borrowed_items_history(request):
    user = request.user
    if not user.organization:
        messages.error(request, "บัญชีของคุณยังไม่ได้ถูกผูกกับองค์กร กรุณาติดต่อผู้ดูแลระบบ.")
        return redirect('login') 

    my_loans = Loan.objects.filter(borrower=request.user).order_by('-borrow_date')
    
    context = {
        'my_loans': my_loans,
    }
    return render(request, 'users/my_borrowed_items_history.html', context)


@login_required
def user_notifications(request):
    """
    View สำหรับผู้ใช้เพื่อดูรายการการแจ้งเตือนทั้งหมด
    และทำเครื่องหมายการแจ้งเตือนที่ยังไม่ได้อ่านว่าอ่านแล้ว
    """
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # ทำเครื่องหมายการแจ้งเตือนทั้งหมดที่ดึงมาว่าอ่านแล้ว
    # (หรือคุณอาจเพิ่มปุ่ม "Mark all as read" ใน template ก็ได้)
    unread_notifications = notifications.filter(is_read=False)
    for notif in unread_notifications:
        notif.is_read = True
        notif.save()
    # หรือ: unread_notifications.update(is_read=True) เพื่อประสิทธิภาพที่ดีกว่า

    context = {
        'notifications': notifications
    }
    return render(request, 'users/notifications.html', context)


@login_required
def mark_notification_as_read(request, notification_id):
    """
    View สำหรับทำเครื่องหมายการแจ้งเตือนเฉพาะว่าเป็นอ่านแล้ว (via POST request)
    """
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    messages.success(request, "การแจ้งเตือนถูกทำเครื่องหมายว่าอ่านแล้ว")
    return redirect('user_notifications')
