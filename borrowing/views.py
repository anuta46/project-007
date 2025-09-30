from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.forms import inlineformset_factory
from django.db.models import Q  # OR queries
from django.db import transaction  # atomicity
from django.conf import settings  # MEDIA_URL

from .forms import ItemForm, AssetForm, LoanRequestForm, AssetCreateForm
from .models import Item, Asset, Loan
from users.models import Notification, CustomUser
from .forms import ItemCategoryForm 


@login_required
def dashboard(request):
    """
    Main dashboard view for Organization Admins.
    Displays key statistics and a quick overview.
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('user_dashboard')

    organization = request.user.organization

    pending_loan_requests = Loan.objects.filter(
        asset__item__organization=organization,
        status='pending'
    ).count()

    active_loans = Loan.objects.filter(
        asset__item__organization=organization,
        status='approved'
    )

    total_assets = Asset.objects.filter(
        item__organization=organization
    ).count()

    available_assets_count = Asset.objects.filter(
        item__organization=organization,
        status='available'
    ).count()

    total_item_types = Item.objects.filter(
        organization=organization
    ).count()

    active_users_count = CustomUser.objects.filter(
        organization=organization,
        is_active=True
    ).count()

    context = {
        'pending_loan_requests': pending_loan_requests,
        'active_loans': active_loans,
        'total_assets': total_assets,
        'available_assets_count': available_assets_count,
        'total_item_types': total_item_types,
        'active_users_count': active_users_count,
        'organization': organization,
    }

    return render(request, 'borrowing/dashboard.html', context)


@login_required
def add_item(request):
    """
    แอดมินองค์กรเพิ่ม 'ประเภทสิ่งของ' (Item) และสามารถใส่รายการ 'อุปกรณ์' (Asset) ใต้ Item ได้
    - มีหมวดอุปกรณ์ (category)
    - ป้องกัน item ถูกเซฟค้างถ้า asset ไม่ผ่าน โดยใช้ savepoint
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เพิ่มสิ่งของ")
        return redirect('dashboard')

    AssetFormSet = inlineformset_factory(
        Item, Asset, form=AssetForm, extra=1, can_delete=True
    )

    if request.method == 'POST':
        item_form = ItemForm(request.POST, request.FILES)
        # เบื้องต้น bind เพื่อแสดงค่ากลับถ้า item ไม่ valid
        asset_formset = AssetFormSet(request.POST, prefix='asset')

        if item_form.is_valid():
            with transaction.atomic():
                sp = transaction.savepoint()
                try:
                    item = item_form.save(commit=False)
                    item.organization = request.user.organization
                    item.save()

                    # bind ใหม่กับ instance เพื่อ validate/บันทึก asset
                    asset_formset = AssetFormSet(request.POST, prefix='asset', instance=item)

                    if asset_formset.is_valid():
                        asset_formset.save()
                        messages.success(request, f'เพิ่ม "{item.name}" เรียบร้อย')
                        return redirect('item_overview')
                    else:
                        transaction.savepoint_rollback(sp)
                except Exception as e:
                    transaction.savepoint_rollback(sp)
                    messages.error(request, f'เกิดข้อผิดพลาด: {e}')
        # ถ้า item_form ไม่ valid จะตกมาที่ render ด้านล่าง
    else:
        item_form = ItemForm()
        asset_formset = AssetFormSet(prefix='asset')

    return render(request, 'borrowing/add_item.html', {
        'item_form': item_form,
        'asset_formset': asset_formset,
    })


