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
        messages.error(request, "You do not have permission to add items.")
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
            messages.success(request, f'Item "{item.name}" added successfully.')
            return redirect('dashboard') # กลับไปที่หน้า dashboard หลังจากเพิ่มสิ่งของสำเร็จ
    else:
        # ถ้าเป็นการร้องขอแบบ GET (เข้าสู่หน้าครั้งแรก) ให้สร้างฟอร์มเปล่า
        form = ItemForm()
    
    # แสดงหน้าฟอร์มเพิ่มสิ่งของ
    return render(request, 'borrowing/add_item.html', {'form': form})

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
        messages.success(request, f'Successfully requested to borrow "{item.name}". Please wait for admin approval.')
    else:
        # 6. ถ้าสิ่งของไม่พร้อมให้ยืม ให้แสดงข้อความผิดพลาด
        messages.error(request, f'"{item.name}" is not available for borrowing.')

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
        messages.success(request, f'Successfully returned "{item.name}".')
    else:
        # 6. ถ้าสถานะไม่ถูกต้อง ให้แสดงข้อความผิดพลาด
        messages.error(request, 'This item cannot be returned at this time.')

    # 7. เปลี่ยนเส้นทางผู้ใช้กลับไปที่หน้า user_dashboard
    return redirect('user_dashboard')


@login_required
def approve_loan(request, loan_id):
    # ตรวจสอบว่าผู้ใช้งานเป็น Organization Admin
    if not request.user.is_org_admin:
        messages.error(request, "You do not have permission to approve loans.")
        return redirect('dashboard') # หรือหน้าที่เหมาะสม

    loan = get_object_or_404(Loan, id=loan_id)
    
    # ตรวจสอบว่าคำขออยู่ในสถานะ 'pending' เท่านั้น
    if loan.status == 'pending':
        loan.status = 'approved'
        loan.borrow_date = timezone.now() # บันทึกวันที่อนุมัติเป็นวันที่ยืมจริง
        loan.save()
        messages.success(request, f'Loan for "{loan.item.name}" by {loan.borrower.username} has been approved.')
    else:
        messages.error(request, 'This loan request cannot be approved.')
        
    return redirect('dashboard') # กลับไปที่หน้า dashboard ของแอดมิน


@login_required
def reject_loan(request, loan_id):
    # ตรวจสอบว่าผู้ใช้งานเป็น Organization Admin
    if not request.user.is_org_admin:
        messages.error(request, "You do not have permission to reject loans.")
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
        messages.success(request, f'Loan for "{loan.item.name}" by {loan.borrower.username} has been rejected.')
    else:
        messages.error(request, 'This loan request cannot be rejected.')
        
    return redirect('dashboard') # กลับไปที่หน้า dashboard ของแอดมิน
