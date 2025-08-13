# borrowing/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ItemForm
from .models import Item, Loan
from django.utils import timezone # นำเข้า timezone
from datetime import timedelta # นำเข้า timedelta


@login_required
def add_item(request):
    # ตรวจสอบว่าผู้ใช้มีสิทธิ์เป็น Organization Admin หรือไม่
    # หากไม่ใช่แอดมินองค์กร จะถูกเปลี่ยนเส้นทางกลับไปที่หน้า dashboard
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์เพิ่มสิ่งของ")
        return redirect('dashboard')

    if request.method == 'POST':
        # ถ้าเป็นการส่งข้อมูลแบบ POST ให้สร้างฟอร์มด้วยข้อมูลที่ส่งมา
        form = ItemForm(request.POST)
        if form.is_valid():
            # บันทึกข้อมูลฟอร์มลงในโมเดล Item แต่ยังไม่บันทึกลงฐานข้อมูลทันที
            item = form.save(commit=False)
            # กำหนดองค์กรของสิ่งของเป็นองค์กรของผู้ใช้ที่ล็อกอินอยู่
            item.organization = request.user.organization
            # กำหนดจำนวนสิ่งของที่พร้อมให้ยืมให้เท่ากับจำนวนทั้งหมดที่เพิ่มเข้ามา
            item.available_quantity = item.quantity
            # บันทึกสิ่งของลงในฐานข้อมูล
            item.save()
            messages.success(request, f'สิ่งของ "{item.name}" ถูกเพิ่มเรียบร้อยแล้ว')
            return redirect('dashboard') # กลับไปที่หน้า dashboard หลังจากเพิ่มสิ่งของสำเร็จ
    else:
        # ถ้าเป็นการร้องขอแบบ GET (เข้าสู่หน้าครั้งแรก) ให้สร้างฟอร์มเปล่า
        form = ItemForm()
    
    # แสดงหน้าฟอร์มเพิ่มสิ่งของ
    return render(request, 'borrowing/add_item.html', {'form': form})

