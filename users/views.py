# users/views.py

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy

from django.db.models import Q, Count, Exists, OuterRef
from django.utils import timezone

from .forms import (
    OrganizationRegistrationForm,
    UserRegistrationForm,
    LinkBasedUserRegistrationForm,
)
from .models import CustomUser, Organization, Notification
from borrowing.models import Item, Asset, Loan


# -------------------------------
# Login ที่เด้งตามบทบาท
# -------------------------------
class RoleAwareLoginView(LoginView):
    """
    ล็อกอินแล้วส่งไปตามบทบาท:
      - superuser      -> superuser_dashboard
      - org admin      -> dashboard ขององค์กรตัวเอง
      - user ทั่วไป    -> ใช้ next ถ้ามี ไม่งั้นไป pick_organization
    """
    def get_success_url(self):
        user = self.request.user
        if user.is_superuser:
            return reverse_lazy('superuser_dashboard')
        if getattr(user, 'is_org_admin', False):
            return reverse_lazy('dashboard')
        next_url = self.get_redirect_url()
        return next_url or reverse_lazy('pick_organization')


@login_required
def post_login_redirect(request):
    if request.user.is_superuser:
        return redirect('superuser_dashboard')
    if getattr(request.user, 'is_org_admin', False):
        return redirect('dashboard')
    return redirect('pick_organization')


# -------------------------------------------------------------------
# ลงทะเบียน "องค์กร + แอดมินขององค์กร"
# -------------------------------------------------------------------
def register_organization(request):
    if request.method == 'POST':
        org_form = OrganizationRegistrationForm(request.POST, request.FILES or None)
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
        # ถ้าไม่ valid -> ตกลงมาด้านล่างเพื่อ render พร้อม errors
    else:
        org_form = OrganizationRegistrationForm()
        user_form = UserRegistrationForm()

    context = {'org_form': org_form, 'user_form': user_form}
    return render(request, 'users/register_organization.html', context)


# -------------------------------------------------------------------
# แดชบอร์ดหลัก (กระโดดไปตามสิทธิ์)
# -------------------------------------------------------------------
@login_required
def dashboard(request):
    # superuser → หน้า Superuser Dashboard
    if request.user.is_superuser:
        return redirect('superuser_dashboard')

    # org admin → dashboard ขององค์กรตัวเอง
    if request.user.is_org_admin:
        organization = request.user.organization

        total_item_types = Item.objects.filter(organization=organization).count()
        total_assets = Asset.objects.filter(item__organization=organization).count()
        available_assets_count = Asset.objects.filter(item__organization=organization, status='available').count()
        on_loan_assets_count = Asset.objects.filter(item__organization=organization, status='on_loan').count()

        pending_loan_requests = Loan.objects.filter(
            asset__item__organization=organization, status='pending'
        ).count()

        overdue_count = Loan.objects.filter(
            asset__item__organization=organization, status='overdue'
        ).count()

        active_users_count = CustomUser.objects.filter(
            organization=organization, is_active=True
        ).count()

        # ⬇️ ปรับ: active = approved + overdue
        active_loans = (
            Loan.objects
            .filter(asset__item__organization=organization, status__in=['approved', 'overdue'])
            .select_related('asset__item', 'borrower')
            .order_by('due_date')
        )

        pending_loans = (
            Loan.objects
            .filter(asset__item__organization=organization, status='pending')
            .select_related('asset__item', 'borrower')
            .order_by('-borrow_date')
        )

        # ⬇️ ปรับ: ย้าย overdue ออกไปจาก history (เพราะยังไม่ปิด)
        loan_history = (
            Loan.objects
            .filter(asset__item__organization=organization)
            .exclude(status__in=['pending', 'approved', 'overdue'])
            .select_related('asset__item', 'borrower')
            .order_by('-borrow_date')
        )

        context = {
            'is_superuser_dashboard': False,
            'organization': organization,
            'total_item_types': total_item_types,
            'total_assets': total_assets,
            'available_assets_count': available_assets_count,
            'on_loan_assets_count': on_loan_assets_count,
            'pending_loan_requests': pending_loan_requests,
            'overdue_count': overdue_count,               # ✅ เพิ่มไว้ใช้แสดงการ์ด/ป้าย
            'active_users_count': active_users_count,
            'pending_loans': pending_loans,
            'active_loans': active_loans,
            'loan_history': loan_history,
        }
        return render(request, 'users/dashboard.html', context)

    # ผู้ใช้ทั่วไป → เด้งไป user dashboard (จะบังคับเลือกองค์กรก่อน)
    return redirect('user_dashboard')


