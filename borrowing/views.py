# borrowing/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.forms import inlineformset_factory
from django.db import transaction
from django.db.models import Q, Prefetch
from django.conf import settings

from .forms import ItemForm, AssetForm, LoanRequestForm, AssetCreateForm, ItemCategoryForm
from .models import Item, Asset, Loan
from users.models import Notification, CustomUser

# -------------------------------------------------------------------
# Utils
# -------------------------------------------------------------------
def check_admin_permission(request):
    if not getattr(request.user, 'is_org_admin', False):
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('user_dashboard')
    if not getattr(request.user, 'organization_id', None):
        messages.error(request, "บัญชีของคุณยังไม่ถูกผูกกับองค์กร กรุณาเลือกองค์กร")
        return redirect('pick_organization')
    return None

# -------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------
@login_required
def dashboard(request):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    org = request.user.organization

    pending_loan_requests = Loan.objects.filter(
        asset__item__organization=org, status='pending'
    ).count()

    active_loans = Loan.objects.filter(
        asset__item__organization=org, status='approved'
    ).select_related('asset__item', 'borrower').order_by('due_date')

    total_assets = Asset.objects.filter(item__organization=org).count()
    available_assets_count = Asset.objects.filter(item__organization=org, status='available').count()
    total_item_types = Item.objects.filter(organization=org).count()
    active_users_count = CustomUser.objects.filter(organization=org, is_active=True).count()

    context = {
        'pending_loan_requests': pending_loan_requests,
        'active_loans': active_loans,             # คงชื่อเดิมให้เทมเพลตเดิมทำงาน
        'active_loans_count': active_loans.count(),
        'total_assets': total_assets,
        'available_assets_count': available_assets_count,
        'total_item_types': total_item_types,
        'active_users_count': active_users_count,
        'organization': org,
    }
    return render(request, 'borrowing/dashboard.html', context)

# -------------------------------------------------------------------
# Items & Assets
# -------------------------------------------------------------------
@login_required
def add_item(request):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    AssetFormSet = inlineformset_factory(Item, Asset, form=AssetForm, extra=1, can_delete=True)

    if request.method == 'POST':
        item_form = ItemForm(request.POST, request.FILES)
        asset_formset = AssetFormSet(request.POST, prefix='asset')

        if item_form.is_valid():
            with transaction.atomic():
                try:
                    item = item_form.save(commit=False)
                    item.organization = request.user.organization
                    item.save()

                    asset_formset = AssetFormSet(request.POST, prefix='asset', instance=item)
                    if asset_formset.is_valid():
                        asset_formset.save()
                        messages.success(request, f'เพิ่ม "{item.name}" และอุปกรณ์ในชุดเรียบร้อย')
                        return redirect('item_overview')
                    else:
                        raise ValueError("Asset formset failed validation.")
                except Exception:
                    messages.error(request, 'เกิดข้อผิดพลาดในการบันทึก: โปรดตรวจสอบฟอร์มอุปกรณ์อีกครั้ง')
                    asset_formset = AssetFormSet(request.POST, prefix='asset')
    else:
        item_form = ItemForm()
        asset_formset = AssetFormSet(prefix='asset')

    return render(request, 'borrowing/add_item.html', {
        'item_form': item_form,
        'asset_formset': asset_formset,
    })

@login_required
def edit_item(request, item_id):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    item = get_object_or_404(Item, pk=item_id, organization=request.user.organization)

    AssetFormSet = inlineformset_factory(Item, Asset, form=AssetForm, extra=0, can_delete=True)

    if request.method == 'POST':
        item_form = ItemForm(request.POST, request.FILES, instance=item)
        asset_formset = AssetFormSet(request.POST, instance=item, prefix='asset')
        if item_form.is_valid() and asset_formset.is_valid():
            with transaction.atomic():
                item_form.save()
                asset_formset.save()
            messages.success(request, f'ประเภทสิ่งของ "{item.name}" และอุปกรณ์ถูกแก้ไขเรียบร้อยแล้ว')
            return redirect('item_overview')
    else:
        item_form = ItemForm(instance=item)
        asset_formset = AssetFormSet(instance=item, prefix='asset')

    return render(request, 'borrowing/edit_item.html', {
        'item_form': item_form,
        'asset_formset': asset_formset,
        'item': item,
    })

