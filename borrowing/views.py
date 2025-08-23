# borrowing/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.forms import inlineformset_factory 

from .forms import ItemForm, AssetForm, LoanRequestForm # นำเข้า LoanRequestForm ด้วย
from .models import Item, Asset, Loan 
from users.models import Notification, CustomUser 


@login_required
def add_item(request):
    """
    View สำหรับ Organization Admin เพื่อเพิ่มประเภทสิ่งของใหม่
    และสามารถเพิ่มอุปกรณ์แต่ละชิ้น (Assets) ที่ผูกกับประเภทนั้นๆ ได้พร้อมกัน
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เพิ่มสิ่งของ")
        return redirect('dashboard')

    AssetFormSet = inlineformset_factory(Item, Asset, form=AssetForm, extra=1, can_delete=True)

    if request.method == 'POST':
        item_form = ItemForm(request.POST, request.FILES)
        asset_formset = AssetFormSet(request.POST, prefix='asset')

        if item_form.is_valid() and asset_formset.is_valid():
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
    View สำหรับ Organization Admin เพื่อแก้ไขประเภทสิ่งของ
    และจัดการ (เพิ่ม/แก้ไข/ลบ) อุปกรณ์แต่ละชิ้น (Assets) ที่ผูกกับประเภทนั้นๆ
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
    View สำหรับ Organization Admin เพื่อลบประเภทสิ่งของ (Item)
    จะอนุญาตให้ลบได้เฉพาะเมื่อไม่มี Asset หรือ Loan ที่ผูกอยู่กับ Item นั้นๆ
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
    View สำหรับผู้ใช้ทั่วไปเพื่อส่งคำขอยืมอุปกรณ์แต่ละชิ้น (Asset) พร้อมเหตุผล
    """
    asset = get_object_or_404(Asset, id=asset_id)
    
    if request.method == 'POST':
        form = LoanRequestForm(request.POST) # ใช้ LoanRequestForm
        if form.is_valid():
            if asset.status == 'available':
                due_date = timezone.now() + timedelta(days=7)
                
                loan = form.save(commit=False) # บันทึกฟอร์มแต่ยังไม่บันทึกเข้า DB
                loan.asset = asset
                loan.borrower = request.user
                loan.status = 'pending'
                loan.due_date = due_date
                loan.save()

                asset.status = 'on_loan' # เปลี่ยนสถานะของ Asset เป็น 'on_loan'
                asset.save()

                messages.success(request, f'คุณได้ส่งคำขอยืมสิ่งของ "{asset.item.name}" (SN/ID: {asset.serial_number or asset.device_id or asset.id}) เรียบร้อยแล้ว โปรดรอการอนุมัติจากผู้ดูแล')

                org_admins = CustomUser.objects.filter(
                    organization=asset.item.organization, 
                    is_org_admin=True, 
                    is_active=True
                )
                for admin in org_admins:
                    Notification.objects.create(
                        user=admin,
                        message=f"ผู้ใช้ {request.user.username} ได้ส่งคำขอยืมสิ่งของ \"{asset.item.name}\" (SN/ID: {asset.serial_number or asset.device_id or asset.id}) ใหม่"
                    )
            else:
                messages.error(request, f'"{asset.item.name}" (SN/ID: {asset.serial_number or asset.device_id or asset.id}) ไม่พร้อมให้ยืมในขณะนี้ (สถานะ: {asset.get_status_display()})')
            return redirect('user_dashboard')
    else: # GET request, แสดงฟอร์ม
        form = LoanRequestForm()
    
    context = {
        'asset': asset,
        'form': form,
        'MEDIA_URL': 'media/' # Assuming MEDIA_URL is '/media/'
    }
    return render(request, 'borrowing/borrow_item.html', context) # ต้องสร้าง template นี้


@login_required
def return_item(request, loan_id):
    """
    View สำหรับผู้ใช้ทั่วไปเพื่อคืนอุปกรณ์ที่ยืม
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
    View สำหรับ Organization Admin เพื่ออนุมัติคำขอยืม
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
    View สำหรับ Organization Admin เพื่อปฏิเสธคำขอยืม
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
