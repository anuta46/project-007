# borrowing/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms import inlineformset_factory 
from django.utils import timezone 
from datetime import timedelta 

from .forms import ItemForm, AssetForm, LoanRequestForm 
from .models import Item, Asset, Loan 
from users.models import Notification, CustomUser 


@login_required
def item_overview(request):
    """
    View สำหรับ Organization Admin เพื่อดูภาพรวมสิ่งของทั้งหมดในองค์กร
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')
    
    # ดึงสิ่งของทั้งหมดขององค์กรของผู้ดูแลระบบ
    items = Item.objects.filter(organization=request.user.organization).order_by('name')
    
    context = {
        'items': items,
        'organization_name': request.user.organization.name 
    }
    return render(request, 'borrowing/item_overview.html', context)


@login_required
def pending_loans_view(request):
    """
    View สำหรับ Organization Admin เพื่อดูคำขอยืมที่รอดำเนินการทั้งหมดในองค์กร
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')
    
    # ดึงคำขอยืมที่รอดำเนินการทั้งหมดขององค์กรของผู้ดูแลระบบ
    pending_loans = Loan.objects.filter(asset__item__organization=request.user.organization, status='pending').order_by('-borrow_date')
    
    context = {
        'pending_loans': pending_loans,
    }
    return render(request, 'borrowing/pending_loans.html', context)


@login_required
def active_loans_view(request):
    """
    View สำหรับ Organization Admin เพื่อดูรายการยืมที่กำลังดำเนินการทั้งหมดในองค์กร
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')
    
    # ดึงรายการยืมที่อนุมัติแล้วและกำลังดำเนินการทั้งหมดขององค์กรของผู้ดูแลระบบ
    active_loans = Loan.objects.filter(asset__item__organization=request.user.organization, status='approved').order_by('due_date')
    
    context = {
        'active_loans': active_loans,
    }
    return render(request, 'borrowing/active_loans.html', context)


@login_required
def loan_history_admin_view(request):
    """
    View สำหรับ Organization Admin เพื่อดูประวัติการยืมทั้งหมดในองค์กร
    (รวมถึงที่คืนแล้ว, ถูกปฏิเสธ, เกินกำหนด)
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')
    
    # ดึงประวัติการยืมทั้งหมด (ยกเว้น 'pending' และ 'approved' ที่มีหน้าเฉพาะ)
    loan_history = Loan.objects.filter(asset__item__organization=request.user.organization).exclude(status__in=['pending', 'approved']).order_by('-borrow_date')
    
    context = {
        'loan_history': loan_history,
    }
    return render(request, 'borrowing/loan_history_admin.html', context)


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
            # ไม่จำเป็นต้องตั้งค่า available_quantity ที่นี่เพราะจะถูกคำนวณจาก Assets
            item.save()

            asset_formset.instance = item
            asset_formset.save()
            
            # อัปเดต total_quantity และ available_quantity ของ Item หลังบันทึก Assets
            item.update_quantities() # เรียกใช้เมธอดใหม่ในโมเดล Item
            
            messages.success(request, f'ประเภทสิ่งของ "{item.name}" และอุปกรณ์ถูกเพิ่มเรียบร้อยแล้ว')
            return redirect('item_overview') 
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

    # AssetFormSet สำหรับแก้ไข Assets ที่มีอยู่
    AssetFormSet = inlineformset_factory(Item, Asset, form=AssetForm, extra=1, can_delete=True)

    if request.method == 'POST':
        item_form = ItemForm(request.POST, request.FILES, instance=item)
        asset_formset = AssetFormSet(request.POST, instance=item, prefix='asset')

        if item_form.is_valid() and asset_formset.is_valid():
            item_form.save() # บันทึกการเปลี่ยนแปลงของ Item
            asset_formset.save() # บันทึกการเปลี่ยนแปลงของ Assets

            # อัปเดต total_quantity และ available_quantity ของ Item หลังบันทึก Assets
            item.update_quantities() # เรียกใช้เมธอดใหม่ในโมเดล Item

            messages.success(request, f'ประเภทสิ่งของ "{item.name}" และอุปกรณ์ถูกแก้ไขเรียบร้อยแล้ว')
            return redirect('item_overview') 
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

    # ตรวจสอบว่ามี Loan ที่อนุมัติแล้วหรือรอดำเนินการผูกกับ Asset ของ Item นี้หรือไม่
    # ถ้ามี Loan ที่ 'pending' หรือ 'approved' อยู่ ไม่ควรให้ลบ Item
    if Loan.objects.filter(asset__item=item, status__in=['pending', 'approved']).exists():
        messages.error(request, f'ไม่สามารถลบประเภทสิ่งของ "{item.name}" ได้ เนื่องจากมีอุปกรณ์ภายใต้ประเภทนี้ที่มีรายการยืมที่ยังไม่เสร็จสิ้น (รอดำเนินการหรืออนุมัติแล้ว)')
        return redirect('item_overview')

    # ตรวจสอบว่ามี Asset ผูกอยู่หรือไม่
    # หากไม่มี Loan แต่ยังมี Asset ก็ควรแจ้งเตือน
    if item.assets.exists():
        messages.error(request, f'ไม่สามารถลบประเภทสิ่งของ "{item.name}" ได้ เนื่องจากยังมีอุปกรณ์ ({item.assets.count()} ชิ้น) ผูกอยู่ กรุณาลบอุปกรณ์แต่ละชิ้นจากหน้าแก้ไขสิ่งของก่อน')
        return redirect('item_overview')
    
    if request.method == 'POST':
        item.delete()
        messages.success(request, f'ประเภทสิ่งของ "{item.name}" ถูกลบเรียบร้อยแล้ว')
        return redirect('item_overview') 
    
    messages.info(request, f'คุณกำลังจะลบประเภทสิ่งของ "{item.name}" หากต้องการยืนยัน โปรดใช้ปุ่มลบจากหน้าภาพรวมสิ่งของ.')
    return redirect('item_overview') 