@login_required
def delete_asset(request, asset_id):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    asset = get_object_or_404(Asset, id=asset_id, item__organization=request.user.organization)
    item_id_of_asset = asset.item.id

    # กันลบถ้ามีคำขอหรือจอง หรือกำลังยืมจริง
    if (
        Loan.objects.filter(asset=asset, status__in=['pending', 'approved']).exists()
        or asset.status == 'on_loan'
    ):
        messages.error(
            request,
            f'ไม่สามารถลบอุปกรณ์ "{asset.item.name}" (SN/ID: {asset.serial_number or asset.device_id or asset.id}) ได้ เนื่องจากมีการยืมที่ยังใช้งานอยู่'
        )
        return redirect('edit_item', item_id=item_id_of_asset)

    if request.method == 'POST':
        asset.delete()
        messages.success(request, f'อุปกรณ์ "{asset.item.name}" ถูกลบเรียบร้อยแล้ว')
        return redirect('edit_item', item_id=item_id_of_asset)

    return redirect('edit_item', item_id=item_id_of_asset)

@login_required
def delete_item(request, item_id):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    item = get_object_or_404(Item, id=item_id, organization=request.user.organization)

    if item.assets.exists():
        messages.error(
            request,
            f'ไม่สามารถลบประเภทสิ่งของ "{item.name}" ได้ เนื่องจากมีอุปกรณ์ ({item.assets.count()} ชิ้น) ผูกอยู่'
        )
        return redirect('item_overview')

    if request.method == 'POST':
        item.delete()
        messages.success(request, f'ประเภทสิ่งของ "{item.name}" ถูกลบเรียบร้อยแล้ว')
        return redirect('item_overview')

    messages.info(request, f'กำลังพยายามลบประเภทสิ่งของ "{item.name}" กรุณายืนยันอีกครั้ง')
    return redirect('item_overview')

# -------------------------------------------------------------------
# Loans (admin actions)
# -------------------------------------------------------------------
@login_required
def approve_loan(request, loan_id):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    loan = get_object_or_404(
        Loan, id=loan_id, asset__item__organization=request.user.organization
    )

    if loan.status != 'pending':
        messages.error(request, 'คำขอยืมนี้ไม่สามารถอนุมัติได้')
        return redirect('pending_loans_view')

    if not loan.start_date or not loan.due_date:
        messages.error(request, 'กรุณาระบุช่วงวันที่ให้ครบก่อนอนุมัติ')
        return redirect('pending_loans_view')

    with transaction.atomic():
        loan_locked = Loan.objects.select_for_update().get(id=loan.id)
        conflict = Loan.objects.filter(
            asset=loan_locked.asset,
            status='approved',
            start_date__lte=loan_locked.due_date,
            due_date__gte=loan_locked.start_date,
        ).exclude(id=loan_locked.id).exists()
        if conflict:
            messages.error(
                request,
                (f"ไม่สามารถอนุมัติได้: มีการอนุมัติ/จอง '{loan_locked.asset.item.name}' "
                 f"ทับช่วง {loan_locked.start_date:%d/%m}-{loan_locked.due_date:%d/%m}")
            )
            return redirect('pending_loans_view')

        loan_locked.status = 'approved'
        loan_locked.approved_at = timezone.now()
        loan_locked.save(update_fields=['status', 'approved_at'])

        Notification.objects.create(
            user=loan_locked.borrower,
            message=(f'คำขอยืม "{loan_locked.asset.item.name}" ได้รับอนุมัติแล้ว '
                     f'(ยืม: {loan_locked.start_date:%d/%m} คืน: {loan_locked.due_date:%d/%m})')
        )

    messages.success(
        request,
        f'อนุมัติคำขอยืม "{loan.asset.item.name}" แล้ว (จอง {loan.start_date:%d/%m/%Y} ถึง {loan.due_date:%d/%m/%Y})'
    )
    return redirect('pending_loans_view')

