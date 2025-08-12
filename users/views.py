# users/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login # อาจไม่จำเป็นต้องใช้ authenticate, login ถ้าใช้ Django's LoginView
from django.contrib.auth.forms import AuthenticationForm # อาจไม่จำเป็นต้องใช้ถ้าใช้ Django's LoginView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction # สำคัญ: สำหรับการทำ Transaction เพื่อความปลอดภัยของข้อมูล
from django.utils import timezone # สำหรับ due_date
from datetime import timedelta # สำหรับ due_date

# นำเข้าโมเดลจากแอปพลิเคชันที่ถูกต้อง
from .models import CustomUser, Organization 
from borrowing.models import Item, Loan # นำเข้าโมเดลจาก borrowing
from .forms import OrganizationRegistrationForm, UserRegistrationForm # นำเข้าฟอร์มที่คุณสร้าง

# ฟังก์ชัน login_view ถูกแทนที่ด้วย Django's LoginView ใน project007/urls.py แล้ว
# จึงไม่จำเป็นต้องมีใน views.py นี้
# def login_view(request):
#     if request.method == 'POST':
#         form = AuthenticationForm(request, data=request.POST)
#         if form.is_valid():
#             username = form.cleaned_data.get('username')
#             password = form.cleaned_data.get('password')
#             user = authenticate(username=username, password=password)
#             if user is not None:
#                 login(request, user)
#                 return redirect('dashboard')
#     else:
#         form = AuthenticationForm()
#     return render(request, 'users/login.html', {'form': form})

@login_required
def dashboard(request):
    """
    หน้าแดชบอร์ดสำหรับผู้ใช้งาน แบ่งตามบทบาท (Platform Admin, Org Admin, End User)
    """
    user = request.user
    
    # ถ้าเป็น Platform Admin ให้เปลี่ยนเส้นทางไปที่หน้า Django Admin
    if user.is_platform_admin:
        return redirect('/admin/')
    
    # ถ้าเป็น Organization Admin
    if user.is_org_admin:
        # ตรวจสอบว่าผู้ใช้มีองค์กรผูกอยู่หรือไม่
        if not user.organization:
            messages.error(request, "บัญชีผู้ดูแลองค์กรของคุณยังไม่ได้ถูกผูกกับองค์กร กรุณาติดต่อผู้ดูแลระบบ.")
            # หรือจะ redirect ไปหน้าที่แจ้งให้ผู้ใช้ติดต่อ admin ก็ได้
            return redirect('login') # ให้กลับไปหน้า login ชั่วคราว

        organization = user.organization
        # ดึงข้อมูลสิ่งของทั้งหมดที่อยู่ในองค์กรนี้
        items = Item.objects.filter(organization=organization)
        # ดึงข้อมูลคำขอยืมที่รอดำเนินการสำหรับองค์กรนี้
        pending_loans = Loan.objects.filter(item__organization=organization, status='pending')

        context = {
            'organization': organization,
            'items': items,
            'pending_loans': pending_loans,
        }
        return render(request, 'users/dashboard.html', context)
    
    # ถ้าไม่ใช่ทั้งสองบทบาท (ถือว่าเป็นผู้ใช้งานทั่วไป)
    else:
        # ตรวจสอบว่าผู้ใช้มีองค์กรผูกอยู่หรือไม่
        if not user.organization:
            messages.error(request, "บัญชีของคุณยังไม่ได้ถูกผูกกับองค์กร กรุณาติดต่อผู้ดูแลระบบ.")
            # หรือจะ redirect ไปหน้าที่แจ้งให้ผู้ใช้ติดต่อ admin ก็ได้
            return redirect('login') # ให้กลับไปหน้า login ชั่วคราว
        return redirect('user_dashboard')

@login_required
def user_dashboard(request):
    """
    หน้าแดชบอร์ดสำหรับผู้ใช้งานทั่วไป แสดงรายการสิ่งของที่พร้อมให้ยืมและรายการที่ยืมไปแล้ว
    """
    user = request.user
    # ตรวจสอบว่าผู้ใช้มีองค์กรผูกอยู่หรือไม่ก่อนที่จะดึงข้อมูล
    if not user.organization:
        messages.error(request, "บัญชีของคุณยังไม่ได้ถูกผูกกับองค์กร กรุณาติดต่อผู้ดูแลระบบ.")
        return redirect('login') # ให้กลับไปหน้า login ชั่วคราว

    organization = user.organization
    
    # ดึงรายการสิ่งของทั้งหมดที่อยู่ในองค์กรเดียวกันและมีจำนวนที่พร้อมให้ยืม > 0
    items = Item.objects.filter(organization=organization, available_quantity__gt=0)
    
    # ดึงรายการสิ่งของที่ผู้ใช้คนนี้ยืมอยู่
    my_loans = Loan.objects.filter(borrower=request.user)
    
    context = {
        'items': items,
        'my_loans': my_loans,
    }
    return render(request, 'users/user_dashboard.html', context)

def register_organization(request):
    """
    View สำหรับการลงทะเบียนองค์กรใหม่และสร้างผู้ดูแลองค์กรคนแรก
    """
    if request.method == 'POST':
        # สร้าง instance ของฟอร์มด้วยข้อมูลที่ส่งมาจาก POST request
        org_form = OrganizationRegistrationForm(request.POST)
        user_form = UserRegistrationForm(request.POST)

        # ตรวจสอบความถูกต้องของข้อมูลจากทั้งสองฟอร์ม
        if org_form.is_valid() and user_form.is_valid():
            try:
                # ใช้ transaction.atomic() เพื่อให้แน่ใจว่าทั้งการสร้างองค์กรและผู้ใช้จะสำเร็จพร้อมกัน
                # หากมีส่วนใดส่วนหนึ่งล้มเหลว ทุกอย่างจะถูกย้อนกลับ
                with transaction.atomic():
                    # 1. บันทึกข้อมูลองค์กร
                    organization = org_form.save() 
                    
                    # 2. บันทึกข้อมูลผู้ใช้ (Password ถูก Hash ในฟอร์ม UserRegistrationForm.save())
                    user = user_form.save(commit=False)
                    
                    # 3. ผูกผู้ใช้เข้ากับองค์กรที่เพิ่งสร้าง
                    user.organization = organization 
                    # 4. กำหนดให้ผู้ใช้คนนี้เป็นแอดมินองค์กร
                    user.is_org_admin = True 
                    # 5. เปิดใช้งานบัญชีผู้ใช้
                    user.is_active = True 
                    # 6. บันทึกผู้ใช้ลงในฐานข้อมูล
                    user.save()

                    # แสดงข้อความสำเร็จและเปลี่ยนเส้นทางไปยังหน้าล็อกอิน
                    messages.success(request, 'การลงทะเบียนองค์กรและผู้ดูแลสำเร็จแล้ว! กรุณาล็อกอิน')
                    return redirect('login') 
            except Exception as e:
                # หากเกิดข้อผิดพลาดใดๆ ในระหว่าง transaction
                messages.error(request, f'เกิดข้อผิดพลาดในการลงทะเบียน: {e}')
    else:
        # หากเป็น GET request (เข้ามาหน้าครั้งแรก) ให้สร้างฟอร์มเปล่า
        org_form = OrganizationRegistrationForm()
        user_form = UserRegistrationForm()
    
    # ส่งฟอร์มไปยัง template เพื่อแสดงผล
    context = {
        'org_form': org_form,
        'user_form': user_form
    }
    return render(request, 'users/register_organization.html', context)