# -------------------------------------------------------------------
# USER DASHBOARD: ใช้ current_org_id ใน session (ทุกองค์กรยืมเสรี)
# -------------------------------------------------------------------
@login_required
def user_dashboard(request):
    current_org_id = request.session.get('current_org_id')
    if not current_org_id:
        return redirect('pick_organization')

    queryset = Asset.objects.filter(
        item__organization_id=current_org_id
    ).select_related('item')

    query = (request.GET.get('q') or '').strip()
    status_filter = (request.GET.get('status') or 'available').strip().lower()

    # ค้นหา
    if query:
        queryset = queryset.filter(
            Q(item__name__icontains=query) |
            Q(serial_number__icontains=query) |
            Q(device_id__icontains=query) |
            Q(item__description__icontains=query)
        )

    # กรองสถานะสินทรัพย์ตามตัวกรองเดิม
    if status_filter == 'available':
        queryset = queryset.filter(status='available')
    elif status_filter == 'unavailable':
        queryset = queryset.exclude(status='available')  # on_loan/maintenance/retired
    elif status_filter == 'all':
        pass
    else:
        queryset = queryset.filter(status='available')
        status_filter = 'available'

    # ====== ใส่ธง "จองแล้ว" ======
    # นิยาม: มี Loan ที่ status in (pending, approved) และกำหนดช่วงวันที่ครบ
    today = timezone.localdate()

    overlapping_today = Loan.objects.filter(
        asset_id=OuterRef('pk'),
        status__in=['pending', 'approved'],
        start_date__isnull=False,
        due_date__isnull=False,
        start_date__lte=today,
        due_date__gte=today,
    )

    future_reservation = Loan.objects.filter(
        asset_id=OuterRef('pk'),
        status__in=['pending', 'approved'],
        start_date__isnull=False,
        start_date__gt=today,
    )

    queryset = queryset.annotate(
        reserved_now=Exists(overlapping_today),
        reserved_future=Exists(future_reservation),
    )
    # ============================

    available_assets = queryset.order_by('item__name', 'serial_number', 'device_id')

    context = {
        'available_assets': available_assets,
        'MEDIA_URL': settings.MEDIA_URL,
        'current_query': query,
        'current_status': status_filter,
    }
    return render(request, 'users/user_dashboard.html', context)

# -------------------------------------------------------------------
# สมัครผู้ใช้ "ผ่านแพลตฟอร์ม" (ไม่ใช้ลิงก์)
# -------------------------------------------------------------------
def register_user_public(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES or None)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.organization = None
            user.is_org_admin = False
            user.save()
            messages.success(request, 'สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'users/register_user_public.html', {'form': form})


# -------------------------------------------------------------------
# หน้า public แสดงรายชื่อองค์กรทั้งหมด
# -------------------------------------------------------------------
def organizations_list(request):
    q = (request.GET.get('q') or '').strip()
    orgs = Organization.objects.all()
    if q:
        orgs = orgs.filter(name__icontains=q)
    orgs = orgs.order_by('name')
    return render(request, 'users/organizations_list.html', {'orgs': orgs})


# -------------------------------------------------------------------
# เลือก "องค์กรที่จะยืม" หลังล็อกอิน (ทุกองค์กรเลือกได้)
# -------------------------------------------------------------------
@login_required
def pick_organization(request):
    orgs = Organization.objects.all().order_by('name')

    if request.method == 'POST':
        org_id = request.POST.get('organization_id')
        org = get_object_or_404(Organization, id=org_id)
        request.session['current_org_id'] = org.id
        messages.success(request, f'เลือกองค์กร "{org.name}" เรียบร้อย')
        return redirect('user_dashboard')

    return render(request, 'users/pick_organization.html', {'orgs': orgs})


# -------------------------------------------------------------------
# จัดการผู้ใช้ในองค์กร (สำหรับแอดมินองค์กรของตนเท่านั้น)
# -------------------------------------------------------------------
@login_required
def manage_organization_users(request):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์จัดการผู้ใช้")
        return redirect('dashboard')

    organization = request.user.organization
    organization_users = CustomUser.objects.filter(
        organization=organization
    ).exclude(id=request.user.id).order_by('username')

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

    user_to_activate = get_object_or_404(
        CustomUser, id=user_id, organization=request.user.organization
    )

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

    user_to_deactivate = get_object_or_404(
        CustomUser, id=user_id, organization=request.user.organization
    )

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


# -------------------------------------------------------------------
# ประวัติการยืมของฉัน / การแจ้งเตือน
# -------------------------------------------------------------------
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


# -------------------------------------------------------------------
# Superuser Dashboard (ภาพรวมทั้งแพลตฟอร์ม)
# -------------------------------------------------------------------
def _is_superuser(user):
    return user.is_superuser


@login_required
@user_passes_test(_is_superuser)
def superuser_dashboard(request):
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

    recent_orgs = Organization.objects.order_by('-id')[:8]
    recent_users = CustomUser.objects.order_by('-date_joined')[:8]
    recent_loans = Loan.objects.select_related('asset__item', 'borrower').order_by('-borrow_date')[:10]

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


# -------------------------------------------------------------------
# ลงทะเบียนผู้ใช้ผ่านลิงก์เชิญ (เก็บไว้ใช้เผื่ออนาคต)
# -------------------------------------------------------------------
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