@login_required
def start_loan(request, loan_id):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    loan = get_object_or_404(
        Loan, id=loan_id, asset__item__organization=request.user.organization
    )

    if loan.status != 'approved':
        messages.error(request, "ทำได้เฉพาะรายการที่อนุมัติแล้ว")
        return redirect('active_loans_view')

    today = timezone.now().date()
    tolerance_days = getattr(settings, 'PICKUP_TOLERANCE_DAYS', 0)

    if loan.start_date and today < (loan.start_date - timedelta(days=tolerance_days)):
        messages.error(request, f'ยังไม่ถึงวันเริ่มใช้ ({loan.start_date:%d/%m/%Y})')
        return redirect('active_loans_view')

    with transaction.atomic():
        asset = Asset.objects.select_for_update().get(id=loan.asset_id)
        if asset.status != 'available':
            messages.error(request, f'อุปกรณ์ไม่พร้อม (สถานะ: {asset.get_status_display()})')
            return redirect('active_loans_view')

        asset.status = 'on_loan'
        asset.save(update_fields=['status'])

        loan.pickup_date = timezone.now()
        loan.save(update_fields=['pickup_date'])

        Notification.objects.create(
            user=loan.borrower,
            message=f'อุปกรณ์ "{loan.asset.item.name}" ถูกบันทึกว่า "เริ่มยืม" แล้ว'
        )

    messages.success(request, f'เริ่มยืม "{loan.asset.item.name}" เรียบร้อย')
    return redirect('active_loans_view')

@login_required
def reject_loan(request, loan_id):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    loan = get_object_or_404(
        Loan, id=loan_id, asset__item__organization=request.user.organization
    )

    if loan.status not in ['pending', 'approved']:
        messages.error(request, "คำขอยืมนี้ไม่สามารถปฏิเสธได้")
        return redirect('dashboard')

    with transaction.atomic():
        asset = Asset.objects.select_for_update().get(id=loan.asset_id)
        if asset.status == 'on_loan':
            messages.error(request, "รายการนี้เริ่มยืมแล้ว ไม่สามารถปฏิเสธได้")
            return redirect('active_loans_view')

        loan.status = 'rejected'
        loan.save(update_fields=['status'])

        if asset.status != 'available':
            asset.status = 'available'
            asset.save(update_fields=['status'])

        Notification.objects.create(
            user=loan.borrower,
            message=f'คำขอยืม "{loan.asset.item.name}" ของคุณถูกปฏิเสธ'
        )

    messages.success(request, f'ปฏิเสธคำขอยืม "{loan.asset.item.name}" แล้ว')
    return redirect('pending_loans_view')

# -------------------------------------------------------------------
# Reports
# -------------------------------------------------------------------
@login_required
def weekly_report(request):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    org = request.user.organization
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    loans = Loan.objects.filter(
        asset__item__organization=org,
        borrow_date__date__range=[start_of_week, end_of_week]
    ).select_related('asset__item', 'borrower').order_by('-borrow_date')

    context = {
        'report_title': 'รายงานประจำสัปดาห์',
        'report_period': f'{start_of_week:%d/%m/%Y} - {end_of_week:%d/%m/%Y}',
        'loans': loans,
        'total_loans': loans.count(),
        'returned_loans': loans.filter(status='returned').count(),
        'approved_loans': loans.filter(status='approved').count(),
        'pending_loans': loans.filter(status='pending').count(),
        'overdue_loans': loans.filter(status='approved', due_date__lt=today).count(),
        'organization_name': org.name,
    }
    return render(request, 'borrowing/weekly_report.html', context)

