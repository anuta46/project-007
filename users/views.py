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
from django.db.models import Q # นำเข้า Q object สำหรับการค้นหาแบบ OR

from .models import CustomUser, Organization, Notification 
from borrowing.models import Item, Asset, Loan 
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
    # ปรับปรุง: การตรวจสอบ is_superuser ควรมาก่อน เพราะ Admin สามารถจัดการทุกอย่างได้
    if request.user.is_superuser:
        messages.info(request, "ในฐานะ Platform Admin คุณจะถูกนำไปยังหน้า Django Administration Site เพื่อจัดการข้อมูลทั้งหมด")
        return redirect('/admin/') 
    
    elif request.user.is_org_admin:
        organization = request.user.organization
        
        # ดึงข้อมูลสำหรับปุ่ม/การ์ดสรุปในแดชบอร์ด
        # Item.objects.filter(organization=organization).count() จะนับ "ประเภทสิ่งของ" (เช่น Laptop Model A)
        total_item_types = Item.objects.filter(organization=organization).count()
        # Asset.objects.filter(item__organization=organization).count() จะนับ "อุปกรณ์แต่ละชิ้น" (เช่น Laptop SN1, Laptop SN2)
        total_assets = Asset.objects.filter(item__organization=organization).count()
        # อุปกรณ์ที่พร้อมให้ยืม
        available_assets_count = Asset.objects.filter(item__organization=organization, status='available').count()
        # อุปกรณ์ที่กำลังถูกยืม
        on_loan_assets_count = Asset.objects.filter(item__organization=organization, status='on_loan').count()
        
        # จำนวนคำขอยืมที่รอดำเนินการ
        pending_loan_requests = Loan.objects.filter(
            asset__item__organization=organization,
            status='pending'
        ).count()

        # จำนวนผู้ใช้ที่ใช้งานอยู่ในองค์กร (ยกเว้น admin ปัจจุบันถ้าไม่ต้องการนับรวม)
        # หากต้องการนับรวม admin ปัจจุบันด้วย ให้ลบ .exclude(id=request.user.id) ออก
        active_users_count = CustomUser.objects.filter(
            organization=organization,
            is_active=True
        ).count()
        
        # กรอง loans ที่เป็น 'approved' สำหรับการแสดงผล 'รายการยืมที่กำลังดำเนินการ'
        # และ 'pending' สำหรับ 'คำขอยืมที่รอดำเนินการ'
        # และ 'returned', 'rejected', 'overdue' สำหรับ 'ประวัติการยืม'
        # เพื่อให้เทมเพลตสามารถเข้าถึงข้อมูลเหล่านี้ได้หากต้องการแสดงรายละเอียด
        pending_loans = Loan.objects.filter(asset__item__organization=organization, status='pending').order_by('-borrow_date')
        active_loans = Loan.objects.filter(asset__item__organization=organization, status='approved').order_by('due_date')
        loan_history = Loan.objects.filter(asset__item__organization=organization).exclude(status__in=['pending', 'approved']).order_by('-borrow_date')


        context = {
            'is_superuser_dashboard': False, 
            'organization': organization,
            # ข้อมูลสรุปสำหรับปุ่ม/การ์ด
            'total_item_types': total_item_types, # จำนวนประเภทสิ่งของทั้งหมด
            'total_assets': total_assets, # จำนวนอุปกรณ์แต่ละชิ้นทั้งหมด
            'available_assets_count': available_assets_count, # จำนวนอุปกรณ์พร้อมให้ยืม
            'on_loan_assets_count': on_loan_assets_count, # จำนวนอุปกรณ์ที่กำลังถูกยืม
            'pending_loan_requests': pending_loan_requests, # จำนวนคำขอยืมที่รอดำเนินการ
            'active_users_count': active_users_count, # จำนวนผู้ใช้ที่ใช้งานอยู่
            
            # ส่ง QuerySet เข้าไปเผื่อต้องการแสดงในตาราง
            'pending_loans': pending_loans,
            'active_loans': active_loans,
            'loan_history': loan_history,
        }
        return render(request, 'users/dashboard.html', context)
    
    else:
        # messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงแดชบอร์ดนี้")
        return redirect('user_dashboard')


@login_required
def user_dashboard(request):
    """
    View สำหรับผู้ใช้ทั่วไปเพื่อดูรายการอุปกรณ์แต่ละชิ้น (Assets) ที่พร้อมให้ยืมในองค์กรของตน
    พร้อมการค้นหาและตัวกรอง
    """
    organization = request.user.organization
    
    # เริ่มต้นด้วย Assets ทั้งหมดในองค์กรของผู้ใช้
    queryset = Asset.objects.filter(item__organization=organization)

    # รับค่าจาก Query Parameters
    query = request.GET.get('q')
    condition_filter = request.GET.get('condition')
    status_filter = request.GET.get('status') 

    # ############## ใช้ตัวกรองการค้นหา (Query Search) ##############
    if query:
        queryset = queryset.filter(
            Q(item__name__icontains=query) | # ค้นหาจากชื่อประเภทสิ่งของ
            Q(serial_number__icontains=query) | # ค้นหาจาก Serial Number
            Q(device_id__icontains=query) | # ค้นหาจาก Device ID
            Q(item__description__icontains=query) # ค้นหาจากรายละเอียดประเภทสิ่งของ
        )

    # ############## ใช้ตัวกรองสภาพ (Condition Filter) ##############
    if condition_filter:
        queryset = queryset.filter(condition=condition_filter)

    # ############## ใช้ตัวกรองสถานะ (Status Filter) ##############
    if status_filter == 'available':
        queryset = queryset.filter(status='available')
    elif status_filter == 'unavailable':
        # 'unavailable' หมายถึงสถานะอื่นๆ ที่ไม่ใช่ 'available' (รวมถึง 'on_loan')
        # แสดงสถานะอื่นๆ ทั้งหมดที่ผู้ดูแลกำหนดว่า 'ไม่พร้อมให้ยืม'
        # โดยการยกเว้น 'available'
        queryset = queryset.exclude(status='available')
    else: # status_filter เป็นค่าว่าง ('') หรือ None (หมายถึง 'ทั้งหมด' หรือไม่มีการกรองสถานะ)
        # ตามคำขอ: อุปกรณ์ที่ถูกยืมไปแล้ว (on_loan) จะไม่แสดงบนหน้าหลักโดยค่าเริ่มต้น
        queryset = queryset.exclude(status='on_loan')

    # เรียงลำดับผลลัพธ์
    available_assets = queryset.order_by('item__name', 'serial_number', 'device_id')

    context = {
        'available_assets': available_assets,
        'MEDIA_URL': settings.MEDIA_URL,
        # ส่งค่าที่ใช้กรองกลับไปที่ template เพื่อคงสถานะการเลือกในฟอร์ม
        'current_query': query if query is not None else '',
        'current_condition': condition_filter if condition_filter is not None else '',
        'current_status': status_filter if status_filter is not None else '',
    }
    return render(request, 'users/user_dashboard.html', context)


@login_required
def generate_registration_link(request):
    """
    View สำหรับ Organization Admin เพื่อสร้างและแสดงลิงก์ลงทะเบียนผู้ใช้
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์สร้างลิงก์ลงทะเบียน")
        return redirect('dashboard')
    
    # ลบเงื่อนไข if request.method == 'POST': ออก เพื่อให้ทำงานได้ทันทีเมื่อมีการคลิก
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