@login_required
def edit_item(request, item_id):
    """
    แก้ไขประเภทสิ่งของ + จัดการอุปกรณ์ด้วย inline formset
    - ถ้าไม่พบ item ขององค์กรนี้ ให้แจ้งข้อความแล้ว redirect (ไม่โยน 404)
    - ใช้ extra=0 กันฟอร์มว่าง
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขสิ่งของ")
        return redirect('dashboard')

    if not getattr(request.user, 'organization_id', None):
        messages.error(request, "บัญชีของคุณยังไม่ถูกผูกกับองค์กร")
        return redirect('dashboard')

    try:
        item = Item.objects.get(pk=item_id, organization=request.user.organization)
    except Item.DoesNotExist:
        messages.error(request, "ไม่พบสิ่งของนี้ในองค์กรของคุณ หรือถูกลบไปแล้ว")
        return redirect('item_overview')

    AssetFormSet = inlineformset_factory(
        Item, Asset,
        form=AssetForm,
        extra=0,
        can_delete=True
    )

    if request.method == 'POST':
        item_form = ItemForm(request.POST, request.FILES, instance=item)
        asset_formset = AssetFormSet(request.POST, instance=item, prefix='asset')

        if item_form.is_valid() and asset_formset.is_valid():
            with transaction.atomic():
                item_form.save()
                asset_formset.save()
            messages.success(request, f'ประเภทสิ่งของ "{item.name}" และอุปกรณ์ถูกแก้ไขเรียบร้อยแล้ว')
            return redirect('dashboard')
    else:
        item_form = ItemForm(instance=item)
        asset_formset = AssetFormSet(instance=item, prefix='asset')

    context = {
        'item_form': item_form,
        'asset_formset': asset_formset,
        'item': item,
    }
    return render(request, 'borrowing/edit_item.html', context)


@login_required
def delete_asset(request, asset_id):
    """
    ลบอุปกรณ์ (เฉพาะอุปกรณ์ในองค์กรของแอดมิน และไม่มีคำขอ/การยืมที่ยังใช้งาน)
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ลบอุปกรณ์")
        return redirect('dashboard')

    asset = get_object_or_404(Asset, id=asset_id, item__organization=request.user.organization)

    # ถ้ามีคำขอที่ยัง pending หรือ approved ห้ามลบ
    if Loan.objects.filter(asset=asset, status__in=['pending', 'approved']).exists():
        messages.error(
            request,
            f'ไม่สามารถลบอุปกรณ์ "{asset.item.name}" (SN/ID: {asset.serial_number or asset.device_id or asset.id}) ได้ เนื่องจากมีการยืมที่ยังใช้งานอยู่ กรุณารอสิ้นสุดการยืมก่อน'
        )
        return redirect('edit_item', item_id=asset.item.id)

    if request.method == 'POST':
        item_id_of_asset = asset.item.id
        asset.delete()
        messages.success(request, f'อุปกรณ์ "{asset.item.name}" ถูกลบเรียบร้อยแล้ว')
        return redirect('edit_item', item_id=item_id_of_asset)

    return redirect('edit_item', item_id=asset.item.id)


