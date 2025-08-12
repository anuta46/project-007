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
from .models import CustomUser, Organization 
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

        context = {
            'organization': organization,
            'items': items,
            'pending_loans': pending_loans,
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
    my_loans = Loan.objects.filter(borrower=request.user)
    
    context = {
        'items': items,
        'my_loans': my_loans,
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
    """
    View สำหรับ Organization Admin เพื่อจัดการผู้ใช้ในองค์กรของตนเอง
    แสดงรายชื่อผู้ใช้ทั้งหมดในองค์กร และสถานะของบัญชี
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')
    
    if not request.user.organization:
        messages.error(request, "บัญชีผู้ดูแลองค์กรของคุณยังไม่ได้ถูกผูกกับองค์กร")
        return redirect('dashboard')

    organization = request.user.organization
    # ดึงผู้ใช้ทั้งหมดที่อยู่ในองค์กรเดียวกัน ยกเว้นตัวแอดมินเอง
    organization_users = CustomUser.objects.filter(organization=organization).exclude(id=request.user.id)
    
    context = {
        'organization_users': organization_users,
        'organization_name': organization.name
    }
    return render(request, 'users/manage_organization_users.html', context)


@login_required
def activate_user(request, user_id):
    """
    View สำหรับ Organization Admin เพื่อเปิดใช้งานบัญชีผู้ใช้
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ดำเนินการนี้")
        return redirect('dashboard')

    # ค้นหาผู้ใช้และตรวจสอบว่าเป็นสมาชิกขององค์กรเดียวกัน
    target_user = get_object_or_404(CustomUser, id=user_id, organization=request.user.organization)

    # ป้องกันแอดมินแก้ไขสถานะของตัวเอง
    if target_user == request.user:
        messages.error(request, "คุณไม่สามารถเปิดใช้งานบัญชีของคุณเองได้")
        return redirect('manage_organization_users')

    # ตรวจสอบว่าผู้ใช้ที่กำลังจะเปิดใช้งานไม่ใช่ Platform Admin
    if target_user.is_platform_admin:
        messages.error(request, "คุณไม่สามารถเปิดใช้งานบัญชี Platform Admin ได้")
        return redirect('manage_organization_users')

    target_user.is_active = True
    target_user.save()
    messages.success(request, f"บัญชี '{target_user.username}' ถูกเปิดใช้งานแล้ว")
    return redirect('manage_organization_users')


@login_required
def deactivate_user(request, user_id):
    """
    View สำหรับ Organization Admin เพื่อปิดใช้งานบัญชีผู้ใช้
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ดำเนินการนี้")
        return redirect('dashboard')

    # ค้นหาผู้ใช้และตรวจสอบว่าเป็นสมาชิกขององค์กรเดียวกัน
    target_user = get_object_or_404(CustomUser, id=user_id, organization=request.user.organization)

    # ป้องกันแอดมินแก้ไขสถานะของตัวเอง
    if target_user == request.user:
        messages.error(request, "คุณไม่สามารถปิดใช้งานบัญชีของคุณเองได้")
        return redirect('manage_organization_users')

    # ป้องกันแอดมินปิดใช้งานบัญชี Organization Admin อื่นๆ
    if target_user.is_org_admin:
        messages.error(request, "คุณไม่สามารถปิดใช้งานบัญชีผู้ดูแลองค์กรอื่นได้")
        return redirect('manage_organization_users')

    # ตรวจสอบว่าผู้ใช้ที่กำลังจะปิดใช้งานไม่ใช่ Platform Admin
    if target_user.is_platform_admin:
        messages.error(request, "คุณไม่สามารถปิดใช้งานบัญชี Platform Admin ได้")
        return redirect('manage_organization_users')

    target_user.is_active = False
    target_user.save()
    messages.success(request, f"บัญชี '{target_user.username}' ถูกปิดใช้งานแล้ว")
    return redirect('manage_organization_users')
