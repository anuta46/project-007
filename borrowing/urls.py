# borrowing/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('add-item/', views.add_item, name='add_item'),
    # เปลี่ยนจาก <int:item_id> เป็น <int:asset_id> เพราะตอนนี้ยืม Asset แต่ละชิ้น
    path('borrow/<int:asset_id>/', views.borrow_item, name='borrow_item'),
    path('return/<int:loan_id>/', views.return_item, name='return_item'),
    path('approve-loan/<int:loan_id>/', views.approve_loan, name='approve_loan'),
    path('reject-loan/<int:loan_id>/', views.reject_loan, name='reject_loan'),
    path('edit-item/<int:item_id>/', views.edit_item, name='edit_item'),
    path('delete-item/<int:item_id>/', views.delete_item, name='delete_item'),
]
