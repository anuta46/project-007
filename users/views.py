# users/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

# นำเข้าโมเดลจากแอปพลิเคชันที่ถูกต้อง
from .models import CustomUser, Organization 
from borrowing.models import Item, Loan

# ไม่จำเป็นต้องมีฟังก์ชัน login_view แล้ว เพราะเราใช้ Django's LoginView
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
    user = request.user

    # ตรวจสอบบทบาทของผู้ใช้
    if user.is_platform_admin:
        # ถ้าเป็น Platform Admin ให้ไปที่หน้า Django Admin เลย
        return redirect('/admin/')

    if user.is_org_admin:
        # ถ้าเป็น Organization Admin
        organization = user.organization
        # ดึงข้อมูล items จาก borrowing app
        items = Item.objects.filter(organization=organization)
        # ดึงข้อมูล loans จาก borrowing app ที่รอการอนุมัติ
        pending_loans = Loan.objects.filter(item__organization=organization, status='pending')

        context = {
            'organization': organization,
            'items': items,
            'pending_loans': pending_loans,
        }
        return render(request, 'users/dashboard.html', context)
    
    # ถ้าไม่ใช่ทั้ง Platform Admin และ Organization Admin (คือผู้ใช้งานทั่วไป)
    else:
        return redirect('user_dashboard') # ไปยังหน้า user_dashboard

@login_required
def user_dashboard(request):
    # ดึงข้อมูลองค์กรของผู้ใช้ (ผู้ใช้ทั่วไปจะอยู่ในองค์กรใดองค์กรหนึ่ง)
    organization = request.user.organization

    # ดึงรายการสิ่งของทั้งหมดที่อยู่ในองค์กรเดียวกัน และมีจำนวนที่พร้อมให้ยืม > 0
    items = Item.objects.filter(organization=organization, available_quantity__gt=0)

    # ดึงรายการสิ่งของที่ผู้ใช้คนนี้ยืมอยู่
    my_loans = Loan.objects.filter(borrower=request.user)

    context = {
        'items': items,
        'my_loans': my_loans,
    }
    return render(request, 'users/user_dashboard.html', context)