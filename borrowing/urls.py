# borrowing/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # URL สำหรับ Organization Admin เพื่อเพิ่มสิ่งของใหม่
    path('add-item/', views.add_item, name='add_item'),
    # URL สำหรับ Organization Admin เพื่อแก้ไขสิ่งของ
    path('edit-item/<int:item_id>/', views.edit_item, name='edit_item'),
    # URL สำหรับ Organization Admin เพื่อลบสิ่งของ
    path('delete-item/<int:item_id>/', views.delete_item, name='delete_item'),
    # URL สำหรับผู้ใช้ทั่วไปเพื่อขอยืมอุปกรณ์
    path('borrow-item/<int:asset_id>/', views.borrow_item, name='borrow_item'),
    # URL สำหรับผู้ใช้ทั่วไปเพื่อคืนอุปกรณ์
    path('return-item/<int:loan_id>/', views.return_item, name='return_item'),
    # URL สำหรับ Organization Admin เพื่ออนุมัติคำขอยืม
    path('approve-loan/<int:loan_id>/', views.approve_loan, name='approve_loan'),
    # URL สำหรับ Organization Admin เพื่อปฏิเสธคำขอยืม
    path('reject-loan/<int:loan_id>/', views.reject_loan, name='reject_loan'),

    # URL สำหรับ Organization Admin เพื่อดูภาพรวมสิ่งของ
    path('item-overview/', views.item_overview, name='item_overview'),
    
    # URL ใหม่สำหรับ Organization Admin เพื่อดูคำขอยืมที่รอดำเนินการ
    path('pending-loans/', views.pending_loans_view, name='pending_loans_view'),
    # URL ใหม่สำหรับ Organization Admin เพื่อดูรายการยืมที่กำลังดำเนินการ
    path('active-loans/', views.active_loans_view, name='active_loans_view'),
    # URL ใหม่สำหรับ Organization Admin เพื่อดูประวัติการยืมทั้งหมด
    path('admin/loan-history/', views.loan_history_admin_view, name='loan_history_admin_view'),
    
     path('add-asset/', views.add_asset, name='add_asset'),
]