@login_required
def monthly_report(request):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    org = request.user.organization
    today = timezone.now().date()
    year, month = today.year, today.month

    first_day = today.replace(day=1)
    last_day = (today.replace(year=year + 1, month=1, day=1) - timedelta(days=1)) if month == 12 \
        else (today.replace(month=month + 1, day=1) - timedelta(days=1))

    loans = Loan.objects.filter(
        asset__item__organization=org,
        borrow_date__date__range=[first_day, last_day]
    ).select_related('asset__item', 'borrower').order_by('-borrow_date')

    context = {
        'report_title': 'รายงานประจำเดือน',
        'report_period': f'เดือน {first_day.strftime("%B %Y")}',
        'loans': loans,
        'total_loans': loans.count(),
        'returned_loans': loans.filter(status='returned').count(),
        'approved_loans': loans.filter(status='approved').count(),
        'pending_loans': loans.filter(status='pending').count(),
        'overdue_loans': loans.filter(status='approved', due_date__lt=today).count(),
        'organization_name': org.name,
    }
    return render(request, 'borrowing/monthly_report.html', context)

# -------------------------------------------------------------------
# User-facing loan request/return
# -------------------------------------------------------------------
@login_required
def borrow_item(request, asset_id):
    """
    ผู้ใช้สามารถยื่นขอยืมอุปกรณ์จาก 'ทุกองค์กร' ได้
    - ไม่กรองด้วย request.user.organization อีกต่อไป
    - แอดมินที่จะได้รับแจ้งคือแอดมินของ 'องค์กรที่เป็นเจ้าของอุปกรณ์'
    """
    # ✅ ไม่กรองด้วย item__organization=request.user.organization แล้ว
    asset = get_object_or_404(
        Asset.objects.select_related("item__organization"),
        id=asset_id
    )

    if request.method == 'POST':
        form = LoanRequestForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            due_date = form.cleaned_data['due_date']
            reason = form.cleaned_data['reason']

            with transaction.atomic():
                # ล็อก asset กันแข่งกันยืม
                asset_locked = Asset.objects.select_for_update().select_related("item__organization").get(id=asset_id)

                # กันทับช่วง (pending/approved/on_loan)
                conflict = Loan.objects.filter(
                    asset=asset_locked,
                    status__in=['pending', 'approved', 'on_loan'],
                    start_date__lte=due_date,
                    due_date__gte=start_date,
                ).exists()
                if conflict:
                    messages.error(
                        request,
                        f"มีการจองอุปกรณ์ชิ้นนี้ทับช่วงวันที่ {start_date:%d/%m/%Y} ถึง {due_date:%d/%m/%Y} แล้ว กรุณาเลือกช่วงอื่น"
                    )
                    return redirect('user_dashboard')

                # สร้างคำขอ
                Loan.objects.create(
                    asset=asset_locked,
                    borrower=request.user,
                    reason=reason,
                    start_date=start_date,
                    due_date=due_date,
                    status='pending',
                )

                # ✅ แจ้ง 'แอดมินขององค์กรเจ้าของอุปกรณ์'
                admin_users = CustomUser.objects.filter(
                    organization=asset_locked.item.organization,
                    is_org_admin=True,
                    is_active=True
                )
                for admin in admin_users:
                    Notification.objects.create(
                        user=admin,
                        message=f'คำขอยืมใหม่จาก {request.user.get_full_name() or request.user.username} '
                                f'สำหรับ "{asset_locked.item.name}" (องค์กร: {asset_locked.item.organization.name})'
                    )

            messages.success(
                request,
                f'ส่งคำขอยืม "{asset.item.name}" (องค์กร: {asset.item.organization.name}) สำเร็จ โปรดรอแอดมินอนุมัติ'
            )
            return redirect('my_borrowed_items_history')
    else:
        form = LoanRequestForm()

    return render(request, 'borrowing/borrow_item.html', {
        'asset': asset,
        'form': form,
        # เผื่อ template อยากแสดงโลโก้/ชื่อองค์กร
        'owner_org': asset.item.organization, 
    })