@login_required
def delete_item(request, item_id):
    """
    ลบประเภทสิ่งของ (ได้ต่อเมื่อไม่มี Asset ผูกอยู่)
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ลบสิ่งของ")
        return redirect('dashboard')

    item = get_object_or_404(Item, id=item_id, organization=request.user.organization)

    if item.assets.exists():
        messages.error(
            request,
            f'ไม่สามารถลบประเภทสิ่งของ "{item.name}" ได้ เนื่องจากมีอุปกรณ์ ({item.assets.count()} ชิ้น) ผูกอยู่ กรุณาลบอุปกรณ์แต่ละชิ้นก่อน'
        )
        return redirect('dashboard')

    if request.method == 'POST':
        item.delete()
        messages.success(request, f'ประเภทสิ่งของ "{item.name}" ถูกลบเรียบร้อยแล้ว')
        return redirect('dashboard')

    messages.info(request, f'คุณกำลังจะลบประเภทสิ่งของ "{item.name}" หากต้องการยืนยัน โปรดใช้ปุ่มลบจากหน้าแดชบอร์ด.')
    return redirect('dashboard')


@login_required
def borrow_item(request, asset_id):
    asset = get_object_or_404(Asset, id=asset_id)

    if request.method == 'POST':
        form = LoanRequestForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            due_date = form.cleaned_data['due_date']
            reason = form.cleaned_data['reason']

            with transaction.atomic():
                # ล็อก asset เพื่อกัน race
                asset_locked = Asset.objects.select_for_update().get(id=asset_id)

                # ตรวจสอบ "ทับช่วงเวลา" กับคำขอ/ที่อนุมัติไปแล้ว
                conflict = Loan.objects.select_for_update().filter(
                    asset=asset_locked,
                    status__in=['pending', 'approved'],
                    start_date__lte=due_date,
                    due_date__gte=start_date,
                ).exists()
                if conflict:
                    messages.error(request, "มีการจองอุปกรณ์ชิ้นนี้ทับช่วงวันที่เลือกไว้ กรุณาเลือกช่วงอื่น")
                    return redirect('user_dashboard')

                # สร้างคำขอ (ยังไม่เปลี่ยนสถานะ asset)
                Loan.objects.create(
                    asset=asset_locked,
                    borrower=request.user,
                    reason=reason,
                    start_date=start_date,
                    due_date=due_date,
                    status='pending'
                )

            messages.success(request, f'ส่งคำขอยืม "{asset.item.name}" สำเร็จ โปรดรอแอดมินอนุมัติ')
            # แจ้งเตือนแอดมิน (คงโค้ดเดิมของคุณที่สร้าง Notification)
            return redirect('user_dashboard')
    else:
        form = LoanRequestForm()

    return render(request, 'borrowing/borrow_item.html', {
        'asset': asset,
        'form': form,
        'MEDIA_URL': 'media/'
    })


@login_required
def return_item(request, loan_id):
    """
    ผู้ใช้คืนอุปกรณ์ของตนเอง
    """
    loan = get_object_or_404(Loan, id=loan_id, borrower=request.user)

    if loan.status == 'approved':
        loan.status = 'returned'
        loan.return_date = timezone.now()
        loan.save()

        asset = loan.asset
        asset.status = 'available'
        asset.save()

        messages.success(request, f'คุณได้คืนสิ่งของ "{asset.item.name}" (SN/ID: {asset.serial_number or asset.device_id or asset.id}) เรียบร้อยแล้ว')
    else:
        messages.error(request, 'สิ่งของนี้ไม่สามารถคืนได้ในขณะนี้')

    return redirect('my_borrowed_items_history')


@login_required
def approve_loan(request, loan_id):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์อนุมัติคำขอเหล่านี้")
        return redirect('dashboard')

    loan = get_object_or_404(Loan, id=loan_id)

    if loan.status != 'pending':
        messages.error(request, 'คำขอยืมนี้ไม่สามารถอนุมัติได้')
        return redirect('dashboard')

    with transaction.atomic():
        # กันจองทับช่วงอีกชั้นก่อนอนุมัติ
        conflict = Loan.objects.select_for_update().filter(
            asset=loan.asset,
            status='approved',
            start_date__lte=loan.due_date,
            due_date__gte=loan.start_date,
        ).exclude(id=loan.id).exists()
        if conflict:
            messages.error(request, "มีการอนุมัติ/จองทับช่วงกับคำขอนี้แล้ว")
            return redirect('dashboard')

        loan.status = 'approved'
        loan.approved_at = timezone.now()
        # ✅ อย่าไปเซ็ต loan.borrow_date ที่นี่ (ปล่อยเป็นเวลาส่งคำขอ)
        loan.save(update_fields=['status', 'approved_at'])

    messages.success(
        request,
        f'อนุมัติคำขอยืม "{loan.asset.item.name}" แล้ว (จอง {loan.start_date:%d/%m/%Y} ถึง {loan.due_date:%d/%m/%Y})'
    )
    return redirect('dashboard')


# ############## VIEWS FOR REPORTS ##############
@login_required
def weekly_report(request):
    """
    รายงานประจำสัปดาห์
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงรายงานนี้")
        return redirect('dashboard')

    organization = request.user.organization

    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    loans_this_week = Loan.objects.filter(
        asset__item__organization=organization,
        borrow_date__date__range=[start_of_week, end_of_week]
    ).select_related('asset__item', 'borrower').order_by('-borrow_date')

    total_loans_this_week = loans_this_week.count()
    returned_this_week = loans_this_week.filter(status='returned').count()
    approved_this_week = loans_this_week.filter(status='approved').count()
    pending_this_week = loans_this_week.filter(status='pending').count()
    overdue_this_week = loans_this_week.filter(status='overdue', due_date__lt=today).count()

    context = {
        'report_title': 'รายงานประจำสัปดาห์',
        'report_period': f'ช่วงวันที่ {start_of_week.strftime("%d/%m/%Y")} - {end_of_week.strftime("%d/%m/%Y")}',
        'loans': loans_this_week,
        'total_loans': total_loans_this_week,
        'returned_loans': returned_this_week,
        'approved_loans': approved_this_week,
        'pending_loans': pending_this_week,
        'overdue_loans': overdue_this_week,
        'organization_name': organization.name,
    }
    return render(request, 'borrowing/weekly_report.html', context)


