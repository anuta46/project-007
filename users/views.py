# users/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.conf import settings  # จำเป็นสำหรับ MEDIA_URL
from django.http import JsonResponse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.db.models import Q, Count  # Q สำหรับค้นหาแบบ OR, Count สำหรับสรุปสถิติ

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

    context = {'org_form': org_form, 'user_form': user_form}
    return render(request, 'users/register_organization.html', context)


@login_required
def dashboard(request):
    # ถ้าเป็น superuser → ไปหน้า Superuser Dashboard
    if request.user.is_superuser:
        return redirect('superuser_dashboard')

    elif request.user.is_org_admin:
        organization = request.user.organization

        total_item_types = Item.objects.filter(organization=organization).count()
        total_assets = Asset.objects.filter(item__organization=organization).count()
        available_assets_count = Asset.objects.filter(item__organization=organization, status='available').count()
        on_loan_assets_count = Asset.objects.filter(item__organization=organization, status='on_loan').count()

        pending_loan_requests = Loan.objects.filter(
            asset__item__organization=organization, status='pending'
        ).count()

        active_users_count = CustomUser.objects.filter(
            organization=organization, is_active=True
        ).count()

        pending_loans = Loan.objects.filter(
            asset__item__organization=organization, status='pending'
        ).order_by('-borrow_date')

        active_loans = Loan.objects.filter(
            asset__item__organization=organization, status='approved'
        ).order_by('due_date')

        loan_history = Loan.objects.filter(
            asset__item__organization=organization
        ).exclude(status__in=['pending', 'approved']).order_by('-borrow_date')

        context = {
            'is_superuser_dashboard': False,
            'organization': organization,
            'total_item_types': total_item_types,
            'total_assets': total_assets,
            'available_assets_count': available_assets_count,
            'on_loan_assets_count': on_loan_assets_count,
            'pending_loan_requests': pending_loan_requests,
            'active_users_count': active_users_count,
            'pending_loans': pending_loans,
            'active_loans': active_loans,
            'loan_history': loan_history,
        }
        return render(request, 'users/dashboard.html', context)

    # ผู้ใช้องค์กรทั่วไป → ไปหน้า user dashboard
    return redirect('user_dashboard')


@login_required
def user_dashboard(request):
    """
    สำหรับผู้ใช้ทั่วไป: ดูรายการ Asset ในองค์กรของตน
    - ค้นหาด้วย q
    - กรองสถานะด้วย status
    """
    organization = request.user.organization
    queryset = Asset.objects.filter(item__organization=organization)

    # Query params
    query = request.GET.get('q')
    status_filter = request.GET.get('status')

    # ค้นหา
    if query:
        queryset = queryset.filter(
            Q(item__name__icontains=query) |
            Q(serial_number__icontains=query) |
            Q(device_id__icontains=query) |
            Q(item__description__icontains=query)
        )

    # กรองสถานะ
    if status_filter == 'available':
        queryset = queryset.filter(status='available')
    elif status_filter == 'unavailable':
        # แสดงทุกสถานะที่ "ไม่ใช่ available" (เช่น on_loan, maintenance, retired)
        queryset = queryset.exclude(status='available')
    else:
        # ค่าเริ่มต้น: ไม่แสดง on_loan
        queryset = queryset.exclude(status='on_loan')

    available_assets = queryset.order_by('item__name', 'serial_number', 'device_id')

    context = {
        'available_assets': available_assets,
        'MEDIA_URL': settings.MEDIA_URL,
        'current_query': query or '',
        'current_status': status_filter or '',
    }
    return render(request, 'users/user_dashboard.html', context)


@login_required
def generate_registration_link(request):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์สร้างลิงก์ลงทะเบียน")
        return redirect('dashboard')

    organization_id = request.user.organization.id
    registration_link = request.build_absolute_uri(f'/register/user-via-link/{organization_id}/')
    messages.success(
        request,
        f'ลิงก์ลงทะเบียนผู้ใช้สำหรับองค์กรของคุณถูกสร้างแล้ว: '
        f'<a href="{registration_link}" target="_blank" class="text-blue-500 hover:underline">{registration_link}</a>'
    )
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

    context = {'form': form, 'organization_name': organization.name}
    return render(request, 'users/register_user_from_link.html', context)


@login_required
def manage_organization_users(request):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์จัดการผู้ใช้")
        return redirect('dashboard')

    organization = request.user.organization
    organization_users = CustomUser.objects.filter(organization=organization).exclude(id=request.user.id).order_by('username')

    context = {'organization_name': organization.name, 'organization_users': organization_users}
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
    return render(request, 'users/my_borrowed_items_history.html', {'my_loans': my_loans})


@login_required
def user_notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')

    unread_notifications = notifications.filter(is_read=False)
    if unread_notifications.exists():
        unread_notifications.update(is_read=True)

    return render(request, 'users/notifications.html', {'notifications': notifications})


@login_required
def mark_notification_as_read(request, notification_id):
    if request.method == 'POST':
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'failed', 'message': 'Invalid request method'}, status=405)


def _is_superuser(user):
    return user.is_superuser


@login_required
@user_passes_test(_is_superuser)
def superuser_dashboard(request):
    # สรุปจำนวนภาพรวมระบบ
    org_count = Organization.objects.count()
    user_count = CustomUser.objects.count()
    active_user_count = CustomUser.objects.filter(is_active=True).count()
    item_count = Item.objects.count()
    asset_count = Asset.objects.count()

    loans_total = Loan.objects.count()
    loans_pending = Loan.objects.filter(status='pending').count()
    loans_approved = Loan.objects.filter(status='approved').count()
    loans_overdue = Loan.objects.filter(status='overdue').count()
    loans_returned = Loan.objects.filter(status='returned').count()
    loans_rejected = Loan.objects.filter(status='rejected').count()

    # ข้อมูลล่าสุด
    recent_orgs = Organization.objects.order_by('-id')[:8]
    recent_users = CustomUser.objects.order_by('-date_joined')[:8]
    recent_loans = Loan.objects.select_related('asset__item', 'borrower').order_by('-borrow_date')[:10]

    # Top องค์กร/สิ่งของตามจำนวนการยืม
    top_orgs_by_loans = (
        Loan.objects.values('asset__item__organization__name')
        .annotate(total_loans=Count('id')).order_by('-total_loans')[:5]
    )
    top_items_by_loans = (
        Loan.objects.values('asset__item__name')
        .annotate(total_loans=Count('id')).order_by('-total_loans')[:5]
    )

    return render(request, 'users/superuser_dashboard.html', {
        'org_count': org_count,
        'user_count': user_count,
        'active_user_count': active_user_count,
        'item_count': item_count,
        'asset_count': asset_count,
        'loans_total': loans_total,
        'loans_pending': loans_pending,
        'loans_approved': loans_approved,
        'loans_overdue': loans_overdue,
        'loans_returned': loans_returned,
        'loans_rejected': loans_rejected,
        'recent_orgs': recent_orgs,
        'recent_users': recent_users,
        'recent_loans': recent_loans,
        'top_orgs_by_loans': top_orgs_by_loans,
        'top_items_by_loans': top_items_by_loans,
    })