@login_required
def return_item(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id, borrower=request.user)

    # คืนได้เมื่ออนุมัติแล้วและอุปกรณ์อยู่สถานะ on_loan
    if loan.status == 'approved' and loan.asset.status == 'on_loan':
        loan.status = 'returned'
        loan.return_date = timezone.now()
        loan.save(update_fields=['status', 'return_date'])

        asset = loan.asset
        asset.status = 'available'
        asset.save(update_fields=['status'])

        messages.success(request, f'บันทึกการคืน "{asset.item.name}" เรียบร้อยแล้ว')
    else:
        messages.error(request, 'ไม่สามารถคืนได้ในขณะนี้')

    return redirect('my_borrowed_items_history')

# -------------------------------------------------------------------
# Admin lists
# -------------------------------------------------------------------
@login_required
def item_overview(request):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    org = request.user.organization

    qs_assets = Asset.objects.only(
        'id', 'item_id', 'serial_number', 'device_id', 'location', 'status'
    ).order_by('id')

    items = (
        Item.objects
        .filter(organization=org)
        .select_related('category')
        .prefetch_related(Prefetch('assets', queryset=qs_assets))  # ใช้ชื่อ related_name = 'assets'
        .order_by('category__name', 'name')
    )

    return render(request, 'borrowing/item_overview.html', {
        'items': items,
        'organization_name': org.name,
    })

@login_required
def pending_loans_view(request):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    org = request.user.organization
    pending_loans = Loan.objects.filter(
        asset__item__organization=org, status='pending'
    ).select_related('asset__item', 'borrower').order_by('-borrow_date')

    return render(request, 'borrowing/pending_loans.html', {
        'pending_loans': pending_loans,
        'organization_name': org.name,
    })

@login_required
def active_loans_view(request):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    org = request.user.organization
    active_loans = Loan.objects.filter(
        asset__item__organization=org, status='approved'
    ).select_related('asset__item', 'borrower').order_by('due_date')

    return render(request, 'borrowing/active_loans.html', {
        'active_loans': active_loans,
        'organization_name': org.name,
    })

@login_required
def loan_history_admin_view(request):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    org = request.user.organization
    loan_history = Loan.objects.filter(
        asset__item__organization=org
    ).exclude(status__in=['pending', 'approved']).select_related('asset__item', 'borrower').order_by('-borrow_date')

    return render(request, 'borrowing/loan_history_admin.html', {
        'loan_history': loan_history,
        'organization_name': org.name,
    })

@login_required
def add_asset(request):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    if request.method == 'POST':
        form = AssetCreateForm(request.POST, user=request.user)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.status = 'available'
            asset.save()
            messages.success(request, f'อุปกรณ์ "{asset.item.name}" ถูกเพิ่มเรียบร้อยแล้ว')
            return redirect('item_overview')
    else:
        form = AssetCreateForm(user=request.user)

    return render(request, 'borrowing/add_asset.html', {
        'form': form,
        'organization_name': request.user.organization.name,
    })

# borrowing/views.py
@login_required
def add_category(request):
    redirect_response = check_admin_permission(request)
    if redirect_response:
        return redirect_response

    if request.method == 'POST':
        form = ItemCategoryForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.icon:
                obj.icon = ''
            obj.save()
            messages.success(request, "เพิ่มหมวดอุปกรณ์เรียบร้อยแล้ว")
            nxt = request.GET.get('next') or request.POST.get('next')
            if nxt:
                return redirect(nxt)
            return redirect('add_item')
    else:
        form = ItemCategoryForm()
    return render(request, 'borrowing/add_category.html', {'form': form})