@login_required
def monthly_report(request):
    """
    รายงานประจำเดือน
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงรายงานนี้")
        return redirect('dashboard')

    organization = request.user.organization

    today = timezone.now().date()
    year = today.year
    month = today.month

    first_day_of_month = today.replace(day=1)
    if month == 12:
        last_day_of_month = today.replace(year=year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_day_of_month = today.replace(month=month + 1, day=1) - timedelta(days=1)

    loans_this_month = Loan.objects.filter(
        asset__item__organization=organization,
        borrow_date__date__range=[first_day_of_month, last_day_of_month]
    ).select_related('asset__item', 'borrower').order_by('-borrow_date')

    total_loans_this_month = loans_this_month.count()
    returned_this_month = loans_this_month.filter(status='returned').count()
    approved_this_month = loans_this_month.filter(status='approved').count()
    pending_this_month = loans_this_month.filter(status='pending').count()
    overdue_this_month = loans_this_month.filter(status='overdue', due_date__lt=today).count()

    context = {
        'report_title': 'รายงานประจำเดือน',
        'report_period': f'เดือน {first_day_of_month.strftime("%B %Y")}',
        'loans': loans_this_month,
        'total_loans': total_loans_this_month,
        'returned_loans': returned_this_month,
        'approved_loans': approved_this_month,
        'pending_loans': pending_this_month,
        'overdue_loans': overdue_this_month,
        'organization_name': organization.name,
    }
    return render(request, 'borrowing/monthly_report.html', context)


# ############## VIEWS FOR ADMIN DASHBOARD ##############
@login_required
def add_asset(request):
    """
    เพิ่มอุปกรณ์ใหม่ โดยเลือกจากประเภทสิ่งของที่มีอยู่
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เพิ่มอุปกรณ์")
        return redirect('dashboard')

    if request.method == 'POST':
        form = AssetCreateForm(request.POST, user=request.user)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.status = 'available'
            asset.save()
            messages.success(request, f'อุปกรณ์ "{asset.item.name}" ถูกเพิ่มเรียบร้อยแล้ว')
            return redirect('dashboard')
    else:
        form = AssetCreateForm(user=request.user)

    context = {
        'form': form,
        'organization_name': request.user.organization.name,
    }
    return render(request, 'borrowing/add_asset.html', context)


@login_required
def item_overview(request):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')

    organization = request.user.organization
    items = (
        Item.objects
            .filter(organization=organization)
            .select_related('category')        # << เพิ่ม
            .order_by('category__name', 'name')
    )
    return render(request, 'borrowing/item_overview.html', {
        'items': items,
        'organization_name': organization.name,
    })


@login_required
def pending_loans_view(request):
    """
    รายการคำขอยืมที่รอดำเนินการ
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')

    organization = request.user.organization
    pending_loans = Loan.objects.filter(
        asset__item__organization=organization,
        status='pending'
    ).select_related('asset__item', 'borrower').order_by('-borrow_date')

    context = {
        'pending_loans': pending_loans,
        'organization_name': organization.name,
    }
    return render(request, 'borrowing/pending_loans.html', context)


@login_required
def active_loans_view(request):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')

    organization = request.user.organization
    # แสดงเฉพาะที่อนุมัติแล้ว และอุปกรณ์อยู่สถานะ on_loan (เริ่มยืมจริง)
    active_loans = Loan.objects.filter(
        asset__item__organization=organization,
        status='approved',
        asset__status='on_loan'
    ).select_related('asset__item', 'borrower').order_by('due_date')

    context = {
        'active_loans': active_loans,
        'organization_name': organization.name,
    }
    return render(request, 'borrowing/active_loans.html', context)

@login_required
def loan_history_admin_view(request):
    """
    ประวัติการยืมทั้งหมด (ยกเว้น pending/approved)
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')

    organization = request.user.organization
    loan_history = Loan.objects.filter(
        asset__item__organization=organization
    ).exclude(
        status__in=['pending', 'approved']
    ).select_related('asset__item', 'borrower').order_by('-borrow_date')

    context = {
        'loan_history': loan_history,
        'organization_name': organization.name,
    }
    return render(request, 'borrowing/loan_history_admin.html', context)

