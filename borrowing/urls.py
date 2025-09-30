# borrowing/urls.py
from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    # ---------- ฝั่งแอดมินองค์กร (จัดการของตัวเอง) ----------
    path('item-overview/', views.item_overview, name='item_overview'),
    path('add-item/', views.add_item, name='add_item'),
    path('edit-item/<int:item_id>/', views.edit_item, name='edit_item'),
    path('delete-item/<int:item_id>/', views.delete_item, name='delete_item'),

    path('add-asset/', views.add_asset, name='add_asset'),
    path('delete-asset/<int:asset_id>/', views.delete_asset, name='delete_asset'),

    path('approve-loan/<int:loan_id>/', views.approve_loan, name='approve_loan'),
    path('reject-loan/<int:loan_id>/', views.reject_loan, name='reject_loan'),

    # ---------- หน้ารายการกู้ยืม (ตั้งชื่อให้ตรงกับ base.html) ----------
    # pending
    path('pending-loans/', views.pending_loans_view, name='pending_loans_view'),
    path('pending-loans/', views.pending_loans_view, name='pending_loans'),  # alias เผื่อชื่อเก่า

    # active
    path('active-loans/', views.active_loans_view, name='active_loans_view'),
    path('active-loans/', views.active_loans_view, name='active_loans'),     # alias เผื่อชื่อเก่า

    # history (admin)
    path('admin/loan-history/', views.loan_history_admin_view, name='loan_history_admin_view'),
    path('admin/loan-history/', views.loan_history_admin_view, name='loan_history_admin'),  # alias เผื่อชื่อเก่า

    # ---------- ฝั่งผู้ใช้ทั่วไป ----------
    path('borrow-item/<int:asset_id>/', views.borrow_item, name='borrow_item'),
    path('return-item/<int:loan_id>/', views.return_item, name='return_item'),
    path('categories/add/', views.add_category, name='add_category'),
    path('loans/<int:loan_id>/start/', views.start_loan, name='start_loan'),
    
    path('items/new/', views.add_item, name='add_item'),
    
    path('dashboard/', views.dashboard, name='dashboard'),
    path('org-dashboard/', views.dashboard, name='org_dashboard'),  



    # ถ้าโปรเจกต์ที่อื่นเคยอ้างอิง 'my_loans' ให้ redirect มาหน้า users ของคุณ
    path(
        'my-loans/',
        RedirectView.as_view(pattern_name='my_borrowed_items_history', permanent=False),
        name='my_loans',
    ),
]
