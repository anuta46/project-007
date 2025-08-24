# users/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.conf import settings
from django.http import JsonResponse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.utils import timezone # เพิ่มบรรทัดนี้เข้ามา

from .models import CustomUser, Organization, Notification # Import Notification
from borrowing.models import Item, Asset, Loan # เพิ่ม Asset เข้ามา
from .forms import OrganizationRegistrationForm, UserRegistrationForm, LinkBasedUserRegistrationForm
from .tokens import account_activation_token # ถ้ามี Token สำหรับ activate user


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
    if request.user.is_superuser:
        messages.info(request, "ในฐานะ Platform Admin คุณจะถูกนำไปยังหน้า Django Administration Site เพื่อจัดการข้อมูลทั้งหมด")
        return redirect('/admin/')
    
    elif request.user.is_org_admin:
        organization = request.user.organization
        
        # ข้อมูลสรุปเดิม
        total_users = CustomUser.objects.filter(organization=organization).count()
        total_item_types = Item.objects.filter(organization=organization).count()
        total_assets = Asset.objects.filter(item__organization=organization).count()
        pending_loans_count = Loan.objects.filter(asset__item__organization=organization, status='pending').count()
        active_loans_count = Loan.objects.filter(asset__item__organization=organization, status='approved').count()

        # เพิ่มข้อมูลสำหรับ Dashboard Cards
        # จำนวนรายการยืม/คืนทั้งหมด (นับ approved, returned, rejected, overdue)
        total_loans_transactions = Loan.objects.filter(
            asset__item__organization=organization
        ).exclude(status='pending').count() # ไม่นับ pending เพราะมีส่วนของมันเอง

        # จำนวนรายการค้างคืน (สถานะ approved และเกิน due_date)
        overdue_loans_count = Loan.objects.filter(
            asset__item__organization=organization,
            status='approved',
            due_date__lt=timezone.now().date() # วันที่ครบกำหนดคืนน้อยกว่าวันนี้
        ).count()

        # จำนวนสมาชิกที่ใช้งาน (ไม่รวม admin ที่ล็อกอินอยู่)
        active_users_count = CustomUser.objects.filter(
            organization=organization,
            is_active=True
        ).exclude(id=request.user.id).count() # ไม่นับตัวแอดมินเอง

        # จำนวนสิ่งของทั้งหมดที่ใช้งานอยู่ (available หรือ on_loan)
        total_active_items = Asset.objects.filter(
            item__organization=organization
        ).filter(status__in=['available', 'on_loan']).count()


        context = {
            'is_superuser_dashboard': False, 
            'organization': organization,
            'total_users': total_users,
            'total_item_types': total_item_types,
            'total_assets': total_assets,
            'pending_loans_count': pending_loans_count,
            'active_loans_count': active_loans_count,
            'total_loans_transactions': total_loans_transactions,
            'overdue_loans_count': overdue_loans_count,
            'active_users_count': active_users_count,
            'total_active_items': total_active_items,
        }
        return render(request, 'users/dashboard.html', context)
    
    else:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงแดชบอร์ดนี้")
        return redirect('user_dashboard')


@login_required
def user_dashboard(request):
    available_assets = Asset.objects.filter(
        item__organization=request.user.organization, 
        status='available'
    ).select_related('item').order_by('item__name', 'serial_number', 'device_id')

    context = {
        'available_assets': available_assets, 
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
            except Exception as e: # บรรทัดนี้คือบรรทัดที่ 158
                messages.error(request, f'เกิดข้อผิดพลาดในการลงทะเบียน: {e}')
        # เพิ่ม else block สำหรับกรณีที่ form ไม่ถูกต้อง
        # เพื่อให้ฟอร์มแสดง error กลับไปที่ผู้ใช้
        else: 
            # ถ้า form ไม่ valid, จะไม่มีการ redirect หรือ error message แบบ global
            # แต่ฟอร์มจะถูกส่งไปที่ template พร้อม error message ในแต่ละ field
            pass 
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
        messages.info(f'ผู้ใช้ "{user_to_deactivate.username}" ถูกปิดใช้งานอยู่แล้ว')
    
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
