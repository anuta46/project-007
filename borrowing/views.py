# borrowing/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ItemForm
from .models import Item, Loan
from django.utils import timezone 
from datetime import timedelta 

from users.models import Notification, CustomUser # นำเข้า Notification และ CustomUser


@login_required
def add_item(request):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เพิ่มสิ่งของ")
        return redirect('dashboard')

    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = request.user.organization
            item.available_quantity = item.quantity
            item.save()
            messages.success(request, f'สิ่งของ "{item.name}" ถูกเพิ่มเรียบร้อยแล้ว')
            return redirect('dashboard')
    else:
        form = ItemForm()
    
    return render(request, 'borrowing/add_item.html', {'form': form})

@login_required
def edit_item(request, item_id):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขสิ่งของ")
        return redirect('dashboard')
    
    item = get_object_or_404(Item, id=item_id, organization=request.user.organization)

    if request.method == 'POST':
        form = ItemForm(request.POST, instance=item) 
        if form.is_valid():
            new_quantity = form.cleaned_data.get('quantity')
            old_available_quantity = item.available_quantity
            old_quantity = item.quantity

            borrowed_count = old_quantity - old_available_quantity
            if new_quantity < borrowed_count:
                messages.error(request, f"ไม่สามารถตั้งจำนวนทั้งหมดน้อยกว่าจำนวนที่ถูกยืมไปแล้ว ({borrowed_count})")
                return render(request, 'borrowing/edit_item.html', {'form': form, 'item': item})
            
            item.available_quantity = new_quantity - borrowed_count
            form.save()
            messages.success(request, f'สิ่งของ "{item.name}" ถูกแก้ไขเรียบร้อยแล้ว')
            return redirect('dashboard')
    else:
        form = ItemForm(instance=item) 
    
    return render(request, 'borrowing/edit_item.html', {'form': form, 'item': item})


@login_required
def delete_item(request, item_id):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ลบสิ่งของ")
        return redirect('dashboard')
    
    item = get_object_or_404(Item, id=item_id, organization=request.user.organization)

    active_loans_for_item = Loan.objects.filter(item=item, status='approved').exists()
    pending_loans_for_item = Loan.objects.filter(item=item, status='pending').exists()

    if active_loans_for_item or pending_loans_for_item:
        messages.error(request, f'ไม่สามารถลบสิ่งของ "{item.name}" ได้ เนื่องจากมีการยืมที่ยังไม่คืนหรือรอดำเนินการ')
        return redirect('dashboard')

    if request.method == 'POST':
        item.delete()
        messages.success(request, f'สิ่งของ "{item.name}" ถูกลบเรียบร้อยแล้ว')
        return redirect('dashboard')
    
    messages.info(request, f'คุณกำลังจะลบสิ่งของ "{item.name}" หากต้องการยืนยัน โปรดใช้ปุ่มลบจากหน้าแดชบอร์ด.')
    return redirect('dashboard')


@login_required
def borrow_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    
    if item.available_quantity > 0:
        due_date = timezone.now() + timedelta(days=7)
        
        Loan.objects.create(
            item=item,
            borrower=request.user,
            status='pending',
            due_date=due_date
        )
        item.available_quantity -= 1
        item.save()
        messages.success(request, f'คุณได้ส่งคำขอยืมสิ่งของ "{item.name}" เรียบร้อยแล้ว โปรดรอการอนุมัติจากผู้ดูแล')

        # เพิ่ม: สร้าง Notification สำหรับ Organization Admin เมื่อมีการขอยืมใหม่
        # ค้นหา Organization Admin ทั้งหมดในองค์กรเดียวกันกับสิ่งของ
        org_admins = CustomUser.objects.filter(
            organization=item.organization, 
            is_org_admin=True, 
            is_active=True
        )
        for admin in org_admins:
            Notification.objects.create(
                user=admin,
                message=f"ผู้ใช้ {request.user.username} ได้ส่งคำขอยืมสิ่งของ \"{item.name}\" ใหม่"
            )

    else:
        messages.error(request, f'"{item.name}" ไม่พร้อมให้ยืมในขณะนี้')

    return redirect('user_dashboard')

@login_required
def return_item(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id, borrower=request.user)

    if loan.status == 'approved':
        loan.status = 'returned'
        loan.save()

        item = loan.item
        item.available_quantity += 1
        item.save()

        messages.success(request, f'คุณได้คืนสิ่งของ "{item.name}" เรียบร้อยแล้ว')
    else:
        messages.error(request, 'สิ่งของนี้ไม่สามารถคืนได้ในขณะนี้')

    return redirect('my_borrowed_items_history')


@login_required
def approve_loan(request, loan_id):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์อนุมัติคำขอเหล่านี้")
        return redirect('dashboard')

    loan = get_object_or_404(Loan, id=loan_id)
    
    if loan.status == 'pending':
        loan.status = 'approved'
        loan.borrow_date = timezone.now()
        loan.save()
        messages.success(request, f'คำขอยืมสิ่งของ "{loan.item.name}" โดย {loan.borrower.username} ได้รับการอนุมัติแล้ว')

        # เพิ่ม: สร้าง Notification สำหรับผู้ยืมเมื่อคำขอยืมได้รับการอนุมัติ
        Notification.objects.create(
            user=loan.borrower,
            message=f"คำขอยืมสิ่งของ \"{loan.item.name}\" ของคุณได้รับการอนุมัติแล้ว! โปรดมารับภายใน 3 วัน" # คุณอาจปรับข้อความนี้ได้
        )
    else:
        messages.error(request, 'คำขอยืมนี้ไม่สามารถอนุมัติได้')
        
    return redirect('dashboard')


@login_required
def reject_loan(request, loan_id):
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ปฏิเสธคำขอเหล่านี้")
        return redirect('dashboard')

    loan = get_object_or_404(Loan, id=loan_id)
    
    if loan.status == 'pending':
        loan.status = 'rejected'
        loan.save()
        
        item = loan.item
        item.available_quantity += 1
        item.save()
        messages.success(request, f'คำขอยืมสิ่งของ "{loan.item.name}" โดย {loan.borrower.username} ได้รับการปฏิเสธแล้ว')

        # เพิ่ม: สร้าง Notification สำหรับผู้ยืมเมื่อคำขอยืมถูกปฏิเสธ
        Notification.objects.create(
            user=loan.borrower,
            message=f"คำขอยืมสิ่งของ \"{loan.item.name}\" ของคุณถูกปฏิเสธแล้ว"
        )
    else:
        messages.error(request, 'คำขอยืมนี้ไม่สามารถปฏิเสธได้')
        
    return redirect('dashboard')