@login_required
def add_category(request):
    if not getattr(request.user, 'is_org_admin', False):
        messages.error(request, "คุณไม่มีสิทธิ์เพิ่มหมวดอุปกรณ์")
        return redirect('dashboard')

    if request.method == 'POST':
        form = ItemCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "เพิ่มหมวดอุปกรณ์เรียบร้อยแล้ว")
            return redirect('add_item')  # กลับไปหน้าเพิ่มประเภทสิ่งของ
    else:
        form = ItemCategoryForm()
    return render(request, 'borrowing/add_category.html', {'form': form})







@login_required
def start_loan(request, loan_id):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ดำเนินการนี้")
        return redirect('dashboard')

    loan = get_object_or_404(Loan, id=loan_id)
    if loan.status != 'approved':
        messages.error(request, "ทำได้เฉพาะรายการที่อนุมัติแล้ว")
        return redirect('dashboard')

    today = timezone.now().date()
    if loan.start_date and today < loan.start_date:
        messages.error(request, f'ยังไม่ถึงวันเริ่มใช้ ({loan.start_date:%d/%m/%Y})')
        return redirect('dashboard')

    with transaction.atomic():
        asset = Asset.objects.select_for_update().get(id=loan.asset_id)
        if asset.status != 'available':
            messages.error(request, f'อุปกรณ์ไม่พร้อม (สถานะ: {asset.get_status_display()})')
            return redirect('dashboard')

        asset.status = 'on_loan'
        asset.save(update_fields=['status'])

        loan.pickup_date = timezone.now()
        loan.save(update_fields=['pickup_date'])

    messages.success(request, f'เริ่มยืม "{loan.asset.item.name}" เรียบร้อย')
    return redirect('dashboard')


@login_required
def reject_loan(request, loan_id):
    """
    แอดมินปฏิเสธคำขอยืม
    - ปฏิเสธได้เฉพาะสถานะ pending หรือ approved ที่ 'ยังไม่เริ่มยืมจริง'
    - ถ้าอุปกรณ์เริ่มยืมจริงแล้ว (asset.status == on_loan) จะไม่ให้ปฏิเสธ
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ปฏิเสธคำขอเหล่านี้")
        return redirect('dashboard')

    loan = get_object_or_404(Loan, id=loan_id)

    if loan.status not in ['pending', 'approved']:
        messages.error(request, "คำขอยืมนี้ไม่สามารถปฏิเสธได้")
        return redirect('dashboard')

    with transaction.atomic():
        asset = Asset.objects.select_for_update().get(id=loan.asset_id)

        # ถ้าเริ่มยืมไปแล้ว ห้ามปฏิเสธ
        if asset.status == 'on_loan':
            messages.error(request, "รายการนี้เริ่มยืมแล้ว ไม่สามารถปฏิเสธได้ กรุณาดำเนินการ 'คืนอุปกรณ์' แทน")
            return redirect('dashboard')

        # ปฏิเสธคำขอ
        loan.status = 'rejected'
        loan.save(update_fields=['status'])

        # เผื่อไว้: ให้สถานะอุปกรณ์กลับเป็นพร้อมยืม
        if asset.status != 'available':
            asset.status = 'available'
            asset.save(update_fields=['status'])

    # แจ้งผู้ยืม (ถ้าใช้ Notification)
    try:
        Notification.objects.create(
            user=loan.borrower,
            message=f'คำขอยืม "{loan.asset.item.name}" ของคุณถูกปฏิเสธ'
        )
    except Exception:
        pass

    messages.success(
        request,
        f'ปฏิเสธคำขอยืม "{loan.asset.item.name}" ของผู้ใช้ {loan.borrower.username} เรียบร้อยแล้ว'
    )
    return redirect('dashboard')
