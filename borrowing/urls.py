# borrowing/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('add-item/', views.add_item, name='add_item'),
    path('borrow/<int:item_id>/', views.borrow_item, name='borrow_item'),
    path('return/<int:loan_id>/', views.return_item, name='return_item'),
    path('approve-loan/<int:loan_id>/', views.approve_loan, name='approve_loan'), # เพิ่มบรรทัดนี้
    path('reject-loan/<int:loan_id>/', views.reject_loan, name='reject_loan'),   # เพิ่มบรรทัดนี้
]