@login_required
def borrow_item(request, asset_id):
    """
    View สำหรับผู้ใช้ทั่วไปเพื่อส่งคำขอยืมอุปกรณ์แต่ละชิ้น (Asset) พร้อมเหตุผล
    """
    asset = get_object_or_404(Asset, id=asset_id)
    
    if request.method == 'POST':
        form = LoanRequestForm(request.POST) 
        if form.is_valid():
            if asset.status == 'available': # ตรวจสอบสถานะของ Asset ว่าพร้อมให้ยืมหรือไม่
                due_date = timezone.now() + timedelta(days=7)
                
                loan = form.save(commit=False) 
                loan.asset = asset
                loan.borrower = request.user
                loan.status = 'pending' # สถานะเริ่มต้นเป็น 'pending'
                loan.due_date = due_date
                loan.save()

                # *** สำคัญ: ไม่เปลี่ยนสถานะ Asset เป็น 'on_loan' ในขั้นตอนนี้ ***
                # สถานะ Asset จะเปลี่ยนเมื่อ Loan ได้รับการอนุมัติเท่านั้น

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
    else: 
        form = LoanRequestForm()
    
    context = {
        'asset': asset,
        'form': form,
        'MEDIA_URL': 'media/' 
    }
    return render(request, 'borrowing/borrow_item.html', context)


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
        asset.status = 'available' # เปลี่ยนสถานะของ Asset กลับเป็น 'available' เมื่อคืนแล้ว
        asset.save()
        asset.item.update_quantities() # อัปเดตจำนวนของ Item ที่เกี่ยวข้อง
        
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
        # ตรวจสอบสถานะของ Asset อีกครั้งก่อนอนุมัติ
        # เนื่องจากเราไม่ได้เปลี่ยนสถานะ Asset ใน borrow_item แล้ว
        if loan.asset.status == 'available': 
            loan.status = 'approved'
            loan.borrow_date = timezone.now()
            loan.save()

            # เปลี่ยนสถานะของ Asset เป็น 'on_loan' เมื่อคำขอยืมได้รับการอนุมัติ
            loan.asset.status = 'on_loan' 
            loan.asset.save()
            loan.asset.item.update_quantities() # อัปเดตจำนวนของ Item ที่เกี่ยวข้อง

            messages.success(request, f'คำขอยืมสิ่งของ "{loan.asset.item.name}" (SN/ID: {loan.asset.serial_number or loan.asset.device_id or loan.asset.id}) โดย {loan.borrower.username} ได้รับการอนุมัติแล้ว')

            Notification.objects.create(
                user=loan.borrower,
                message=f"คำขอยืมสิ่งของ \"{loan.asset.item.name}\" (SN/ID: {loan.asset.serial_number or loan.asset.device_id or loan.asset.id}) ของคุณได้รับการอนุมัติแล้ว! โปรดมารับภายใน 3 วัน"
            )
        else:
            # ข้อผิดพลาดนี้ควรเกิดขึ้นเฉพาะเมื่อ Asset ถูกยืมไปแล้วจริงๆ
            messages.error(request, f'ไม่สามารถอนุมัติคำขอยืมนี้ได้: อุปกรณ์ "{loan.asset.item.name}" (SN/ID: {loan.asset.serial_number or loan.asset.device_id or loan.asset.id}) ไม่อยู่ในสถานะพร้อมให้ยืม ({loan.asset.get_status_display()})')
            return redirect('pending_loans_view')
    else:
        messages.error(request, 'คำขอยืมนี้ไม่สามารถอนุมัติได้')
        
    return redirect('pending_loans_view')


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
        
        # เมื่อคำขอยืมถูกปฏิเสธ อุปกรณ์ควรกลับไปอยู่ในสถานะ 'available' เสมอ
        # เนื่องจากเราคาดว่า Asset ควรอยู่ในสถานะ 'available' ตลอดเวลาที่มี Loan เป็น 'pending'
        # ดังนั้นการตั้งค่าเป็น 'available' จึงเป็นการยืนยันสถานะที่ถูกต้อง
        loan.asset.status = 'available' 
        loan.asset.save()
        loan.asset.item.update_quantities() # อัปเดตจำนวนของ Item ที่เกี่ยวข้อง

        messages.success(request, f'คำขอยืมสิ่งของ "{loan.asset.item.name}" (SN/ID: {loan.asset.serial_number or loan.asset.device_id or loan.asset.id}) โดย {loan.borrower.username} ได้รับการปฏิเสธแล้ว')

        Notification.objects.create(
            user=loan.borrower,
            message=f"คำขอยืมสิ่งของ \"{loan.asset.item.name}\" (SN/ID: {loan.asset.serial_number or loan.asset.device_id or loan.asset.id}) ของคุณถูกปฏิเสธแล้ว"
        )
    else:
        messages.error(request, 'คำขอยืมนี้ไม่สามารถปฏิเสธได้')
        
    return redirect('pending_loans_view')
