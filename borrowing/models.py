# borrowing/models.py
from django.db import models
from users.models import Organization, CustomUser

# โมเดลสำหรับสิ่งของที่ให้ยืม
class Item(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    quantity = models.IntegerField(default=1)  # จำนวนทั้งหมดของสิ่งของ
    available_quantity = models.IntegerField(default=1) # จำนวนที่ว่างให้ยืม
    # ผูกสิ่งของกับองค์กรที่ดูแล
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE
    )

    def __str__(self):
        return self.name

# โมเดลสำหรับบันทึกการยืม-คืน
class Loan(models.Model):
    # ผู้ใช้งานที่ยืมสิ่งของ
    borrower = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE
    )
    # สิ่งของที่ถูกยืม
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE
    )
    borrow_date = models.DateTimeField(auto_now_add=True)
    return_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField()

    # สถานะของการยืม
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
        ('rejected', 'Rejected'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.borrower.username} borrowed {self.item.name}"