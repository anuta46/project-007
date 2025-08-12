# borrowing/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import ItemForm # นำเข้าฟอร์มที่เราสร้าง
from .models import Item

@login_required
def add_item(request):
    # ตรวจสอบสิทธิ์ว่าเป็น Organization Admin หรือไม่
    if not request.user.is_org_admin:
        return redirect('dashboard')

    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = request.user.organization
            item.available_quantity = item.quantity
            item.save()
            return redirect('dashboard')
    else:
        form = ItemForm()

    return render(request, 'borrowing/add_item.html', {'form': form})