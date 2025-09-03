from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.forms import inlineformset_factory 
from django.db.models import Q # Import Q object for OR queries
from django.db import transaction # Import transaction for database atomicity

from .forms import ItemForm, AssetForm, LoanRequestForm 
from .models import Item, Asset, Loan 
from users.models import Notification, CustomUser 


@login_required
def add_item(request):
    """
    View for Organization Admin to add a new item type
    and can also add individual assets linked to that item type.
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เพิ่มสิ่งของ")
        return redirect('dashboard')

    AssetFormSet = inlineformset_factory(Item, Asset, form=AssetForm, extra=1, can_delete=True)

    if request.method == 'POST':
        item_form = ItemForm(request.POST, request.FILES)
        asset_formset = AssetFormSet(request.POST, prefix='asset')

        if item_form.is_valid() and asset_formset.is_valid():
            with transaction.atomic():
                item = item_form.save(commit=False)
                item.organization = request.user.organization
                item.save()

                asset_formset.instance = item
                asset_formset.save()

            messages.success(request, f'ประเภทสิ่งของ "{item.name}" และอุปกรณ์ถูกเพิ่มเรียบร้อยแล้ว')
            return redirect('dashboard')
    else:
        item_form = ItemForm()
        asset_formset = AssetFormSet(prefix='asset')
    
    context = {
        'item_form': item_form,
        'asset_formset': asset_formset,
    }
    return render(request, 'borrowing/add_item.html', context)


@login_required
def edit_item(request, item_id):
    """
    View for Organization Admin to edit an item type
    and manage (add/edit/delete) individual assets linked to that item type.
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขสิ่งของ")
        return redirect('dashboard')
    
    item = get_object_or_404(Item, id=item_id, organization=request.user.organization)

    AssetFormSet = inlineformset_factory(Item, Asset, form=AssetForm, extra=1, can_delete=True)

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
def delete_item(request, item_id):
    """
    View for Organization Admin to delete an item type.
    Allowed only if no Assets or Loans are linked to that Item.
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ลบสิ่งของ")
        return redirect('dashboard')
    
    item = get_object_or_404(Item, id=item_id, organization=request.user.organization)

    if item.assets.exists():
        messages.error(request, f'ไม่สามารถลบประเภทสิ่งของ "{item.name}" ได้ เนื่องจากมีอุปกรณ์ ({item.assets.count()} ชิ้น) ผูกอยู่ กรุณาลบอุปกรณ์แต่ละชิ้นก่อน')
        return redirect('dashboard')

    if request.method == 'POST':
        item.delete()
        messages.success(request, f'ประเภทสิ่งของ "{item.name}" ถูกลบเรียบร้อยแล้ว')
        return redirect('dashboard')
    
    messages.info(request, f'คุณกำลังจะลบประเภทสิ่งของ "{item.name}" หากต้องการยืนยัน โปรดใช้ปุ่มลบจากหน้าแดชบอร์ด.')
    return redirect('dashboard') 


@login_required
def borrow_item(request, asset_id):
    """
    View for general users to submit a loan request for a specific Asset.
    """
    asset = get_object_or_404(Asset, id=asset_id)
    
    if request.method == 'POST':
        form = LoanRequestForm(request.POST)
        if form.is_valid():
            # Use a database transaction to prevent race conditions
            with transaction.atomic():
                # Re-fetch the asset inside the transaction to ensure its status is up-to-date
                asset_recheck = Asset.objects.select_for_update().get(id=asset_id)
                
                if asset_recheck.status == 'available':
                    # Extract data from the validated form
                    borrow_date = form.cleaned_data['borrow_date']
                    due_date = form.cleaned_data['due_date']
                    reason = form.cleaned_data['reason']

                    # Create the new loan request
                    loan = Loan.objects.create(
                        asset=asset_recheck,
                        borrower=request.user,
                        reason=reason,
                        borrow_date=borrow_date,
                        due_date=due_date,
                        status='pending'
                    )

                    # Update asset status
                    asset_recheck.status = 'on_loan' 
                    asset_recheck.save()

                    messages.success(request, f'คุณได้ส่งคำขอยืมสิ่งของ "{asset_recheck.item.name}" (SN/ID: {asset_recheck.serial_number or asset_recheck.device_id or asset_recheck.id}) เรียบร้อยแล้ว โปรดรอการอนุมัติจากผู้ดูแล')

                    # Create notifications for all organization admins
                    org_admins = CustomUser.objects.filter(
                        organization=asset_recheck.item.organization, 
                        is_org_admin=True, 
                        is_active=True
                    )
                    for admin in org_admins:
                        Notification.objects.create(
                            user=admin,
                            message=f"ผู้ใช้ {request.user.username} ได้ส่งคำขอยืมสิ่งของ \"{asset_recheck.item.name}\" (SN/ID: {asset_recheck.serial_number or asset_recheck.device_id or asset_recheck.id}) ใหม่"
                        )
                else:
                    messages.error(request, f'"{asset_recheck.item.name}" (SN/ID: {asset_recheck.serial_number or asset_recheck.device_id or asset_recheck.id}) ไม่พร้อมให้ยืมในขณะนี้ (สถานะ: {asset_recheck.get_status_display()})')
            
            return redirect('user_dashboard')
        else:
            # Re-render the form with validation errors if the form is not valid
            context = {
                'asset': asset,
                'form': form,
                'MEDIA_URL': 'media/'
            }
            return render(request, 'borrowing/borrow_item.html', context)
    else: # GET request, display the form
        form = LoanRequestForm()
    
    context = {
        'asset': asset,
        'form': form,
        'MEDIA_URL': 'media/' # Assuming MEDIA_URL is '/media/'
    }
    return render(request, 'borrowing/borrow_item.html', context)


@login_required
def return_item(request, loan_id):
    """
    View for general users to return a borrowed item.
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
    """
    View for Organization Admin to approve a loan request.
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์อนุมัติคำขอเหล่านี้")
        return redirect('dashboard')

    loan = get_object_or_404(Loan, id=loan_id)
    
    if loan.status == 'pending':
        if loan.asset.status == 'available': 
            loan.status = 'approved'
            loan.borrow_date = timezone.now()
            loan.save()

            loan.asset.status = 'on_loan' 
            loan.asset.save()

            messages.success(request, f'คำขอยืมสิ่งของ "{loan.asset.item.name}" (SN/ID: {loan.asset.serial_number or loan.asset.device_id or loan.asset.id}) โดย {loan.borrower.username} ได้รับการอนุมัติแล้ว')

            Notification.objects.create(
                user=loan.borrower,
                message=f"คำขอยืมสิ่งของ \"{loan.asset.item.name}\" (SN/ID: {loan.asset.serial_number or loan.asset.device_id or loan.asset.id}) ของคุณได้รับการอนุมัติแล้ว! โปรดมารับภายใน 3 วัน"
            )
        else:
            messages.error(request, f'ไม่สามารถอนุมัติคำขอยืมนี้ได้: อุปกรณ์ "{loan.asset.item.name}" (SN/ID: {loan.asset.serial_number or loan.asset.device_id or loan.asset.id}) ไม่อยู่ในสถานะพร้อมให้ยืม ({loan.asset.get_status_display()})')
            return redirect('dashboard')
    else:
        messages.error(request, 'คำขอยืมนี้ไม่สามารถอนุมัติได้')
        
    return redirect('dashboard')


@login_required
def reject_loan(request, loan_id):
    """
    View for Organization Admin to reject a loan request.
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ปฏิเสธคำขอเหล่านี้")
        return redirect('dashboard')

    loan = get_object_or_404(Loan, id=loan_id)
    
    if loan.status == 'pending':
        loan.status = 'rejected'
        loan.save()
        
        if loan.asset.status == 'on_loan': 
             loan.asset.status = 'available' 
             loan.asset.save()
        elif loan.asset.status == 'available': 
             pass 

        messages.success(request, f'คำขอยืมสิ่งของ "{loan.asset.item.name}" (SN/ID: {loan.asset.serial_number or loan.asset.device_id or loan.asset.id}) โดย {loan.borrower.username} ได้รับการปฏิเสธแล้ว')

        Notification.objects.create(
            user=loan.borrower,
            message=f"คำขอยืมสิ่งของ \"{loan.asset.item.name}\" (SN/ID: {loan.asset.serial_number or loan.asset.device_id or loan.asset.id}) ของคุณถูกปฏิเสธแล้ว"
        )
    else:
        messages.error(request, 'คำขอยืมนี้ไม่สามารถปฏิเสธได้')
        
    return redirect('dashboard')


# ############## VIEWS FOR REPORTS ##############
@login_required
def weekly_report(request):
    """
    View for Organization Admin to view a weekly loan report.
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
    View for Organization Admin to view a monthly loan report.
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
def item_overview(request):
    """
    View for Organization Admin to get an overview of item types and number of assets.
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')
    
    organization = request.user.organization
    items = Item.objects.filter(organization=organization).order_by('name')

    context = {
        'items': items,
        'organization_name': organization.name,
    }
    return render(request, 'borrowing/item_overview.html', context)


@login_required
def pending_loans_view(request):
    """
    View for Organization Admin to view pending loan requests.
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
    """
    View for Organization Admin to view active (approved) loans.
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')
    
    organization = request.user.organization
    active_loans = Loan.objects.filter(
        asset__item__organization=organization, 
        status='approved'
    ).select_related('asset__item', 'borrower').order_by('due_date')

    context = {
        'active_loans': active_loans,
        'organization_name': organization.name,
    }
    return render(request, 'borrowing/active_loans.html', context)


@login_required
def loan_history_admin_view(request):
    """
    View for Organization Admin to view all loan history.
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