@login_required
def edit_item(request, item_id):
    """
    View สำหรับ Organization Admin เพื่อแก้ไขข้อมูลสิ่งของ
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขสิ่งของ")
        return redirect('dashboard')
    
    # ดึงสิ่งของจาก ID และตรวจสอบว่าเป็นขององค์กรเดียวกัน
    item = get_object_or_404(Item, id=item_id, organization=request.user.organization)

    if request.method == 'POST':
        form = ItemForm(request.POST, instance=item) # สร้างฟอร์มพร้อมข้อมูลเดิมของสิ่งของ
        if form.is_valid():
            new_quantity = form.cleaned_data.get('quantity')
            old_available_quantity = item.available_quantity
            old_quantity = item.quantity

            # ตรวจสอบว่าจำนวนที่ถูกยืมไปแล้วไม่เกินจำนวนใหม่
            borrowed_count = old_quantity - old_available_quantity
            if new_quantity < borrowed_count:
                messages.error(request, f"ไม่สามารถตั้งจำนวนทั้งหมดน้อยกว่าจำนวนที่ถูกยืมไปแล้ว ({borrowed_count})")
                return render(request, 'borrowing/edit_item.html', {'form': form, 'item': item})
            
            # ปรับ available_quantity ตามการเปลี่ยนแปลงของ quantity
            item.available_quantity = new_quantity - borrowed_count
            form.save()
            messages.success(request, f'สิ่งของ "{item.name}" ถูกแก้ไขเรียบร้อยแล้ว')
            return redirect('dashboard')
    else:
        form = ItemForm(instance=item) # แสดงฟอร์มพร้อมข้อมูลปัจจุบันของสิ่งของ
    
    return render(request, 'borrowing/edit_item.html', {'form': form, 'item': item})


@login_required
def delete_item(request, item_id):
    """
    View สำหรับ Organization Admin เพื่อลบสิ่งของ
    """
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ลบสิ่งของ")
        return redirect('dashboard')
    
    # ดึงสิ่งของจาก ID และตรวจสอบว่าเป็นขององค์กรเดียวกัน
    item = get_object_or_404(Item, id=item_id, organization=request.user.organization)

    # ตรวจสอบว่าสิ่งของมีการยืมที่ยังไม่คืนหรือไม่
    active_loans_for_item = Loan.objects.filter(item=item, status='approved').exists()
    pending_loans_for_item = Loan.objects.filter(item=item, status='pending').exists()

    if active_loans_for_item or pending_loans_for_item:
        messages.error(request, f'ไม่สามารถลบสิ่งของ "{item.name}" ได้ เนื่องจากมีการยืมที่ยังไม่คืนหรือรอดำเนินการ')
        return redirect('dashboard')

    if request.method == 'POST':
        item.delete()
        messages.success(request, f'สิ่งของ "{item.name}" ถูกลบเรียบร้อยแล้ว')
        return redirect('dashboard')
    
    # หากเป็น GET request จะให้แสดงหน้ายืนยันการลบ (ถ้าคุณมี template สำหรับยืนยัน)
    # สำหรับตอนนี้ เราจะ redirect กลับไปพร้อมข้อความแจ้งเตือนให้ผู้ใช้ใช้ปุ่ม POST เท่านั้น
    messages.info(request, f'คุณกำลังจะลบสิ่งของ "{item.name}" หากต้องการยืนยัน โปรดใช้ปุ่มลบจากหน้าแดชบอร์ด.')
    return redirect('dashboard')


@login_required
def borrow_item(request, item_id):
    # 1. ค้นหาสิ่งของจาก ID หรือแสดงข้อผิดพลาด 404 หากไม่พบ
    item = get_object_or_404(Item, id=item_id)
    
    # 2. ตรวจสอบว่าสิ่งของยังมีให้ยืมอยู่หรือไม่
    if item.available_quantity > 0:
        # คำนวณ due_date: 7 วันนับจากปัจจุบัน
        due_date = timezone.now() + timedelta(days=7) # เพิ่มบรรทัดนี้
        
        # 3. ถ้ามี ให้สร้างรายการยืมใหม่ในฐานข้อมูล
        Loan.objects.create(
            item=item, # สิ่งของที่ถูกยืม
            borrower=request.user, # ผู้ที่ทำการยืม (ผู้ใช้ปัจจุบัน)
            status='pending',  # ตั้งสถานะเริ่มต้นเป็น 'pending' (รอการอนุมัติ)
            due_date=due_date # ส่งค่า due_date เข้าไปด้วย
        )
        # 4. ลดจำนวนสิ่งของที่พร้อมให้ยืมลง 1
        item.available_quantity -= 1
        item.save()
        # 5. แสดงข้อความสำเร็จแก่ผู้ใช้
        messages.success(request, f'คุณได้ส่งคำขอยืมสิ่งของ "{item.name}" เรียบร้อยแล้ว โปรดรอการอนุมัติจากผู้ดูแล')
    else:
        # 6. ถ้าสิ่งของไม่พร้อมให้ยืม ให้แสดงข้อความผิดพลาด
        messages.error(request, f'"{item.name}" ไม่พร้อมให้ยืมในขณะนี้')

    # 7. เปลี่ยนเส้นทางผู้ใช้กลับไปที่หน้า user_dashboard
    return redirect('user_dashboard')

@login_required
def return_item(request, loan_id):
    # 1. ค้นหาบันทึกการยืมจาก ID และตรวจสอบว่าเป็นของผู้ใช้ปัจจุบัน หรือแสดงข้อผิดพลาด 404 หากไม่พบ
    loan = get_object_or_404(Loan, id=loan_id, borrower=request.user)

    # 2. ตรวจสอบสถานะของการยืมว่าได้รับการอนุมัติหรือไม่ (จึงจะสามารถคืนได้)
    if loan.status == 'approved':
        # 3. เปลี่ยนสถานะของบันทึกการยืมเป็น 'returned'
        loan.status = 'returned'
        loan.save()

        # 4. เพิ่มจำนวนสิ่งของที่พร้อมให้ยืมคืน
        item = loan.item
        item.available_quantity += 1
        item.save()

        # 5. แสดงข้อความสำเร็จแก่ผู้ใช้
        messages.success(request, f'คุณได้คืนสิ่งของ "{item.name}" เรียบร้อยแล้ว')
    else:
        # 6. ถ้าสถานะไม่ถูกต้อง ให้แสดงข้อความผิดพลาด
        messages.error(request, 'สิ่งของนี้ไม่สามารถคืนได้ในขณะนี้')

    # 7. เปลี่ยนเส้นทางผู้ใช้กลับไปที่หน้า user_dashboard
    return redirect('my_borrowed_items_history') # เปลี่ยนเส้นทางไปหน้าประวัติการยืม


@login_required
def approve_loan(request, loan_id):
    # ตรวจสอบว่าผู้ใช้งานเป็น Organization Admin
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์อนุมัติคำขอเหล่านี้")
        return redirect('dashboard') # หรือหน้าที่เหมาะสม

    loan = get_object_or_404(Loan, id=loan_id)
    
    # ตรวจสอบว่าคำขออยู่ในสถานะ 'pending' เท่านั้น
    if loan.status == 'pending':
        loan.status = 'approved'
        loan.borrow_date = timezone.now() # บันทึกวันที่อนุมัติเป็นวันที่ยืมจริง
        loan.save()
        messages.success(request, f'คำขอยืมสิ่งของ "{loan.item.name}" โดย {loan.borrower.username} ได้รับการอนุมัติแล้ว')
    else:
        messages.error(request, 'คำขอยืมนี้ไม่สามารถอนุมัติได้')
        
    return redirect('dashboard') # กลับไปที่หน้า dashboard ของแอดมิน


@login_required
def reject_loan(request, loan_id):
    # ตรวจสอบว่าผู้ใช้งานเป็น Organization Admin
    if not request.user.is_org_admin:
        messages.error(request, "คุณไม่มีสิทธิ์ปฏิเสธคำขอเหล่านี้")
        return redirect('dashboard') # หรือหน้าที่เหมาะสม

    loan = get_object_or_404(Loan, id=loan_id)
    
    # ตรวจสอบว่าคำขออยู่ในสถานะ 'pending' เท่านั้น
    if loan.status == 'pending':
        loan.status = 'rejected'
        loan.save()
        
        # เพิ่มจำนวนสิ่งของที่พร้อมให้ยืมคืนหากถูกปฏิเสธ
        item = loan.item
        item.available_quantity += 1
        item.save()
        messages.success(request, f'คำขอยืมสิ่งของ "{loan.item.name}" โดย {loan.borrower.username} ได้รับการปฏิเสธแล้ว')
    else:
        messages.error(request, 'คำขอยืมนี้ไม่สามารถปฏิเสธได้')
        
    return redirect('dashboard') # กลับไปที่หน้า dashboard ของแอดมิน
